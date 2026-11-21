"""Helpers that turn DB rows into API schemas and compute dashboard numbers."""
from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from ..models import EmailDraft, Meeting, Task
from ..schemas import (
    DashboardOut, Decision, EmailOut, MeetingOut, MeetingSummaryOut, OpenQuestion, Risk, Segment, Summary, TaskOut,
)
from .extract import clarification_reasons


def task_out(t: Task) -> TaskOut:
    reasons = clarification_reasons(
        owner=t.owner, owner_confidence=t.owner_confidence, deadline_raw=t.deadline_raw,
        deadline_resolved=t.deadline_resolved, verified=t.verified or t.manual, title=t.title,
    )
    return TaskOut(
        id=t.id, meeting_id=t.meeting_id, title=t.title, description=t.description, owner=t.owner,
        owner_confidence=t.owner_confidence, deadline_raw=t.deadline_raw, deadline_resolved=t.deadline_resolved,
        priority=t.priority, status=t.status, evidence_quote=t.evidence_quote, evidence_timestamp=t.evidence_timestamp,
        evidence_segment=t.evidence_segment, verified=t.verified, manual=t.manual, position=t.position,
        needs_clarification=bool(reasons), clarification_reasons=reasons,
    )


def email_out(e: EmailDraft) -> EmailOut:
    return EmailOut.model_validate(e, from_attributes=True)


def meeting_out(session: Session, m: Meeting) -> MeetingOut:
    tasks = session.exec(select(Task).where(Task.meeting_id == m.id).order_by(Task.position, Task.created_at)).all()
    emails = session.exec(select(EmailDraft).where(EmailDraft.meeting_id == m.id).order_by(EmailDraft.kind.desc(), EmailDraft.recipient)).all()
    r = m.result or {}
    return MeetingOut(
        id=m.id, title=m.title, date=m.meeting_date, timezone=m.timezone, attendees=list(m.attendees or []),
        status=m.status, error=m.error, source=m.source, provider=m.provider, language=m.language, tone=m.tone,
        transcript=m.transcript, segments=[Segment(**s) for s in (m.segments or [])],
        summary=Summary(**r["summary"]) if r.get("summary") else None,
        decisions=[Decision(**d) for d in r.get("decisions", [])],
        open_questions=[OpenQuestion(**q) for q in r.get("open_questions", [])],
        risks=[Risk(**x) for x in r.get("risks", [])], topics=r.get("topics", []), warnings=r.get("warnings", []),
        tasks=[task_out(t) for t in tasks], emails=[email_out(e) for e in emails],
    )


def _is_open(t: Task) -> bool:
    return t.status != "done"


def meeting_summaries(session: Session) -> list[MeetingSummaryOut]:
    today = date.today()
    out = []
    for m in session.exec(select(Meeting).order_by(Meeting.created_at.desc())).all():
        tasks = session.exec(select(Task).where(Task.meeting_id == m.id)).all()
        out.append(
            MeetingSummaryOut(
                id=m.id, title=m.title, date=m.meeting_date, status=m.status, source=m.source,
                open_tasks=sum(_is_open(t) for t in tasks), total_tasks=len(tasks),
                overdue_tasks=sum(_is_open(t) and bool(t.deadline_resolved) and t.deadline_resolved < today for t in tasks),
                created_at=m.created_at.isoformat(),
            )
        )
    return out


def dashboard(session: Session) -> DashboardOut:
    today = date.today()
    tasks = session.exec(select(Task)).all()
    open_tasks = [t for t in tasks if _is_open(t)]
    workload: dict[str, int] = {}
    for t in open_tasks:
        key = t.owner or "Unassigned"
        workload[key] = workload.get(key, 0) + 1
    return DashboardOut(
        meetings=len(session.exec(select(Meeting)).all()),
        open_tasks=len(open_tasks),
        overdue_tasks=sum(bool(t.deadline_resolved) and t.deadline_resolved < today for t in open_tasks),
        workload=dict(sorted(workload.items(), key=lambda kv: -kv[1])),
    )
