from __future__ import annotations

from collections import deque
from typing import Dict, Optional, Set

import numpy as np


class KeypointBuffer:
    """Per-track sliding window of keypoint sequences."""

    def __init__(self, window_size: int = 30):
        self._buffers: Dict[int, deque] = {}
        self._window_size = window_size

    def push(self, track_id: int, keypoints: np.ndarray) -> None:
        if track_id not in self._buffers:
            self._buffers[track_id] = deque(maxlen=self._window_size)
        self._buffers[track_id].append(keypoints.copy())

    def get_sequence(self, track_id: int) -> Optional[np.ndarray]:
        buf = self._buffers.get(track_id)
        if buf is None or len(buf) == 0:
            return None
        return np.stack(list(buf))

    def is_ready(self, track_id: int, min_frames: int = 10) -> bool:
        buf = self._buffers.get(track_id)
        return buf is not None and len(buf) >= min_frames

    def remove(self, track_id: int) -> None:
        self._buffers.pop(track_id, None)

    def prune(self, active_track_ids: Set[int]) -> int:
        stale = [tid for tid in self._buffers if tid not in active_track_ids]
        for tid in stale:
            del self._buffers[tid]
        return len(stale)

    @property
    def buffer_count(self) -> int:
        return len(self._buffers)
