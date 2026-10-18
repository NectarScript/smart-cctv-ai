from __future__ import annotations
from typing import Iterable
import math
from .base import Behaviour, BehaviourContext, Candidate
from ..schema import BehaviourType, Severity


class UnattendedObject(Behaviour):
    """Fire when a bag-class object has been stationary and its nearest person
    is far away (or absent) for N seconds.

    `ctx.objects` holds non-person detections (bag, backpack, suitcase, handbag).
    """
    name = "unattended_object"

    def __init__(self, stationary_seconds: float = 15.0,
                 abandon_distance_px: float = 180.0,
                 move_tolerance_px: float = 20.0):
        self.stationary_seconds = stationary_seconds
        self.abandon_distance = abandon_distance_px
        self.move_tol = move_tolerance_px
        # obj.track_id -> (first_ts, last_xy)
        self._state: dict[int, tuple[float, tuple[float, float]]] = {}
        self._fired: set[int] = set()

    def _bottom_center(self, xyxy):
        x1, y1, x2, y2 = xyxy
        return ((x1 + x2) / 2.0, y2)

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        objs = ctx.objects or []
        out: list[Candidate] = []
        seen: set[int] = set()
        for o in objs:
            seen.add(o.track_id)
            cx, cy = self._bottom_center(o.xyxy)
            prev = self._state.get(o.track_id)
            if prev is None:
                self._state[o.track_id] = (ctx.ts, (cx, cy))
                continue
            first_ts, (px, py) = prev
            if math.hypot(cx - px, cy - py) > self.move_tol:
                # moved; reset timer
                self._state[o.track_id] = (ctx.ts, (cx, cy))
                self._fired.discard(o.track_id)
                continue
            dwell = ctx.ts - first_ts
            if dwell < self.stationary_seconds:
                continue
            # Nearest person distance
            nearest = math.inf
            for t in ctx.tracks:
                tx, ty = self._bottom_center(t.xyxy)
                nearest = min(nearest, math.hypot(cx - tx, cy - ty))
            if nearest >= self.abandon_distance and o.track_id not in self._fired:
                self._fired.add(o.track_id)
                out.append(Candidate(
                    type=BehaviourType.unattended_object,
                    severity=Severity.critical,
                    track_ids=[o.track_id],
                    meta={"stationary_seconds": round(dwell, 1),
                          "nearest_person_px": round(nearest, 1),
                          "class": o.cls},
                ))
        # Drop gone objects
        for gone in set(self._state.keys()) - seen:
            self._state.pop(gone, None)
            self._fired.discard(gone)
        return out
