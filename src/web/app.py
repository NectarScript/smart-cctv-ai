from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from typing import Dict, List, Optional

import cv2
import numpy as np
from flask import Flask, Response, render_template, jsonify

from src.core.config import AppConfig, CameraConfig, load_config
from src.core.constants import BehaviourLabel, SourceType
from src.core.logger import setup_logging
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

logger = logging.getLogger(__name__)


class WebPipeline:
    """Pipeline adapted for web streaming — no cv2 windows."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._camera_mgr = CameraManager(config.cameras, config.frame_queue_maxsize)
        self._detector = PersonDetector(config.detection)
        self._trackers: Dict[str, Tracker] = {}
        self._track_store = TrackStore()
        self._pose_estimator = PoseEstimator()
        self._kp_buffer = KeypointBuffer(config.behaviour.keypoint_window_size)
        self._classifier = BehaviourClassifier(config.behaviour)
        self._renderer = Renderer()

        self._timer = PerfTimer()
        self._timer_detect = PerfTimer()
        self._timer_track = PerfTimer()
        self._timer_pose = PerfTimer()

        self._running = False
        self._frame_count = 0

        self._latest_frames: Dict[str, bytes] = {}
        self._frame_locks: Dict[str, threading.Lock] = {}
        self._event_log: deque = deque(maxlen=100)
        self._stats: dict = {}
        self._event_counts: Dict[str, int] = {}
        self._active_alerts: Dict[int, BehaviourEvent] = {}

    def start(self):
        self._detector.warmup()
        started = self._camera_mgr.start_all()
        for cam_id in started:
            self._trackers[cam_id] = Tracker(self._config.tracking)
            self._frame_locks[cam_id] = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("WebPipeline started with %d cameras", len(started))

    def _loop(self):
        while self._running:
            active = self._camera_mgr.active_cameras
            if not active:
                time.sleep(0.1)
                continue

            for camera_id in active:
                packet = self._camera_mgr.get_frame(camera_id, timeout=0.01)
                if packet is None:
                    continue
                self._process_and_encode(packet)

    def _process_and_encode(self, packet: FramePacket):
        with self._timer:
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
                    active_tracks = self._track_store.get_active_tracks()
                    event = self._classifier.classify(
                        tid, history, kp_seq, active_tracks, packet.timestamp,
                    )
                    events.append(event)

                    if event.label != BehaviourLabel.NORMAL:
                        self._active_alerts[tid] = event
                        etype = event.event_type.value
                        self._event_counts[etype] = self._event_counts.get(etype, 0) + 1
                    elif tid in self._active_alerts:
                        del self._active_alerts[tid]

            self._track_store.prune_stale(max_age=10.0)
            active_ids = set()
            if tracked.tracker_id is not None:
                active_ids = {int(t) for t in tracked.tracker_id}
            self._kp_buffer.prune(active_ids)

        annotated = self._renderer.draw(
            packet.frame, tracked, events, kp_map,
            fps=self._timer.fps,
        )

        _, jpeg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        jpeg_bytes = jpeg.tobytes()

        cam_id = packet.camera_id
        if cam_id not in self._frame_locks:
            self._frame_locks[cam_id] = threading.Lock()
        with self._frame_locks[cam_id]:
            self._latest_frames[cam_id] = jpeg_bytes

        for e in events:
            if e.label != BehaviourLabel.NORMAL:
                self._event_log.appendleft({
                    "time": time.strftime("%H:%M:%S"),
                    "track_id": e.track_id,
                    "camera": cam_id,
                    "event": e.event_type.value,
                    "severity": e.label.value,
                    "confidence": f"{e.confidence:.0%}",
                })

        track_n = len(tracked) if tracked.tracker_id is not None else 0
        self._stats = {
            "fps": round(self._timer.fps, 1),
            "tracks": track_n,
            "alerts": len(self._active_alerts),
            "detect_ms": round(self._timer_detect.avg_ms, 1),
            "track_ms": round(self._timer_track.avg_ms, 1),
            "pose_ms": round(self._timer_pose.avg_ms, 1),
            "event_counts": dict(self._event_counts),
        }

    def get_frame(self, camera_id: str) -> Optional[bytes]:
        lock = self._frame_locks.get(camera_id)
        if lock is None:
            return None
        with lock:
            return self._latest_frames.get(camera_id)

    @property
    def camera_ids(self) -> list:
        return list(self._frame_locks.keys())

    @property
    def stats(self) -> dict:
        return self._stats

    @property
    def event_log(self) -> list:
        return list(self._event_log)

    def stop(self):
        self._running = False
        self._camera_mgr.stop_all()
        self._pose_estimator.close()


pipeline: Optional[WebPipeline] = None


def create_app(config: AppConfig) -> Flask:
    global pipeline

    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = "smartcctv"

    pipeline = WebPipeline(config)
    pipeline.start()

    @app.route("/")
    def index():
        return render_template("dashboard.html", cameras=pipeline.camera_ids)

    @app.route("/video_feed/<camera_id>")
    def video_feed(camera_id):
        def generate():
            while True:
                frame = pipeline.get_frame(camera_id)
                if frame is not None:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                else:
                    time.sleep(0.03)
        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/stats")
    def api_stats():
        return jsonify(pipeline.stats)

    @app.route("/api/events")
    def api_events():
        return jsonify(pipeline.event_log[:50])

    @app.teardown_appcontext
    def shutdown(exc):
        pass

    return app
