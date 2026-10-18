from __future__ import annotations
from collections import deque
from typing import Iterable
import math
import numpy as np
from .base import Behaviour, BehaviourContext, Candidate
from ..detect.pose import kp_center
from ..schema import BehaviourType, Severity


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(ix2 - ix1, 0), max(iy2 - iy1, 0)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / (area_a + area_b - inter + 1e-9)


class Fighting(Behaviour):
    """Experimental: two people overlapping + high limb motion.

    Pose motion is measured as the mean frame-to-frame displacement of all
    keypoint centroids. If no pose is available, fires on sustained overlap
    alone (lower severity).
    """
    name = "fighting"

    def __init__(self, min_overlap_iou: float = 0.1,
                 min_motion_px: float = 25.0):
        self.min_iou = min_overlap_iou
        self.min_motion = min_motion_px
        # per-camera history of pose centroid positions for motion
        self._prev_centroids: dict[str, np.ndarray | None] = {}

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        tracks = ctx.tracks
        if len(tracks) < 2:
            self._prev_centroids[ctx.camera_id] = None
            return []
        # Find overlapping pairs
        pairs = []
        for i in range(len(tracks)):
            for j in range(i + 1, len(tracks)):
                if _iou(tracks[i].xyxy, tracks[j].xyxy) >= self.min_iou:
                    pairs.append((tracks[i], tracks[j]))
        if not pairs:
            self._prev_centroids[ctx.camera_id] = None
            return []

        # Motion from pose centroids
        motion = 0.0
        motion_ok = True
        poses = ctx.poses or []
        if poses:
            cur = np.vstack([kp_center(p) for p in poses])
            prev = self._prev_centroids.get(ctx.camera_id)
            self._prev_centroids[ctx.camera_id] = cur
            if prev is None or prev.shape[0] != cur.shape[0]:
                motion_ok = False
            else:
                motion = float(np.mean(np.linalg.norm(cur - prev, axis=1)))
        else:
            motion_ok = False

        out: list[Candidate] = []
        for a, b in pairs:
            if motion_ok and motion >= self.min_motion:
                sev = Severity.critical
                meta = {"iou": round(_iou(a.xyxy, b.xyxy), 2),
                        "pose_motion_px": round(motion, 1)}
            else:
                sev = Severity.suspicious
                meta = {"iou": round(_iou(a.xyxy, b.xyxy), 2),
                        "note": "overlap only; pose motion unavailable"}
            out.append(Candidate(
                type=BehaviourType.fighting,
                severity=sev,
                track_ids=[a.track_id, b.track_id],
                meta=meta,
            ))
        return out
