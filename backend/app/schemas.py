"""Pydantic v2 schemas: LLM extraction contract + API payloads."""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Level = Literal["high", "medium", "low"]
TaskStatus = Literal["todo", "in_progress", "done"]
Tone = Literal["professional", "friendly", "concise"]


# ---------- LLM extraction contract (strict) ----------
class Summary(BaseModel):
    bullets: list[str] = Field(default_factory=list, max_length=8)
    paragraph: str = ""


class Decision(BaseModel):
    id: str = ""
    decision: str
    rationale: Optional[str] = None
    evidence_quote: str
    evidence_timestamp: Optional[float] = None
    evidence_segment: Optional[int] = None
    verified: bool = True


class ActionItemLLM(BaseModel):
    id: str = ""
    title: str
    description: str = ""
    owner: Optional[str] = None
    owner_confidence: Level = "low"
    deadline_raw: Optional[str] = None
    priority: Level = "medium"
    evidence_quote: str
    evidence_timestamp: Optional[float] = None

    @field_validator("owner", "deadline_raw", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        if isinstance(v, str) and v.strip().lower() in {"", "null", "none", "unknown", "n/a", "unassigned"}:
            return None
        return v


class OpenQuestion(BaseModel):
    id: str = ""
    question: str
    suggested_owner: Optional[str] = None


class Risk(BaseModel):
    id: str = ""
    risk: str
    severity: Level = "medium"


class Extraction(BaseModel):
    """What the LLM must return (JSON)."""

    summary: Summary
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItemLLM] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


# ---------- API payloads ----------
class Segment(BaseModel):
    idx: int
    start: Optional[float] = None
    end: Optional[float] = None
    speaker: Optional[str] = None
    text: str


class MeetingCreate(BaseModel):
    title: str = Field("Untitled meeting", max_length=200)
    date: Optional[dt.date] = None
    attendees: str | list[str] = ""
    timezone: str = "UTC"
    transcript: str = Field(..., max_length=400_000)
    tone: Tone = "friendly"
    sample_id: Optional[str] = None


class MeetingPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)


class TaskOut(BaseModel):
    id: str
    meeting_id: str
    title: str
    description: str
    owner: Optional[str]
    owner_confidence: str
    deadline_raw: Optional[str]
    deadline_resolved: Optional[dt.date]
    priority: str
    status: str
    evidence_quote: str
    evidence_timestamp: Optional[float]
    evidence_segment: Optional[int]
    verified: bool
    manual: bool
    position: int
    needs_clarification: bool
    clarification_reasons: list[str]


class TaskCreate(BaseModel):
    meeting_id: str
    title: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    owner: Optional[str] = None
    deadline_resolved: Optional[dt.date] = None
    priority: Level = "medium"
    status: TaskStatus = "todo"


class TaskPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    owner: Optional[str] = None
    deadline_resolved: Optional[dt.date] = None
    deadline_raw: Optional[str] = None
    priority: Optional[Level] = None
    status: Optional[TaskStatus] = None
    position: Optional[int] = None
    clear_owner: bool = False
    clear_deadline: bool = False


class EmailOut(BaseModel):
    id: str
    meeting_id: str
    kind: str
    recipient: Optional[str]
    to_addr: Optional[str]
    tone: str
    subject: str
    body_text: str
    body_html: str
    edited: bool


class EmailPatch(BaseModel):
    subject: Optional[str] = None
    body_text: Optional[str] = None
    to_addr: Optional[str] = None


class MeetingSummaryOut(BaseModel):
    id: str
    title: str
    date: dt.date
    status: str
    source: str
    open_tasks: int
    total_tasks: int
    overdue_tasks: int
    created_at: str


class MeetingOut(BaseModel):
    id: str
    title: str
    date: dt.date
    timezone: str
    attendees: list[str]
    status: str
    error: Optional[str]
    source: str
    provider: str
    language: Optional[str]
    tone: str
    transcript: str
    segments: list[Segment]
    summary: Optional[Summary]
    decisions: list[Decision]
    open_questions: list[OpenQuestion]
    risks: list[Risk]
    topics: list[str]
    warnings: list[str]
    tasks: list[TaskOut]
    emails: list[EmailOut]


class DashboardOut(BaseModel):
    meetings: int
    open_tasks: int
    overdue_tasks: int
    workload: dict[str, int]
