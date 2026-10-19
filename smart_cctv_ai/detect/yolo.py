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
                 person_class: int = 0):
        from ultralytics import YOLO  # local import
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.tracker = tracker
        self.person_class = person_class
        self.device = _resolve_device(device)

        weights_path = _resolve_weights(model)
        logger.info(f"loading YOLO weights: {weights_path} (device={self.device})")
        self.model = YOLO(str(weights_path))

    def track(self, frame: np.ndarray) -> list[Track]:
        results = self.model.track(
            source=frame,
            persist=True,
            tracker=self.tracker,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            classes=[self.person_class],
            verbose=False,
        )
        tracks: list[Track] = []
        if not results:
            return tracks
        r = results[0]
        if r.boxes is None or r.boxes.id is None:
            return tracks
        xyxy = r.boxes.xyxy.cpu().numpy()
        ids = r.boxes.id.cpu().numpy().astype(int)
        confs = r.boxes.conf.cpu().numpy()
        clss = r.boxes.cls.cpu().numpy().astype(int)
        for i in range(len(ids)):
            x1, y1, x2, y2 = xyxy[i].tolist()
            tracks.append(Track(int(ids[i]), (x1, y1, x2, y2),
                                float(confs[i]), int(clss[i])))
        return tracks


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
