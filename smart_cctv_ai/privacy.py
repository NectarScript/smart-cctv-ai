"""Fast privacy mode: Gaussian-blur the head region of every person bbox.

No face detector — we approximate the head as the top 25% of the person
bbox, centered on the bbox's horizontal midline. Robust enough for a demo,
and runs at full FPS because it reuses the YOLO detections.
"""
from __future__ import annotations
import cv2
import numpy as np
from .detect.yolo import Track


def blur_heads(img: np.ndarray, tracks: list[Track]) -> np.ndarray:
    out = img
    h, w = img.shape[:2]
    for t in tracks:
        x1, y1, x2, y2 = (int(v) for v in t.xyxy)
        bh = y2 - y1
        bw = x2 - x1
        if bh <= 0 or bw <= 0:
            continue
        head_h = int(bh * 0.3)
        hy1 = max(y1, 0)
        hy2 = min(y1 + head_h, h)
        hx1 = max(x1, 0)
        hx2 = min(x2, w)
        if hy2 - hy1 < 4 or hx2 - hx1 < 4:
            continue
        roi = out[hy1:hy2, hx1:hx2]
        k = max((min(roi.shape[0], roi.shape[1]) // 3) | 1, 15)
        out[hy1:hy2, hx1:hx2] = cv2.GaussianBlur(roi, (k, k), 0)
    return out
