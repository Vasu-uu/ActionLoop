from __future__ import annotations

import asyncio
import json
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session, delete, select

from ..config import get_settings
from ..db import get_engine, get_session
from ..errors import ApiError
from ..models import EmailDraft, Meeting, Task
from ..schemas import (
    DashboardOut, EmailOut, EmailPatch, MeetingCreate, MeetingOut, MeetingPatch, MeetingSummaryOut, Tone,
)
from ..services import emails as emails_svc
from ..services import store
from ..services.llm import get_provider
from ..services.pipeline import generate_emails, process_meeting
from ..services.transcribe import ALLOWED_EXTENSIONS, TranscriptionError, transcribe_file
from ..services.transcript import parse_transcript

router = APIRouter(prefix="/api", tags=["meetings"])
MIN_WORDS = 8


def _get_meeting(session: Session, meeting_id: str) -> Meeting:
    m = session.get(Meeting, meeting_id)
    if not m:
        raise ApiError(404, "meeting_not_found", "Meeting not found.")
    return m


def _clean_text(text: str) -> str:
    return text.replace("\x00", "").strip()


def _new_meeting(title: str, when: Optional[date], attendees, tz: str, tone: str, source: str, transcript: str = "") -> Meeting:
    return Meeting(
        title=(title or "Untitled meeting").strip()[:200] or "Untitled meeting", meeting_date=when or date.today(),
        timezone=(tz or "UTC")[:64], attendees=emails_svc.parse_attendees(attendees), tone=tone, source=source,
        transcript=transcript, status="queued", provider=get_provider().name,
    )


# ---------- samples ----------
def _samples() -> list[dict]:
    p = Path(get_settings().samples_dir) / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


@router.get("/samples")
def list_samples():
    return [{k: v for k, v in s.items() if k != "file"} for s in _samples()]


@router.get("/samples/{sample_id}")
def get_sample(sample_id: str):
    for s in _samples():
        if s["id"] == sample_id:
            text = (Path(get_settings().samples_dir) / s["file"]).read_text(encoding="utf-8")
            return {**{k: v for k, v in s.items() if k != "file"}, "transcript": text, "date": date.today().isoformat()}
    raise ApiError(404, "sample_not_found", "Unknown sample.")


# ---------- create ----------
@router.post("/meetings", response_model=MeetingOut, status_code=202)
def create_meeting(body: MeetingCreate, bg: BackgroundTasks, session: Session = Depends(get_session)):
    text = _clean_text(body.transcript)
    if len(text.split()) < MIN_WORDS:
        raise ApiError(422, "transcript_too_short", f"The transcript is too short to analyse (need at least {MIN_WORDS} words).")
    m = _new_meeting(body.title, body.date, body.attendees, body.timezone, body.tone,
                     "sample" if body.sample_id else "text", text)
    m.segments = parse_transcript(text)
    session.add(m)
    session.commit()
    session.refresh(m)
    bg.add_task(process_meeting, m.id)
    return store.meeting_out(session, m)


@router.post("/meetings/audio", response_model=MeetingOut, status_code=202)
async def create_meeting_from_audio(
    bg: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form("Untitled meeting"),
    meeting_date: Optional[date] = Form(None, alias="date"),
    attendees: str = Form(""),
    timezone: str = Form("UTC"),
    tone: Tone = Form("friendly"),
    session: Session = Depends(get_session),
):
    path = await _save_upload(file)
    m = _new_meeting(title, meeting_date, attendees, timezone, tone, "audio")
    session.add(m)
    session.commit()
    session.refresh(m)
    bg.add_task(process_meeting, m.id, str(path))
    return store.meeting_out(session, m)


