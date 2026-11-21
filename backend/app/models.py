"""SQLModel tables."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Meeting(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    title: str = "Untitled meeting"
    meeting_date: date = Field(default_factory=date.today)
    timezone: str = "UTC"
    attendees: list = Field(default_factory=list, sa_column=Column(JSON))
    transcript: str = ""
    segments: list = Field(default_factory=list, sa_column=Column(JSON))
    language: Optional[str] = None
    source: str = "text"  # text | audio | sample
    status: str = "queued"  # queued|transcribing|analyzing|drafting|done|error
    error: Optional[str] = None
    provider: str = "demo"
    tone: str = "friendly"
    # extraction result minus action items (those live in Task)
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


class Task(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    meeting_id: str = Field(foreign_key="meeting.id", index=True)
    title: str
    description: str = ""
    owner: Optional[str] = None
    owner_confidence: str = "low"
    deadline_raw: Optional[str] = None
    deadline_resolved: Optional[date] = None
    priority: str = "medium"
    status: str = "todo"  # todo | in_progress | done
    evidence_quote: str = ""
    evidence_timestamp: Optional[float] = None
    evidence_segment: Optional[int] = None
    verified: bool = True
    manual: bool = False
    position: int = 0
    created_at: datetime = Field(default_factory=_now)


class EmailDraft(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    meeting_id: str = Field(foreign_key="meeting.id", index=True)
    kind: str = "recap"  # recap | owner
    recipient: Optional[str] = None
    to_addr: Optional[str] = None
    tone: str = "friendly"
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    edited: bool = False
