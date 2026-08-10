from __future__ import annotations

import logging
import queue
from typing import Dict, List, Optional

from src.core.config import CameraConfig
from src.core.types import FramePacket
from src.ingestion.camera_source import CameraSource

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages multiple CameraSource instances and their frame queues."""

    def __init__(self, configs: List[CameraConfig], queue_maxsize: int = 64):
        self._configs = {c.source_id: c for c in configs}
        self._queue_maxsize = queue_maxsize
        self._sources: Dict[str, CameraSource] = {}
        self._queues: Dict[str, queue.Queue] = {}
        self._robin_index = 0

    def start_all(self) -> List[str]:
        started = []
        for cam_id, config in self._configs.items():
            if self._start_camera(config):
                started.append(cam_id)
        logger.info("Started %d/%d cameras", len(started), len(self._configs))
        return started

    def _start_camera(self, config: CameraConfig) -> bool:
        q = queue.Queue(maxsize=self._queue_maxsize)
        source = CameraSource(config, q)
        if source.start():
            self._sources[config.source_id] = source
            self._queues[config.source_id] = q
            return True
        return False

    def stop_all(self) -> None:
        for source in self._sources.values():
            source.stop()
        self._sources.clear()
        self._queues.clear()

    def get_frame(self, camera_id: str, timeout: float = 0.1) -> Optional[FramePacket]:
        q = self._queues.get(camera_id)
        if q is None:
            return None
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_any_frame(self) -> Optional[FramePacket]:
        cameras = self.active_cameras
        if not cameras:
            return None
        for _ in range(len(cameras)):
            cam_id = cameras[self._robin_index % len(cameras)]
            self._robin_index += 1
            packet = self.get_frame(cam_id, timeout=0.005)
            if packet is not None:
                return packet
        return None

    def add_camera(self, config: CameraConfig) -> bool:
        if config.source_id in self._sources:
            logger.warning("Camera %s already exists", config.source_id)
            return False
        self._configs[config.source_id] = config
        return self._start_camera(config)

    def remove_camera(self, camera_id: str) -> None:
        source = self._sources.pop(camera_id, None)
        if source:
            source.stop()
        self._queues.pop(camera_id, None)
        self._configs.pop(camera_id, None)

    @property
    def active_cameras(self) -> List[str]:
        return [cid for cid, s in self._sources.items() if s.is_alive]

    @property
    def all_cameras(self) -> List[str]:
        return list(self._sources.keys())

    def get_source(self, camera_id: str) -> Optional[CameraSource]:
        return self._sources.get(camera_id)
