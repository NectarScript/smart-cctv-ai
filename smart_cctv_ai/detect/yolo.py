from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import numpy as np
from loguru import logger


@dataclass
class Track:
    track_id: int
    xyxy: tuple[float, float, float, float]
    conf: float
    cls: int


class YoloTracker:
    """Thin wrapper around ultralytics YOLO + ByteTrack.

    Lazy-imports ultralytics so the whole app doesn't fail to import when
    ultralytics isn't installed (useful on dev PC with no GPU).
    """

    def __init__(self, model: str, device: str = "auto",
                 conf: float = 0.35, iou: float = 0.5,
                 imgsz: int = 640, tracker: str = "bytetrack.yaml",
                 person_class: int = 0, extra_classes: list[int] | None = None):
        from ultralytics import YOLO  # local import
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.tracker = tracker
        self.person_class = person_class
        self.classes = [person_class] + list(extra_classes or [])
        self.device = _resolve_device(device)

        weights_path = _resolve_weights(model)
        logger.info(f"loading YOLO weights: {weights_path} (device={self.device})")
        self.model = YOLO(str(weights_path))

    def track(self, frame: np.ndarray) -> tuple[list[Track], list[Track]]:
        """Returns (person_tracks, object_tracks). Object tracks only exist
        when extra_classes was non-empty."""
        results = self.model.track(
            source=frame,
            persist=True,
            tracker=self.tracker,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            classes=self.classes,
            verbose=False,
        )
        persons: list[Track] = []
        objects: list[Track] = []
        if not results:
            return persons, objects
        r = results[0]
        if r.boxes is None or r.boxes.id is None:
            return persons, objects
        xyxy = r.boxes.xyxy.cpu().numpy()
        ids = r.boxes.id.cpu().numpy().astype(int)
        confs = r.boxes.conf.cpu().numpy()
        clss = r.boxes.cls.cpu().numpy().astype(int)
        for i in range(len(ids)):
            x1, y1, x2, y2 = xyxy[i].tolist()
            tr = Track(int(ids[i]), (x1, y1, x2, y2),
                       float(confs[i]), int(clss[i]))
            if tr.cls == self.person_class:
                persons.append(tr)
            else:
                objects.append(tr)
        return persons, objects


def _resolve_weights(name: str) -> Path:
    """Prefer ./models/<name>; else let ultralytics auto-download by name."""
    local = Path("models") / name
    if local.exists():
        return local
    return Path(name)


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"
