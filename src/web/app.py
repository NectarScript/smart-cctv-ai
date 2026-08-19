from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from typing import Dict, List, Optional

import cv2
import numpy as np
from flask import Flask, Response, render_template, jsonify, request, redirect, url_for

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


class VideoProcessor:
    """Processes uploaded video files through the pipeline."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._detector = None
        self._jobs: Dict[str, dict] = {}

    def _ensure_detector(self):
        if self._detector is None:
            self._detector = PersonDetector(self._config.detection)
            self._detector.warmup()
            self._pose_estimator = PoseEstimator()
            self._renderer = Renderer()

    def start_job(self, video_path: str) -> str:
        job_id = str(uuid.uuid4())[:8]
        self._jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "total_frames": 0,
            "events": [],
            "output_path": None,
            "fps": 0,
            "error": None,
        }
        thread = threading.Thread(target=self._process, args=(job_id, video_path), daemon=True)
        thread.start()
        return job_id

    def _process(self, job_id: str, video_path: str):
        try:
            self._ensure_detector()
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self._jobs[job_id]["status"] = "error"
                self._jobs[job_id]["error"] = "Cannot open video file"
                return

            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._jobs[job_id]["total_frames"] = total
            self._jobs[job_id]["fps"] = fps

            out_dir = os.path.join(os.path.dirname(video_path), "output")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{job_id}_annotated.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

            tracker = Tracker(self._config.tracking)
            track_store = TrackStore()
            kp_buffer = KeypointBuffer(self._config.behaviour.keypoint_window_size)
            classifier = BehaviourClassifier(self._config.behaviour)
            frame_count = 0
            all_events = []

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                timestamp = frame_count / fps

                detections = self._detector.detect(frame)
                tracked = tracker.update(detections)
                track_store.update(tracked, "video", timestamp)

                events = []
                kp_map = {}

                if tracked.tracker_id is not None and len(tracked.tracker_id) > 0:
                    do_pose = (frame_count % self._config.pose_every_n_frames == 0)

                    for i, tid in enumerate(tracked.tracker_id):
                        tid = int(tid)
                        bbox = tracked.xyxy[i]

                        if do_pose:
                            from src.ingestion.preprocessor import crop_bbox, preprocess_for_pose
                            crop = crop_bbox(frame, bbox, padding=0.1)
                            crop_rgb = preprocess_for_pose(crop)
                            kp = self._pose_estimator.estimate(crop_rgb)
                            if kp is not None:
                                kp_buffer.push(tid, kp)
                                kp_map[tid] = kp

                        history = track_store.get(tid)
                        if history is None:
                            continue

                        kp_seq = kp_buffer.get_sequence(tid)
                        active = track_store.get_active_tracks()
                        event = classifier.classify(tid, history, kp_seq, active, timestamp)
                        events.append(event)

                        if event.label != BehaviourLabel.NORMAL:
                            all_events.append({
                                "frame": frame_count,
                                "time": f"{int(timestamp//60):02d}:{int(timestamp%60):02d}",
                                "track_id": event.track_id,
                                "event": event.event_type.value,
                                "severity": event.label.value,
                                "confidence": f"{event.confidence:.0%}",
                            })

                track_store.prune_stale(max_age=10.0)
                active_ids = set()
                if tracked.tracker_id is not None:
                    active_ids = {int(t) for t in tracked.tracker_id}
                kp_buffer.prune(active_ids)

                annotated = self._renderer.draw(frame, tracked, events, kp_map, fps=fps)
                writer.write(annotated)

                self._jobs[job_id]["progress"] = frame_count

            cap.release()
            writer.release()

            seen = set()
            deduped = []
            for e in all_events:
                key = f"{e['track_id']}_{e['event']}_{e['time']}"
                if key not in seen:
                    seen.add(key)
                    deduped.append(e)

            self._jobs[job_id]["status"] = "done"
            self._jobs[job_id]["events"] = deduped[-100:]
            self._jobs[job_id]["output_path"] = out_path

        except Exception as ex:
            logger.exception("Video processing error")
            self._jobs[job_id]["status"] = "error"
            self._jobs[job_id]["error"] = str(ex)

    def get_job(self, job_id: str) -> Optional[dict]:
        return self._jobs.get(job_id)


pipeline: Optional[WebPipeline] = None
video_processor: Optional[VideoProcessor] = None


def create_app(config: AppConfig) -> Flask:
    global pipeline, video_processor

    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = "smartcctv"
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

    upload_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    pipeline = WebPipeline(config)
    pipeline.start()
    video_processor = VideoProcessor(config)

    @app.route("/")
    def index():
        return render_template("dashboard.html", cameras=pipeline.camera_ids)

    @app.route("/upload")
    def upload_page():
        return render_template("upload.html")

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

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        if "video" not in request.files:
            return jsonify({"error": "No video file"}), 400
        f = request.files["video"]
        if not f.filename:
            return jsonify({"error": "Empty filename"}), 400

        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".mp4", ".avi", ".mkv", ".mov", ".webm"):
            return jsonify({"error": "Unsupported format"}), 400

        save_name = f"{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(upload_dir, save_name)
        f.save(save_path)

        job_id = video_processor.start_job(save_path)
        return jsonify({"job_id": job_id})

    @app.route("/api/job/<job_id>")
    def api_job(job_id):
        job = video_processor.get_job(job_id)
        if job is None:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)

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
