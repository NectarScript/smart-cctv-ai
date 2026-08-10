from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    logger.warning("mediapipe not installed — pose estimation disabled")


class PoseEstimator:
    """MediaPipe Pose: extracts 33 body keypoints from a person crop."""

    def __init__(self, model_complexity: int = 1, static_image_mode: bool = False):
        if not _MP_AVAILABLE:
            self._pose = None
            return
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        logger.info("MediaPipe Pose initialized (complexity=%d)", model_complexity)

    def estimate(self, person_crop_rgb: np.ndarray) -> Optional[np.ndarray]:
        """Run pose estimation on an RGB person crop.

        Returns (33, 3) array of [x_norm, y_norm, visibility] or None.
        """
        if self._pose is None:
            return None
        if person_crop_rgb.size == 0 or person_crop_rgb.shape[0] < 10 or person_crop_rgb.shape[1] < 10:
            return None

        result = self._pose.process(person_crop_rgb)
        if result.pose_landmarks is None:
            return None

        landmarks = result.pose_landmarks.landmark
        return np.array(
            [[lm.x, lm.y, lm.visibility] for lm in landmarks],
            dtype=np.float32,
        )

    def close(self) -> None:
        if self._pose is not None:
            self._pose.close()
            self._pose = None
