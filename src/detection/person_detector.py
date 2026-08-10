from __future__ import annotations

import logging

import numpy as np
import supervision as sv
from ultralytics import YOLO

from src.core.config import DetectionConfig

logger = logging.getLogger(__name__)


class PersonDetector:
    """YOLOv8 person detection. Returns supervision.Detections filtered to person class."""

    def __init__(self, config: DetectionConfig):
        self._config = config
        logger.info("Loading YOLO model: %s (device=%s)", config.model_name, config.device)
        self._model = YOLO(config.model_name)
        self._conf = config.confidence_threshold
        self._person_class = config.person_class_id
        self._device = config.device
        self._warmup_done = False

    def warmup(self) -> None:
        if self._warmup_done:
            return
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        self._model(dummy, conf=self._conf, device=self._device, verbose=False)
        self._warmup_done = True
        logger.info("Detector warmup complete")

    def detect(self, frame: np.ndarray) -> sv.Detections:
        results = self._model(
            frame,
            conf=self._conf,
            device=self._device,
            verbose=False,
        )[0]
        detections = sv.Detections.from_ultralytics(results)

        if len(detections) == 0:
            return detections

        person_mask = detections.class_id == self._person_class
        return detections[person_mask]
