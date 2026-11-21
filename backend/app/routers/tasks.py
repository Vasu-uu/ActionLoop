from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..errors import ApiError
from ..models import Meeting, Task
from ..schemas import TaskCreate, TaskOut, TaskPatch
from ..services.store import task_out

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get(session: Session, task_id: str) -> Task:
    t = session.get(Task, task_id)
    if not t:
        raise ApiError(404, "task_not_found", "Task not found.")
    return t


def _resequence(session: Session, meeting_id: str, status: str, moved: Task | None, position: int | None) -> None:
    """Keep positions dense (0..n) within a column, inserting `moved` at `position`."""
    col = [t for t in session.exec(select(Task).where(Task.meeting_id == meeting_id, Task.status == status).order_by(Task.position, Task.created_at)).all()
           if not moved or t.id != moved.id]
    if moved is not None:
        idx = len(col) if position is None else max(0, min(position, len(col)))
        col.insert(idx, moved)
    for i, t in enumerate(col):
        t.position = i
        session.add(t)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, session: Session = Depends(get_session)):
    if not session.get(Meeting, body.meeting_id):
        raise ApiError(404, "meeting_not_found", "Meeting not found.")
    t = Task(
        meeting_id=body.meeting_id, title=body.title.strip(), description=body.description,
        owner=(body.owner or "").strip() or None, owner_confidence="high" if body.owner else "low",
        deadline_resolved=body.deadline_resolved, priority=body.priority, status=body.status, manual=True, verified=True,
    )
    session.add(t)
    session.flush()
    _resequence(session, t.meeting_id, t.status, t, None)
    session.commit()
    session.refresh(t)
    return task_out(t)


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(task_id: str, body: TaskPatch, session: Session = Depends(get_session)):
    t = _get(session, task_id)
    data = body.model_dump(exclude_unset=True)
    old_status = t.status
    for key in ("title", "description", "priority", "deadline_raw"):
        if key in data and data[key] is not None:
            setattr(t, key, data[key].strip() if isinstance(data[key], str) else data[key])
    if data.get("clear_owner"):
        t.owner, t.owner_confidence = None, "low"
    elif "owner" in data and data["owner"] is not None:
        t.owner = data["owner"].strip() or None
        t.owner_confidence = "high" if t.owner else "low"  # a human confirmed it
    if data.get("clear_deadline"):
        t.deadline_resolved = None
    elif "deadline_resolved" in data and data["deadline_resolved"] is not None:
        t.deadline_resolved = data["deadline_resolved"]
        if not t.deadline_raw:
            t.deadline_raw = data["deadline_resolved"].isoformat()
    if "status" in data and data["status"] is not None:
        t.status = data["status"]
    session.add(t)
    if t.status != old_status or data.get("position") is not None:
        _resequence(session, t.meeting_id, t.status, t, data.get("position"))
        if t.status != old_status:
            _resequence(session, t.meeting_id, old_status, None, None)
    session.commit()
    session.refresh(t)
    return task_out(t)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, session: Session = Depends(get_session)):
    t = _get(session, task_id)
    mid, st = t.meeting_id, t.status
    session.delete(t)
    session.flush()
    _resequence(session, mid, st, None, None)
    session.commit()
