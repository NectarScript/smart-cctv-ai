from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np
import supervision as sv

from src.core.config import AppConfig
from src.core.constants import BehaviourLabel
from src.core.timer import PerfTimer
from src.core.types import BehaviourEvent, FramePacket
from src.detection.person_detector import PersonDetector
from src.detection.tracker import Tracker
from src.detection.track_store import TrackStore
from src.behaviour.pose_estimator import PoseEstimator
from src.behaviour.keypoint_buffer import KeypointBuffer
from src.behaviour.classifier import BehaviourClassifier
from src.ingestion.camera_manager import CameraManager
from src.ingestion.preprocessor import crop_bbox, preprocess_for_pose
from src.visualization.renderer import Renderer
from src.visualization.display import Display

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates M1 → M2 → M3 as a single processing loop."""

    def __init__(
        self,
        config: AppConfig,
        on_events: Optional[Callable[[List[BehaviourEvent]], None]] = None,
    ):
        self._config = config
        self._on_events = on_events

        self._camera_mgr = CameraManager(config.cameras, config.frame_queue_maxsize)
        self._detector = PersonDetector(config.detection)
        self._trackers: Dict[str, Tracker] = {}
        self._track_store = TrackStore()
        self._pose_estimator = PoseEstimator()
        self._kp_buffer = KeypointBuffer(config.behaviour.keypoint_window_size)
        self._classifier = BehaviourClassifier(config.behaviour)
        self._renderer = Renderer()
        self._display = Display()

        self._timer_pipeline = PerfTimer()
        self._timer_detect = PerfTimer()
        self._timer_track = PerfTimer()
        self._timer_pose = PerfTimer()

        self._running = False
        self._frame_count = 0
        self._event_counts: Dict[str, int] = {}

    def start(self) -> None:
        logger.info("Starting pipeline...")
        self._detector.warmup()
        started = self._camera_mgr.start_all()
        for cam_id in started:
            self._trackers[cam_id] = Tracker(self._config.tracking)
        self._running = True
        logger.info("Pipeline started with %d cameras", len(started))

    def run(self) -> None:
        self.start()
        try:
            while self._running:
                active = self._camera_mgr.active_cameras
                if not active:
                    logger.info("No active cameras, stopping")
                    break

                for camera_id in active:
                    packet = self._camera_mgr.get_frame(camera_id, timeout=0.01)
                    if packet is None:
                        continue

                    events, tracked, kp_map = self._process_frame(packet)

                    annotated = self._renderer.draw(
                        packet.frame, tracked, events, kp_map,
                        fps=self._timer_pipeline.fps,
                    )
                    self._display.show(camera_id, annotated)

                    if self._on_events and events:
                        non_normal = [e for e in events if e.label != BehaviourLabel.NORMAL]
                        if non_normal:
                            self._on_events(non_normal)

                if self._display.check_quit():
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            self.stop()

    def _process_frame(
        self, packet: FramePacket,
    ) -> tuple[List[BehaviourEvent], sv.Detections, Dict[int, np.ndarray]]:
        with self._timer_pipeline:
            with self._timer_detect:
                detections = self._detector.detect(packet.frame)

            tracker = self._trackers.get(packet.camera_id)
            if tracker is None:
                tracker = Tracker(self._config.tracking)
                self._trackers[packet.camera_id] = tracker

            with self._timer_track:
                tracked = tracker.update(detections)

            self._track_store.update(tracked, packet.camera_id, packet.timestamp)

            events: List[BehaviourEvent] = []
            kp_map: Dict[int, np.ndarray] = {}

            if tracked.tracker_id is not None and len(tracked.tracker_id) > 0:
                self._frame_count += 1
                do_pose = (self._config.pose_every_n_frames <= 1 or
                           self._frame_count % self._config.pose_every_n_frames == 0)

                for i, tid in enumerate(tracked.tracker_id):
                    tid = int(tid)
                    bbox = tracked.xyxy[i]

                    if do_pose:
                        crop = crop_bbox(packet.frame, bbox, padding=0.1)
                        crop_rgb = preprocess_for_pose(crop)
                        with self._timer_pose:
                            kp = self._pose_estimator.estimate(crop_rgb)
                        if kp is not None:
                            self._kp_buffer.push(tid, kp)
                            kp_map[tid] = kp

                    history = self._track_store.get(tid)
                    if history is None:
                        continue

                    kp_seq = self._kp_buffer.get_sequence(tid)
                    active = self._track_store.get_active_tracks()

                    event = self._classifier.classify(
                        tid, history, kp_seq, active, packet.timestamp,
                    )
                    events.append(event)

                    etype = event.event_type.value
                    if event.label != BehaviourLabel.NORMAL:
                        self._event_counts[etype] = self._event_counts.get(etype, 0) + 1

            self._track_store.prune_stale(max_age=10.0)
            active_ids = set()
            if tracked.tracker_id is not None:
                active_ids = {int(t) for t in tracked.tracker_id}
            self._kp_buffer.prune(active_ids)

        return events, tracked, kp_map

    def process_single_frame(
        self, frame: np.ndarray, camera_id: str = "default",
    ) -> tuple[List[BehaviourEvent], np.ndarray]:
        """Process one frame without camera manager. For scripting/testing."""
        packet = FramePacket(
            camera_id=camera_id,
            frame=frame,
            timestamp=time.time(),
            frame_number=self._frame_count,
        )
        events, tracked, kp_map = self._process_frame(packet)
        annotated = self._renderer.draw(
            frame, tracked, events, kp_map,
            fps=self._timer_pipeline.fps,
        )
        return events, annotated

    def stop(self) -> None:
        self._running = False
        self._camera_mgr.stop_all()
        self._pose_estimator.close()
        self._display.destroy_all()
        logger.info("Pipeline stopped")
        self._log_summary()

    def _log_summary(self) -> None:
        logger.info("=== Pipeline Summary ===")
        logger.info("Avg pipeline FPS: %.1f", self._timer_pipeline.fps)
        logger.info("Avg detect: %.1fms | track: %.1fms | pose: %.1fms",
                     self._timer_detect.avg_ms,
                     self._timer_track.avg_ms,
                     self._timer_pose.avg_ms)
        logger.info("Event counts: %s", self._event_counts)

    @property
    def stats(self) -> dict:
        return {
            "pipeline_fps": round(self._timer_pipeline.fps, 1),
            "detect_ms": round(self._timer_detect.avg_ms, 1),
            "track_ms": round(self._timer_track.avg_ms, 1),
            "pose_ms": round(self._timer_pose.avg_ms, 1),
            "active_tracks": len(self._track_store.get_active_tracks()),
            "event_counts": dict(self._event_counts),
        }
