from __future__ import annotations

import logging

import supervision as sv

from src.core.config import TrackingConfig

logger = logging.getLogger(__name__)


class Tracker:
    """ByteTrack multi-object tracker via supervision library."""

    def __init__(self, config: TrackingConfig):
        self._tracker = sv.ByteTrack(
            track_activation_threshold=config.track_activation_threshold,
            lost_track_buffer=config.lost_track_buffer,
            minimum_matching_threshold=config.minimum_matching_threshold,
            frame_rate=config.frame_rate,
        )
        logger.info("ByteTrack tracker initialized")

    def update(self, detections: sv.Detections) -> sv.Detections:
        if len(detections) == 0:
            return detections
        return self._tracker.update_with_detections(detections)

    def reset(self) -> None:
        self._tracker.reset()
