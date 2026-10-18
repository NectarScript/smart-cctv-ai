from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import Session, select
from ..schema import Event, EventRead
from .. import db

router = APIRouter(prefix="/events")


@router.get("", response_model=list[EventRead])
def list_events(limit: int = 100, camera_id: str | None = None):
    with Session(db.engine()) as s:
        stmt = select(Event).order_by(Event.id.desc()).limit(limit)
        if camera_id:
            stmt = select(Event).where(Event.camera_id == camera_id)\
                .order_by(Event.id.desc()).limit(limit)
        return [EventRead(**e.model_dump()) for e in s.exec(stmt).all()]


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: int):
    with Session(db.engine()) as s:
        ev = s.get(Event, event_id)
        if ev is None:
            raise HTTPException(404, "event not found")
        return EventRead(**ev.model_dump())


@router.get("/{event_id}/snapshot")
def snapshot(event_id: int):
    with Session(db.engine()) as s:
        ev = s.get(Event, event_id)
        if ev is None or not ev.snapshot:
            raise HTTPException(404, "snapshot not found")
    p = Path(ev.snapshot)
    if not p.exists():
        raise HTTPException(404, "snapshot file missing")
    return FileResponse(p, media_type="image/jpeg")
