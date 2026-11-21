from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if url.startswith("sqlite"):
            if ":memory:" in url:
                kwargs["poolclass"] = StaticPool
            else:
                Path(url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _pragma(dbapi_con, _):  # noqa: ANN001
                cur = dbapi_con.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
    return _engine


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s
