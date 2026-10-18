from __future__ import annotations
import threading
import time
from dataclasses import dataclass
from typing import Optional
import numpy as np
from loguru import logger
from .source import open_source


@dataclass
class Frame:
    camera_id: str
    frame: np.ndarray
    ts: float   # monotonic seconds since capture


class CameraWorker(threading.Thread):
    """Threaded capture with auto-reconnect. Latest frame only (drop stale)."""

    def __init__(self, camera_id: str, source: str, fps: int = 15):
        super().__init__(daemon=True, name=f"cam-{camera_id}")
        self.camera_id = camera_id
        self.source = source
        self.target_dt = 1.0 / max(fps, 1)
        self._lock = threading.Lock()
        self._latest: Optional[Frame] = None
        self._stop = threading.Event()
        self.alive = False

    def read(self) -> Optional[Frame]:
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                cap = open_source(self.source)
                logger.info(f"[{self.camera_id}] opened: {self.source}")
                self.alive = True
                backoff = 1.0
                last = 0.0
                while not self._stop.is_set():
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        logger.warning(f"[{self.camera_id}] read failed; reopening")
                        break
                    now = time.monotonic()
                    if now - last < self.target_dt:
                        continue
                    last = now
                    with self._lock:
                        self._latest = Frame(self.camera_id, frame, now)
                cap.release()
            except Exception as e:
                logger.error(f"[{self.camera_id}] {e}")
            self.alive = False
            if self._stop.is_set():
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


class CameraManager:
    def __init__(self):
        self._workers: dict[str, CameraWorker] = {}

    def add(self, camera_id: str, source: str, fps: int = 15) -> CameraWorker:
        w = CameraWorker(camera_id, source, fps)
        self._workers[camera_id] = w
        w.start()
        return w

    def get(self, camera_id: str) -> Optional[CameraWorker]:
        return self._workers.get(camera_id)

    def ids(self) -> list[str]:
        return list(self._workers.keys())

    def status(self) -> dict[str, bool]:
        return {cid: w.alive for cid, w in self._workers.items()}

    def stop_all(self) -> None:
        for w in self._workers.values():
            w.stop()
