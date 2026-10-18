from __future__ import annotations
from typing import Iterable
from .base import Behaviour, BehaviourContext, Candidate
from ..schema import BehaviourType, Severity


class Loitering(Behaviour):
    """Fire when a track has been inside a zone continuously for >= dwell_seconds."""
    name = "loitering"

    def __init__(self, dwell_seconds: float = 10.0):
        self.dwell = dwell_seconds
        # (camera_id, track_id, zone) -> entry_ts
        self._entries: dict[tuple[str, int, str], float] = {}
        # keys already fired this stay — avoid re-firing until track leaves
        self._fired: set[tuple[str, int, str]] = set()

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        out: list[Candidate] = []
        seen: set[tuple[str, int, str]] = set()
        for z in ctx.zones:
            if self.name not in z.rules:
                continue
            for t in ctx.tracks:
                key = (ctx.camera_id, t.track_id, z.name)
                if z.contains_box(t.xyxy):
                    seen.add(key)
                    entry = self._entries.setdefault(key, ctx.ts)
                    dwell = ctx.ts - entry
                    if dwell >= self.dwell and key not in self._fired:
                        self._fired.add(key)
                        out.append(Candidate(
                            type=BehaviourType.loitering,
                            severity=Severity.suspicious,
                            track_ids=[t.track_id],
                            zone=z.name,
                            meta={"dwell_seconds": round(dwell, 2)},
                        ))
        # Reset state for keys that are no longer inside the zone
        gone = set(self._entries.keys()) - seen
        for k in gone:
            self._entries.pop(k, None)
            self._fired.discard(k)
        return out
