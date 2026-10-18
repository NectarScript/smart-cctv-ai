from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session
from ..schema import Event
from ..search.clip_index import ClipIndex
from .. import db

router = APIRouter()
_index: ClipIndex | None = None


def _idx() -> ClipIndex:
    global _index
    if _index is None:
        _index = ClipIndex()
    return _index


@router.get("/search")
def search(q: str = Query(..., min_length=1), top_k: int = 10):
    try:
        hits = _idx().search(q, top_k=top_k)
    except Exception as e:
        raise HTTPException(500, f"search failed: {e}")
    out = []
    with Session(db.engine()) as s:
        for ev_id, score in hits:
            e = s.get(Event, ev_id)
            if e is None:
                continue
            out.append({
                "id": e.id, "type": e.type.value, "severity": e.severity.value,
                "camera_id": e.camera_id, "zone": e.zone,
                "start_ts": e.start_ts.isoformat(),
                "snapshot_url": f"/events/{e.id}/snapshot",
                "clip_url": f"/events/{e.id}/clip" if e.clip else None,
                "score": round(score, 3),
            })
    return {"query": q, "hits": out}
