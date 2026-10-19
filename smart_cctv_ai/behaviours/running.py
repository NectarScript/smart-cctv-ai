from __future__ import annotations
from collections import deque
from typing import Iterable
import math
from .base import Behaviour, BehaviourContext, Candidate
from ..schema import BehaviourType, Severity


class Running(Behaviour):
    """Fire when a track's speed normalised by box height exceeds threshold.

    Speed uses the bottom-center of the bbox (ground point); dividing by
    box height makes it roughly camera-distance invariant.
    """
    name = "running"

    def __init__(self, min_speed_hpersec: float = 2.5,
                 window_seconds: float = 1.0):
        self.min_speed = min_speed_hpersec
        self.window = window_seconds
        # track_id -> deque[(ts, x, y, h)]
        self._hist: dict[int, deque] = {}

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        out: list[Candidate] = []
        alive_ids: set[int] = set()
        for t in ctx.tracks:
            alive_ids.add(t.track_id)
            x1, y1, x2, y2 = t.xyxy
            cx, cy = (x1 + x2) / 2.0, y2
            h = max(y2 - y1, 1.0)
            dq = self._hist.setdefault(t.track_id, deque(maxlen=30))
            dq.append((ctx.ts, cx, cy, h))
            # Trim to window
            while dq and ctx.ts - dq[0][0] > self.window:
                dq.popleft()
            if len(dq) < 2:
                continue
            t0, x0, y0, h0 = dq[0]
            dt = ctx.ts - t0
            if dt < 0.3:
                continue
            dist = math.hypot(cx - x0, cy - y0)
            avg_h = (h + h0) / 2.0
            speed_h = dist / dt / avg_h  # heights per second
            if speed_h >= self.min_speed:
                out.append(Candidate(
                    type=BehaviourType.running,
                    severity=Severity.suspicious,
                    track_ids=[t.track_id],
                    meta={"speed_hps": round(speed_h, 2)},
                ))
        # Drop history for tracks that disappeared
        for gone in set(self._hist.keys()) - alive_ids:
            self._hist.pop(gone, None)
        return out
