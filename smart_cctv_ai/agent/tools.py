"""Tools the chat agent can call. Each tool reads from SQLite; nothing writes."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlmodel import Session, select, func
from ..schema import Event, BehaviourType, Severity
from .. import db


def _parse_since(since: str | None) -> datetime | None:
    """Accept ISO datetimes or '15m', '2h', '1d' relative strings."""
    if not since:
        return None
    s = since.strip().lower()
    try:
        if s.endswith(("m", "h", "d")):
            n = int(s[:-1])
            unit = s[-1]
            delta = {"m": timedelta(minutes=n),
                     "h": timedelta(hours=n),
                     "d": timedelta(days=n)}[unit]
            return datetime.now(timezone.utc) - delta
        return datetime.fromisoformat(s)
    except Exception:
        return None


def count_events(camera_id: str | None = None, type: str | None = None,
                 zone: str | None = None, since: str | None = None) -> dict:
    with Session(db.engine()) as s:
        stmt = select(func.count(Event.id))
        if camera_id: stmt = stmt.where(Event.camera_id == camera_id)
        if type: stmt = stmt.where(Event.type == BehaviourType(type))
        if zone: stmt = stmt.where(Event.zone == zone)
        t = _parse_since(since)
        if t: stmt = stmt.where(Event.start_ts >= t)
        n = s.exec(stmt).one()
    return {"count": int(n), "camera_id": camera_id, "type": type,
            "zone": zone, "since": since}


def list_events(camera_id: str | None = None, type: str | None = None,
                zone: str | None = None, since: str | None = None,
                limit: int = 10) -> dict:
    with Session(db.engine()) as s:
        stmt = select(Event).order_by(Event.id.desc()).limit(limit)
        if camera_id: stmt = stmt.where(Event.camera_id == camera_id)
        if type: stmt = stmt.where(Event.type == BehaviourType(type))
        if zone: stmt = stmt.where(Event.zone == zone)
        t = _parse_since(since)
        if t: stmt = stmt.where(Event.start_ts >= t)
        rows = s.exec(stmt).all()
    return {"events": [
        {"id": e.id, "type": e.type.value, "severity": e.severity.value,
         "camera_id": e.camera_id, "zone": e.zone,
         "start_ts": e.start_ts.isoformat(), "vlm_summary": e.vlm_summary}
        for e in rows]}


def get_event(event_id: int) -> dict:
    with Session(db.engine()) as s:
        e = s.get(Event, event_id)
        if e is None:
            return {"error": f"event {event_id} not found"}
        return {"id": e.id, "type": e.type.value, "severity": e.severity.value,
                "camera_id": e.camera_id, "zone": e.zone,
                "start_ts": e.start_ts.isoformat(),
                "end_ts": e.end_ts.isoformat(),
                "clip_url": (f"/events/{e.id}/clip" if e.clip else None),
                "snapshot_url": (f"/events/{e.id}/snapshot" if e.snapshot else None),
                "vlm_verdict": e.vlm_verdict, "vlm_summary": e.vlm_summary,
                "meta": e.meta}


def search_events(query: str, top_k: int = 10) -> dict:
    """Semantic search via CLIP. Imported lazily to keep the agent module cheap."""
    from ..search.clip_index import ClipIndex
    idx = _get_index()
    hits = idx.search(query, top_k=top_k)
    out = []
    with Session(db.engine()) as s:
        for ev_id, score in hits:
            e = s.get(Event, ev_id)
            if e is None: continue
            out.append({"id": e.id, "type": e.type.value,
                        "camera_id": e.camera_id, "zone": e.zone,
                        "start_ts": e.start_ts.isoformat(),
                        "score": round(score, 3)})
    return {"query": query, "hits": out}


_index_singleton: Any = None


def _get_index():
    global _index_singleton
    if _index_singleton is None:
        from ..search.clip_index import ClipIndex
        _index_singleton = ClipIndex()
    return _index_singleton


TOOLS: dict[str, Any] = {
    "count_events": count_events,
    "list_events": list_events,
    "get_event": get_event,
    "search_events": search_events,
}


TOOL_SPEC = """
Available tools (return exactly one JSON object with a "tool" key and args):

count_events  {camera_id?, type?, zone?, since?}  -> {count}
list_events   {camera_id?, type?, zone?, since?, limit?}  -> {events: [...]}
get_event     {event_id}                           -> event detail
search_events {query, top_k?}                      -> {hits: [...]}

Notes:
- `type` ∈ intrusion | loitering | running | fighting | fall | unattended_object | crowd_surge
- `since` is a relative string: "15m", "2h", "1d" (minutes, hours, days)
- Pick the single tool that best answers the user's question.
- Reply ONLY with JSON: {"tool": "<name>", "args": {...}}  — no prose.
"""
