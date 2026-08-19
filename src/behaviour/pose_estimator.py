from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
DEFAULT_POSE_MODEL = "pose_landmarker_lite.task"

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    logger.warning("mediapipe not installed — pose estimation disabled")


class PoseEstimator:
    """MediaPipe Pose: extracts 33 body keypoints from a person crop."""

    def __init__(self, model_path: Optional[str] = None):
        if not _MP_AVAILABLE:
            self._landmarker = None
            return

        resolved = self._resolve_model(model_path or DEFAULT_POSE_MODEL)
        if resolved is None:
            logger.warning(
                "Pose model not found at models/%s — pose estimation disabled. "
                "Download with: python -c \"import urllib.request; "
                "urllib.request.urlretrieve("
                "'https://storage.googleapis.com/mediapipe-models/"
                "pose_landmarker/pose_landmarker_lite/float16/latest/"
                "pose_landmarker_lite.task', 'models/pose_landmarker_lite.task')\"",
                DEFAULT_POSE_MODEL,
            )
            self._landmarker = None
            return

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved)),
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        logger.info("MediaPipe PoseLandmarker initialized (%s)", resolved.name)

    @staticmethod
    def _resolve_model(model_name: str) -> Optional[Path]:
        path = Path(model_name)
        if path.is_absolute() and path.exists():
            return path
        local = MODELS_DIR / path.name
        if local.exists():
            return local
        if path.exists():
            return path
        return None

    def estimate(self, person_crop_rgb: np.ndarray) -> Optional[np.ndarray]:
        """Run pose estimation on an RGB person crop.

        Returns (33, 3) array of [x_norm, y_norm, visibility] or None.
        """
        if self._landmarker is None:
            return None
        if person_crop_rgb.size == 0 or person_crop_rgb.shape[0] < 10 or person_crop_rgb.shape[1] < 10:
            return None

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=person_crop_rgb)
        result = self._landmarker.detect(mp_image)

        if not result.pose_landmarks:
            return None

        landmarks = result.pose_landmarks[0]
        return np.array(
            [[lm.x, lm.y, lm.visibility] for lm in landmarks],
            dtype=np.float32,
        )

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
