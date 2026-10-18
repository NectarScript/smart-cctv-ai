from __future__ import annotations
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from .schema import Event  # noqa: F401  (registers table)

_engine = None
_DB_PATH = Path("data/events.db")


def init(db_path: Path | str = _DB_PATH):
    global _engine
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{p.as_posix()}",
                            connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(_engine)
    return _engine


def engine():
    if _engine is None:
        init()
    return _engine


def session() -> Session:
    return Session(engine())
