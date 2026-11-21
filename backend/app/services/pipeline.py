"""Background processing: transcribe -> analyze -> draft emails -> done."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlmodel import Session, delete, select

from ..db import get_engine
from ..models import EmailDraft, Meeting, Task
from . import emails as emails_svc
from .extract import ExtractionError, run_extraction
from .llm import LLMError, get_provider
from .store import meeting_out
from .transcribe import TranscriptionError, transcribe_file
from .transcript import parse_transcript, plain_text, segments_from_whisper

log = logging.getLogger(__name__)


def _set(session: Session, m: Meeting, **fields) -> None:
    for k, v in fields.items():
        setattr(m, k, v)
    session.add(m)
    session.commit()
    session.refresh(m)


def generate_emails(session: Session, meeting_id: str, tone: str) -> list[EmailDraft]:
    m = session.get(Meeting, meeting_id)
    out = meeting_out(session, m)
    session.exec(delete(EmailDraft).where(EmailDraft.meeting_id == meeting_id))
    drafts = []
    for d in emails_svc.build_all(out, tone, get_provider()):
        row = EmailDraft(meeting_id=meeting_id, **d)
        session.add(row)
        drafts.append(row)
    m.tone = tone
    session.add(m)
    session.commit()
    return drafts


def process_meeting(meeting_id: str, audio_path: Optional[str] = None) -> None:
    """Runs in a background thread. Never raises: failures are stored on the meeting."""
    with Session(get_engine()) as session:
        m = session.get(Meeting, meeting_id)
        if m is None:
            return
        try:
            if audio_path:
                _set(session, m, status="transcribing")
                res = transcribe_file(Path(audio_path))
                segments = segments_from_whisper(res["segments"])
                _set(session, m, transcript=plain_text(segments), segments=segments, language=res.get("language"))
            else:
                segments = m.segments or parse_transcript(m.transcript)
                _set(session, m, segments=segments)

            provider = get_provider()
            _set(session, m, status="analyzing", provider=provider.name)
            processed = run_extraction(
                provider, segments, title=m.title, meeting_date=m.meeting_date, attendees=list(m.attendees or []),
            )
            result = {
                "summary": processed.summary.model_dump(),
                "decisions": [d.model_dump() for d in processed.decisions],
                "open_questions": [q.model_dump() for q in processed.open_questions],
                "risks": [r.model_dump() for r in processed.risks],
                "topics": processed.topics, "warnings": processed.warnings,
            }
            session.exec(delete(Task).where(Task.meeting_id == m.id, Task.manual == False))  # noqa: E712
            for pos, a in enumerate(processed.action_items):
                session.add(Task(
                    meeting_id=m.id, title=a["title"], description=a["description"], owner=a["owner"],
                    owner_confidence=a["owner_confidence"], deadline_raw=a["deadline_raw"],
                    deadline_resolved=a["deadline_resolved"], priority=a["priority"], status="todo",
                    evidence_quote=a["evidence_quote"], evidence_timestamp=a["evidence_timestamp"],
                    evidence_segment=a["evidence_segment"], verified=a["verified"], position=pos,
                ))
            _set(session, m, result=result, status="drafting")
            generate_emails(session, m.id, m.tone)
            _set(session, m, status="done", error=None)
        except (TranscriptionError, ExtractionError, LLMError) as e:
            log.warning("Meeting %s failed: %s", meeting_id, e)
            session.rollback()
            _set(session, m, status="error", error=str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("Unexpected failure for meeting %s", meeting_id)
            session.rollback()
            _set(session, m, status="error", error=f"Unexpected error: {type(e).__name__}. Check the server logs.")
        finally:
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)
