from __future__ import annotations
from pathlib import Path
import cv2


def open_source(src: str) -> cv2.VideoCapture:
    """Accept webcam index ('0'), file path, or RTSP/HTTP URL.

    Raises RuntimeError with an actionable message if the source cannot open.
    """
    s = src.strip()
    cap: cv2.VideoCapture
    if s.isdigit():
        cap = cv2.VideoCapture(int(s), cv2.CAP_DSHOW)
    elif s.startswith(("rtsp://", "http://", "https://")):
        cap = cv2.VideoCapture(s, cv2.CAP_FFMPEG)
    else:
        p = Path(s)
        if not p.exists():
            raise RuntimeError(
                f"camera source not found: {p.resolve()} "
                f"(drop a sample clip here, or edit config.yaml)"
            )
        cap = cv2.VideoCapture(p.as_posix())
    if not cap.isOpened():
        raise RuntimeError(f"could not open camera source: {src}")
    return cap
