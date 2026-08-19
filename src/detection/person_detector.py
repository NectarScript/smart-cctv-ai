from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import supervision as sv
from ultralytics import YOLO

from src.core.config import DetectionConfig

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


class PersonDetector:
    """YOLOv8 person detection. Returns supervision.Detections filtered to person class."""

    def __init__(self, config: DetectionConfig):
        self._config = config
        model_path = self._resolve_model_path(config.model_name)
        logger.info("Loading YOLO model: %s (device=%s)", model_path, config.device)
        self._model = YOLO(str(model_path))
        self._conf = config.confidence_threshold
        self._person_class = config.person_class_id
        self._device = config.device
        self._warmup_done = False

    @staticmethod
    def _resolve_model_path(model_name: str) -> Path:
        path = Path(model_name)
        if path.is_absolute() and path.exists():
            return path
        local = MODELS_DIR / path.name
        if local.exists():
            return local
        return path

    def warmup(self) -> None:
        if self._warmup_done:
            return
        sz = self._config.input_size
        dummy = np.zeros((sz, sz, 3), dtype=np.uint8)
        self._model(dummy, conf=self._conf, device=self._device,
                    imgsz=sz, verbose=False)
        self._warmup_done = True
        logger.info("Detector warmup complete")

    def detect(self, frame: np.ndarray) -> sv.Detections:
        results = self._model(
            frame,
            conf=self._conf,
            device=self._device,
            imgsz=self._config.input_size,
            verbose=False,
        )[0]
        detections = sv.Detections.from_ultralytics(results)

        if len(detections) == 0:
            return detections

        person_mask = detections.class_id == self._person_class
        return detections[person_mask]
