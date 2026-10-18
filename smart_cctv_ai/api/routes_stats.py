from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
from sqlmodel import Session, select
from ..schema import Event
from .. import db

router = APIRouter(prefix="/stats")


@router.get("")
def stats(hours: int = 24):
    """Counts for the last `hours` window, grouped by hour / type / camera."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    by_hour: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    by_camera: dict[str, int] = defaultdict(int)
    by_severity: dict[str, int] = defaultdict(int)
    total = 0
    with Session(db.engine()) as s:
        rows = s.exec(select(Event).where(Event.start_ts >= since)).all()
    for e in rows:
        total += 1
        hour_key = e.start_ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
        by_hour[hour_key] += 1
        by_type[e.type.value] += 1
        by_camera[e.camera_id] += 1
        by_severity[e.severity.value] += 1

    return {
        "window_hours": hours,
        "total": total,
        "by_hour": [{"hour": h, "count": by_hour[h]} for h in sorted(by_hour)],
        "by_type": [{"type": k, "count": v} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
        "by_camera": [{"camera_id": k, "count": v} for k, v in sorted(by_camera.items(), key=lambda x: -x[1])],
        "by_severity": [{"severity": k, "count": v} for k, v in sorted(by_severity.items())],
    }
