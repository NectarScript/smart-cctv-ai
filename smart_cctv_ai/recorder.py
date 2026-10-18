from __future__ import annotations
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
import cv2
import numpy as np
from loguru import logger


@dataclass
class _PendingClip:
    camera_id: str
    event_type: str
    out_path: Path
    pre_frames: list[np.ndarray]
    frames_needed_after: int
    frames: list[np.ndarray]
    size: tuple[int, int]
    on_done: Optional[Callable[[Path], None]]


class ClipRecorder:
    """Ring buffer of recent frames per camera; dumps pre+post seconds to mp4.

    Uses cv2.VideoWriter with the mp4v fourcc (works on Windows out of the box,
    no ffmpeg binary needed for writing — reading via ultralytics still uses it).
    """

    def __init__(self, pre_seconds: float, post_seconds: float,
                 fps: int, out_dir: Path | str = "data/clips"):
        self.pre = pre_seconds
        self.post = post_seconds
        self.fps = max(fps, 1)
        self.pre_frames = int(self.pre * self.fps)
        self.post_frames = int(self.post * self.fps)
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._buffers: dict[str, deque[np.ndarray]] = {}
        self._pending: list[_PendingClip] = []

    def push(self, camera_id: str, frame: np.ndarray) -> None:
        with self._lock:
            buf = self._buffers.setdefault(
                camera_id, deque(maxlen=max(self.pre_frames, 1)))
            buf.append(frame.copy())
            # Feed any pending clips waiting for post-event frames
            still: list[_PendingClip] = []
            for p in self._pending:
                if p.camera_id != camera_id:
                    still.append(p)
                    continue
                p.frames.append(frame.copy())
                if len(p.frames) >= p.frames_needed_after:
                    self._finish(p)
                else:
                    still.append(p)
            self._pending = still

    def trigger(self, camera_id: str, event_type: str,
                on_done: Optional[Callable[[Path], None]] = None) -> Path:
        """Schedule a clip write for this camera. Returns the eventual file path."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")[:-3]
        name = f"{camera_id}_{event_type}_{ts}.mp4"
        out = self.out_dir / name
        with self._lock:
            buf = self._buffers.get(camera_id)
            pre = list(buf) if buf else []
            size = (pre[-1].shape[1], pre[-1].shape[0]) if pre else (640, 360)
            p = _PendingClip(
                camera_id=camera_id, event_type=event_type, out_path=out,
                pre_frames=pre, frames_needed_after=self.post_frames,
                frames=[], size=size, on_done=on_done,
            )
            self._pending.append(p)
        return out

    def _finish(self, p: _PendingClip) -> None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        w = cv2.VideoWriter(p.out_path.as_posix(), fourcc, self.fps, p.size)
        if not w.isOpened():
            logger.error(f"VideoWriter failed to open: {p.out_path}")
            return
        try:
            for f in p.pre_frames:
                w.write(f if f.shape[:2][::-1] == p.size else cv2.resize(f, p.size))
            for f in p.frames:
                w.write(f if f.shape[:2][::-1] == p.size else cv2.resize(f, p.size))
        finally:
            w.release()
        logger.info(f"clip saved: {p.out_path}  ({len(p.pre_frames) + len(p.frames)} frames)")
        if p.on_done:
            try:
                p.on_done(p.out_path)
            except Exception as e:
                logger.error(f"clip on_done failed: {e}")