async def _save_upload(file: UploadFile) -> Path:
    """Validate type, stream to a temp file enforcing the size limit. Caller (pipeline) deletes it."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ApiError(415, "unsupported_file_type", f"Unsupported file type '{ext or 'unknown'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.")
    limit = get_settings().max_upload_mb * 1024 * 1024
    fd, name = tempfile.mkstemp(prefix="actionloop_up_", suffix=ext)
    size = 0
    try:
        with open(fd, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ApiError(413, "file_too_large", f"File is larger than the {get_settings().max_upload_mb} MB limit.")
                out.write(chunk)
        if size == 0:
            raise ApiError(422, "empty_file", "The uploaded file is empty.")
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


@router.post("/transcribe")
async def transcribe_only(file: UploadFile = File(...)):
    """Transcribe a file and return text + timestamped segments (no meeting is created)."""
    path = await _save_upload(file)
    try:
        return await asyncio.to_thread(transcribe_file, path)
    except TranscriptionError as e:
        raise ApiError(422, "transcription_failed", str(e)) from e
    finally:
        path.unlink(missing_ok=True)


# ---------- read / update / delete ----------
@router.get("/meetings", response_model=list[MeetingSummaryOut])
def list_meetings(session: Session = Depends(get_session)):
    return store.meeting_summaries(session)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(session: Session = Depends(get_session)):
    return store.dashboard(session)


@router.get("/meetings/{meeting_id}", response_model=MeetingOut)
def get_meeting(meeting_id: str, session: Session = Depends(get_session)):
    return store.meeting_out(session, _get_meeting(session, meeting_id))


@router.patch("/meetings/{meeting_id}", response_model=MeetingOut)
def rename_meeting(meeting_id: str, body: MeetingPatch, session: Session = Depends(get_session)):
    m = _get_meeting(session, meeting_id)
    if body.title:
        m.title = body.title.strip()
    session.add(m)
    session.commit()
    return store.meeting_out(session, m)


@router.delete("/meetings/{meeting_id}", status_code=204)
def delete_meeting(meeting_id: str, session: Session = Depends(get_session)):
    m = _get_meeting(session, meeting_id)
    session.exec(delete(Task).where(Task.meeting_id == m.id))
    session.exec(delete(EmailDraft).where(EmailDraft.meeting_id == m.id))
    session.delete(m)
    session.commit()


# ---------- progress (SSE) ----------
STEPS = ["transcribing", "analyzing", "drafting", "done"]


@router.get("/meetings/{meeting_id}/progress")
async def progress(meeting_id: str):
    with Session(get_engine()) as s:
        _get_meeting(s, meeting_id)

    async def gen():
        last = None
        for _ in range(60 * 30 * 2):  # up to ~30 min
            with Session(get_engine()) as s:
                m = s.get(Meeting, meeting_id)
                payload = {"status": m.status if m else "error", "error": m.error if m else "Meeting was deleted."}
            if payload != last:
                yield f"data: {json.dumps(payload)}\n\n"
                last = payload
            if payload["status"] in ("done", "error"):
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- emails ----------
@router.post("/meetings/{meeting_id}/emails", response_model=list[EmailOut])
def regenerate_emails(meeting_id: str, tone: Tone = Query("friendly"), session: Session = Depends(get_session)):
    m = _get_meeting(session, meeting_id)
    if m.status != "done":
        raise ApiError(409, "not_ready", "The meeting is still being processed.")
    generate_emails(session, m.id, tone)
    return store.meeting_out(session, m).emails


@router.post("/emails/{email_id}/regenerate", response_model=EmailOut)
def regenerate_one_email(email_id: str, tone: Tone = Query("friendly"), session: Session = Depends(get_session)):
    e = session.get(EmailDraft, email_id)
    if not e:
        raise ApiError(404, "email_not_found", "Email draft not found.")
    out = store.meeting_out(session, _get_meeting(session, e.meeting_id))
    provider = get_provider()
    if e.kind == "recap":
        d = emails_svc.build_recap(out, tone, provider)
    else:
        mine = [t for t in out.tasks if t.owner == e.recipient and t.status != "done"]
        d = emails_svc.build_owner_email(out, e.recipient or "", mine, tone, provider)
    for k, v in d.items():
        setattr(e, k, v)
    e.edited = False
    session.add(e)
    session.commit()
    return store.email_out(e)


@router.patch("/emails/{email_id}", response_model=EmailOut)
def edit_email(email_id: str, body: EmailPatch, session: Session = Depends(get_session)):
    e = session.get(EmailDraft, email_id)
    if not e:
        raise ApiError(404, "email_not_found", "Email draft not found.")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(e, k, v)
    if "body_text" in data:
        import html

        e.body_html = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in re.split(r"\n{2,}", e.body_text))
    e.edited = True
    session.add(e)
    session.commit()
    return store.email_out(e)
