from __future__ import annotations

import numpy as np
import cv2


def crop_bbox(
    frame: np.ndarray,
    bbox: np.ndarray,
    padding: float = 0.1,
) -> np.ndarray:
    """Extract a person crop from frame with optional padding."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox.astype(int)
    bw, bh = x2 - x1, y2 - y1
    pad_x = int(bw * padding)
    pad_y = int(bh * padding)

    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)

    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return np.zeros((64, 64, 3), dtype=np.uint8)
    return crop


def preprocess_for_pose(crop: np.ndarray) -> np.ndarray:
    """Convert BGR crop to RGB for MediaPipe."""
    return cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)


def letterbox(
    frame: np.ndarray,
    target_size: int = 640,
) -> np.ndarray:
    """Resize with letterboxing (maintain aspect ratio, pad with gray)."""
    h, w = frame.shape[:2]
    scale = target_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
    top = (target_size - new_h) // 2
    left = (target_size - new_w) // 2
    canvas[top:top + new_h, left:left + new_w] = resized
    return canvas
