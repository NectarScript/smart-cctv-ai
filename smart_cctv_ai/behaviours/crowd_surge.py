from __future__ import annotations
from typing import Iterable
from .base import Behaviour, BehaviourContext, Candidate
from ..schema import BehaviourType, Severity


class CrowdSurge(Behaviour):
    """Fire when the number of people inside a zone exceeds `max_people`."""
    name = "crowd_surge"

    def __init__(self, max_people: int = 5):
        self.max_people = max_people
        self._fired: set[tuple[str, str]] = set()  # (cam, zone) latched

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        out: list[Candidate] = []
        for z in ctx.zones:
            if self.name not in z.rules:
                continue
            inside = [t for t in ctx.tracks if z.contains_box(t.xyxy)]
            key = (ctx.camera_id, z.name)
            if len(inside) > self.max_people:
                if key not in self._fired:
                    self._fired.add(key)
                    out.append(Candidate(
                        type=BehaviourType.crowd_surge,
                        severity=Severity.critical,
                        track_ids=[t.track_id for t in inside],
                        zone=z.name,
                        meta={"count": len(inside), "threshold": self.max_people},
                    ))
            elif len(inside) <= self.max_people - 2:
                self._fired.discard(key)  # hysteresis
        return out
