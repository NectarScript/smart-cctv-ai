from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional

import cv2
import numpy as np

from src.core.config import CameraConfig
from src.core.constants import SourceType
from src.core.types import FramePacket

logger = logging.getLogger(__name__)


class CameraSource:
    """Threaded camera capture. Pushes FramePackets to a shared queue."""

    def __init__(self, config: CameraConfig, frame_queue: queue.Queue):
        self._config = config
        self._queue = frame_queue
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0
        self._fps_counter_start = 0.0
        self._fps_frame_count = 0
        self._measured_fps = 0.0

    def start(self) -> bool:
        source = self._config.source
        if self._config.source_type == SourceType.RTSP:
            self._cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        else:
            self._cap = cv2.VideoCapture(source)

        if not self._cap.isOpened():
            logger.error("Cannot open camera source: %s", source)
            return False

        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        w, h = self._config.resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

        self._running.set()
        self._fps_counter_start = time.time()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"cam-{self._config.source_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Started camera: %s (source=%s)", self._config.source_id, source)
        return True

    def stop(self) -> None:
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("Stopped camera: %s", self._config.source_id)

    def _capture_loop(self) -> None:
        interval = 1.0 / self._config.fps_target if self._config.fps_target > 0 else 0
        while self._running.is_set():
            loop_start = time.time()
            ret, frame = self._cap.read()
            if not ret:
                if self._config.source_type == SourceType.FILE:
                    logger.info("End of video file: %s", self._config.source_id)
                    self._running.clear()
                    break
                logger.warning("Frame read failed: %s, retrying...", self._config.source_id)
                time.sleep(0.1)
                continue

            self._frame_count += 1
            packet = FramePacket(
                camera_id=self._config.source_id,
                frame=frame,
                timestamp=time.time(),
                frame_number=self._frame_count,
            )

            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put(packet)

            self._fps_frame_count += 1
            elapsed = time.time() - self._fps_counter_start
            if elapsed >= 1.0:
                self._measured_fps = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._fps_counter_start = time.time()

            sleep_time = interval - (time.time() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def fps_actual(self) -> float:
        return self._measured_fps

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def source_fps(self) -> float:
        if self._cap:
            return self._cap.get(cv2.CAP_PROP_FPS) or 0.0
        return 0.0
