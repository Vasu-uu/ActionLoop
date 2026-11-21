from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from ..db import get_session
from ..errors import ApiError
from ..models import Meeting
from ..services import exports as ex
from ..services.store import meeting_out

router = APIRouter(tags=["exports"])

FORMATS = {
    "md": ("text/markdown; charset=utf-8", ex.to_markdown),
    "csv": ("text/csv; charset=utf-8", ex.to_csv),
    "ics": ("text/calendar; charset=utf-8", ex.to_ics),
    "json": ("application/json", ex.to_json),
    "slack": ("text/plain; charset=utf-8", ex.to_slack),
    "html": ("text/html; charset=utf-8", ex.to_html),
}


def _out(session: Session, meeting_id: str):
    m = session.get(Meeting, meeting_id)
    if not m:
        raise ApiError(404, "meeting_not_found", "Meeting not found.")
    return meeting_out(session, m)


@router.get("/api/meetings/{meeting_id}/export/{fmt}")
def export(meeting_id: str, fmt: str, session: Session = Depends(get_session)):
    out = _out(session, meeting_id)
    if out.status != "done":
        raise ApiError(409, "not_ready", "The meeting is still being processed.")
    if fmt == "zip":
        data = ex.to_zip(out, ex.emails_to_markdown(out))
        return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{ex.filename(out, "zip")}"'})
    if fmt not in FORMATS:
        raise ApiError(404, "unknown_format", f"Unknown export format '{fmt}'. Use: md, csv, ics, json, slack, html, zip.")
    ctype, fn = FORMATS[fmt]
    ext = "txt" if fmt == "slack" else fmt
    return Response(fn(out), media_type=ctype, headers={"Content-Disposition": f'attachment; filename="{ex.filename(out, ext)}"'})


@router.get("/m/{meeting_id}", response_class=HTMLResponse, include_in_schema=False)
def shared_report(meeting_id: str, session: Session = Depends(get_session)):
    """Shareable read-only HTML report."""
    out = _out(session, meeting_id)
    return HTMLResponse(ex.to_html(out), headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "X-Robots-Tag": "noindex"})
