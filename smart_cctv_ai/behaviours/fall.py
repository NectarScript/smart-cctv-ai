from __future__ import annotations
from typing import Iterable
from .base import Behaviour, BehaviourContext, Candidate
from ..detect.pose import torso_angle_deg
from ..schema import BehaviourType, Severity


class Fall(Behaviour):
    """Fire when torso angle stays near-horizontal for N seconds.

    Pose keypoints aren't tracked (no persistent id), so this uses a simple
    per-camera "down counter" that counts frames where at least one person's
    torso is horizontal.
    """
    name = "fall"

    def __init__(self, horizontal_angle_deg: float = 35.0,
                 down_seconds: float = 1.5):
        self.max_angle = horizontal_angle_deg
        self.down_seconds = down_seconds
        self._down_since: dict[str, float | None] = {}
        self._fired: dict[str, bool] = {}

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        poses = ctx.poses or []
        anyone_down = False
        for pk in poses:
            ang = torso_angle_deg(pk)
            if ang is not None and ang <= self.max_angle:
                anyone_down = True
                break

        cam = ctx.camera_id
        if anyone_down:
            start = self._down_since.get(cam)
            if start is None:
                self._down_since[cam] = ctx.ts
                self._fired[cam] = False
            else:
                if ctx.ts - start >= self.down_seconds and not self._fired.get(cam):
                    self._fired[cam] = True
                    return [Candidate(
                        type=BehaviourType.fall,
                        severity=Severity.critical,
                        track_ids=[t.track_id for t in ctx.tracks[:1]],
                        meta={"down_seconds": round(ctx.ts - start, 2)},
                    )]
        else:
            self._down_since[cam] = None
            self._fired[cam] = False
        return []
