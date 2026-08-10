from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import supervision as sv


@dataclass
class TrackHistory:
    track_id: int
    camera_id: str
    centroids: deque = field(default_factory=lambda: deque(maxlen=300))
    bboxes: deque = field(default_factory=lambda: deque(maxlen=300))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=300))
    first_seen: float = 0.0
    last_seen: float = 0.0

    def centroid_at(self, index: int) -> Tuple[float, float]:
        return self.centroids[index]

    @property
    def current_centroid(self) -> Optional[Tuple[float, float]]:
        return self.centroids[-1] if self.centroids else None

    @property
    def current_bbox(self) -> Optional[np.ndarray]:
        return self.bboxes[-1] if self.bboxes else None

    @property
    def duration(self) -> float:
        return self.last_seen - self.first_seen


class TrackStore:
    """Stores per-track spatial/temporal history for behaviour analysis."""

    def __init__(self, history_maxlen: int = 300):
        self._tracks: Dict[int, TrackHistory] = {}
        self._maxlen = history_maxlen

    def update(
        self,
        tracked: sv.Detections,
        camera_id: str,
        timestamp: float,
    ) -> None:
        if tracked.tracker_id is None:
            return
        for i, tid in enumerate(tracked.tracker_id):
            tid = int(tid)
            bbox = tracked.xyxy[i]
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2

            if tid not in self._tracks:
                self._tracks[tid] = TrackHistory(
                    track_id=tid,
                    camera_id=camera_id,
                    centroids=deque(maxlen=self._maxlen),
                    bboxes=deque(maxlen=self._maxlen),
                    timestamps=deque(maxlen=self._maxlen),
                    first_seen=timestamp,
                )

            track = self._tracks[tid]
            track.centroids.append((cx, cy))
            track.bboxes.append(bbox.copy())
            track.timestamps.append(timestamp)
            track.last_seen = timestamp

    def get(self, track_id: int) -> Optional[TrackHistory]:
        return self._tracks.get(track_id)

    def get_active_tracks(self, stale_threshold: float = 2.0) -> List[TrackHistory]:
        now = time.time()
        return [
            t for t in self._tracks.values()
            if (now - t.last_seen) < stale_threshold
        ]

    def prune_stale(self, max_age: float = 10.0) -> int:
        now = time.time()
        stale = [tid for tid, t in self._tracks.items() if (now - t.last_seen) > max_age]
        for tid in stale:
            del self._tracks[tid]
        return len(stale)

    def get_velocity(self, track_id: int, window: int = 5) -> Optional[float]:
        track = self._tracks.get(track_id)
        if track is None or len(track.centroids) < 2:
            return None
        pts = list(track.centroids)[-window:]
        if len(pts) < 2:
            return None
        dists = []
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dy = pts[i][1] - pts[i - 1][1]
            dists.append(np.sqrt(dx * dx + dy * dy))
        return float(np.mean(dists))

    def get_displacement(self, track_id: int) -> Optional[float]:
        track = self._tracks.get(track_id)
        if track is None or len(track.centroids) < 2:
            return None
        first = track.centroids[0]
        last = track.centroids[-1]
        dx = last[0] - first[0]
        dy = last[1] - first[1]
        return float(np.sqrt(dx * dx + dy * dy))

    @property
    def track_count(self) -> int:
        return len(self._tracks)
