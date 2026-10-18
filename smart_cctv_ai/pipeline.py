from __future__ import annotations
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from loguru import logger
from sqlmodel import Session

from .camera.manager import CameraManager, Frame
from .config import Config, CameraCfg
from .behaviours import build_behaviours, BehaviourContext, Candidate, \
    pose_needed, object_classes_needed
from .detect.yolo import YoloTracker, Track
from .detect.pose import PoseEstimator, PoseKeypoints
from .recorder import ClipRecorder
from .schema import Event, Severity
from .zones import Zone
from . import db


class CameraState:
    """Per-camera overlay cache + cooldown tracker (shared with the MJPEG stream)."""
    def __init__(self, cfg: CameraCfg):
        self.cfg = cfg
        self.zones = [Zone(z) for z in cfg.zones]
        self.last_rendered: Optional[np.ndarray] = None
        self.last_tracks: list[Track] = []
        self.last_poses: list[PoseKeypoints] = []
        self.cooldown: dict[tuple[str, int, Optional[str]], float] = {}
        self.fps: float = 0.0
        self.frame_count: int = 0
        self._lock = threading.Lock()

    def set_frame(self, img: np.ndarray) -> None:
        with self._lock:
            self.last_rendered = img

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self.last_rendered is None else self.last_rendered.copy()


class Pipeline(threading.Thread):
    """Single worker: pull latest frame from each camera, detect+track, pose
    (optional), run rules, persist events, trigger clips, dispatch alerts +
    VLM. One YOLO + one YOLO-pose instance shared across cameras.
    """

    def __init__(self, cfg: Config):
        super().__init__(daemon=True, name="pipeline")
        self.cfg = cfg
        self._stop = threading.Event()
        self.cams = CameraManager()
        self.states: dict[str, CameraState] = {}

        self.tracker: Optional[YoloTracker] = None
        self.pose: Optional[PoseEstimator] = None
        self.behaviours = build_behaviours(cfg.behaviour)
        self.cooldown_s = cfg.behaviour.cooldown_seconds
        self._use_pose = pose_needed(cfg.behaviour)
        self._extra_classes = object_classes_needed(cfg.behaviour)
        self._pose_every = max(cfg.behaviour.pose.every_n_frames, 1)
        self._pose_min_people = cfg.behaviour.pose.min_people_for_pose

        Path("data/clips").mkdir(parents=True, exist_ok=True)
        db.init()

        self.recorder = ClipRecorder(
            pre_seconds=cfg.recorder.pre_seconds,
            post_seconds=cfg.recorder.post_seconds,
            fps=cfg.recorder.fps,
        ) if cfg.recorder.enabled else None

        # Alerts + VLM wired by api.app (needs the pipeline instance)
        self.telegram = None
        self.vlm = None

    def start_cameras(self) -> None:
        for cam in self.cfg.cameras:
            self.states[cam.id] = CameraState(cam)
            self.cams.add(cam.id, cam.source, fps=cam.fps)

    def _ensure_models(self) -> None:
        if self.tracker is None:
            d = self.cfg.detection
            self.tracker = YoloTracker(
                model=d.model, device=self.cfg.app.device,
                conf=d.conf, iou=d.iou, imgsz=d.imgsz,
                tracker=d.tracker, person_class=d.person_class,
                extra_classes=self._extra_classes,
            )
        if self._use_pose and self.pose is None:
            p = self.cfg.behaviour.pose
            self.pose = PoseEstimator(
                model=p.model, device=self.cfg.app.device,
                conf=p.conf, imgsz=p.imgsz,
            )

    def stop(self) -> None:
        self._stop.set()
        self.cams.stop_all()
        if self.telegram:
            self.telegram.stop()
        if self.vlm:
            self.vlm.stop()

    def run(self) -> None:
        self.start_cameras()
        try:
            self._ensure_models()
        except Exception as e:
            logger.error(f"model init failed: {e}")
            logger.error("pipeline continues without detection (cameras only)")

        last_tick = time.monotonic()
        frames_since = 0

        while not self._stop.is_set():
            did_work = False
            for cam_id, w in list(self.cams._workers.items()):
                f = w.read()
                if f is None:
                    continue
                state = self.states[cam_id]
                persons: list[Track] = []
                objects: list[Track] = []
                poses: list[PoseKeypoints] = []
                if self.tracker is not None:
                    try:
                        persons, objects = self.tracker.track(f.frame)
                    except Exception as e:
                        logger.error(f"[{cam_id}] detect error: {e}")
                state.last_tracks = persons
                state.frame_count += 1

                if (self.pose is not None and
                        len(persons) >= self._pose_min_people and
                        state.frame_count % self._pose_every == 0):
                    try:
                        poses = self.pose.infer(f.frame)
                    except Exception as e:
                        logger.error(f"[{cam_id}] pose error: {e}")
                state.last_poses = poses

                if self.recorder is not None:
                    self.recorder.push(cam_id, f.frame)

                self._run_rules(state, f, persons, objects, poses)
                self._render(state, f.frame, persons, poses)
                did_work = True
                frames_since += 1

            now = time.monotonic()
            if now - last_tick >= 1.0:
                total_fps = frames_since / (now - last_tick)
                for s in self.states.values():
                    s.fps = total_fps / max(len(self.states), 1)
                frames_since = 0
                last_tick = now

            if not did_work:
                time.sleep(0.01)

    def _run_rules(self, state: CameraState, f: Frame,
                   persons: list[Track], objects: list[Track],
                   poses: list[PoseKeypoints]) -> None:
        ctx = BehaviourContext(camera_id=f.camera_id, frame=f.frame,
                               ts=f.ts, tracks=persons, zones=state.zones,
                               poses=poses, objects=objects)
        candidates: list[Candidate] = []
        for b in self.behaviours:
            try:
                candidates.extend(b.process(ctx))
            except Exception as e:
                logger.error(f"[{f.camera_id}] behaviour {b.name} failed: {e}")
        for c in candidates:
            if not self._cooldown_ok(state, c, f.ts):
                continue
            self._persist(state, f, c)

    def _cooldown_ok(self, state: CameraState, c: Candidate, ts: float) -> bool:
        for tid in c.track_ids or [0]:
            key = (c.type.value, tid, c.zone)
            last = state.cooldown.get(key, -1e9)
            if ts - last < self.cooldown_s:
                return False
            state.cooldown[key] = ts
        return True

    def _persist(self, state: CameraState, f: Frame, c: Candidate) -> None:
        now = datetime.now(timezone.utc)
        snap_rel = self._save_snapshot(f, c)
        ev = Event(
            camera_id=f.camera_id, type=c.type, severity=c.severity,
            track_ids=c.track_ids, zone=c.zone,
            start_ts=now, end_ts=now,
            snapshot=snap_rel, clip=None,
            vlm_verdict=None, vlm_summary=None,
            meta=c.meta or {},
        )
        with Session(db.engine()) as s:
            s.add(ev)
            s.commit()
            s.refresh(ev)
        logger.info(f"EVENT #{ev.id} {ev.type.value} ({ev.severity.value}) "
                    f"on {ev.camera_id} zone={ev.zone} tracks={ev.track_ids}")

        # Telegram: snapshot first (fast)
        if self.telegram:
            self.telegram.submit_event(ev)

        # VLM: schedule verification; updates DB when done
        if self.vlm:
            self.vlm.submit(ev)

        # Clip: schedule post-event capture, then update DB + telegram
        if self.recorder:
            ev_id = ev.id

            def _on_clip_done(path: Path) -> None:
                self._update_clip(ev_id, path)
                if self.telegram:
                    self.telegram.submit_clip(ev_id, path)

            self.recorder.trigger(f.camera_id, c.type.value, on_done=_on_clip_done)

    def _update_clip(self, event_id: int, path: Path) -> None:
        try:
            with Session(db.engine()) as s:
                ev = s.get(Event, event_id)
                if ev is None:
                    return
                ev.clip = path.as_posix()
                ev.end_ts = datetime.now(timezone.utc)
                s.add(ev); s.commit()
        except Exception as e:
            logger.error(f"update clip failed for #{event_id}: {e}")

    def update_vlm(self, event_id: int, verdict: str, summary: str) -> None:
        try:
            with Session(db.engine()) as s:
                ev = s.get(Event, event_id)
                if ev is None:
                    return
                ev.vlm_verdict = verdict
                ev.vlm_summary = summary
                s.add(ev); s.commit()
        except Exception as e:
            logger.error(f"update vlm failed for #{event_id}: {e}")

    def _save_snapshot(self, f: Frame, c: Candidate) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")[:-3]
        name = f"{f.camera_id}_{c.type.value}_{ts}.jpg"
        path = Path("data/clips") / name
        try:
            cv2.imwrite(path.as_posix(), f.frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        except Exception as e:
            logger.error(f"snapshot save failed: {e}")
            return ""
        return path.as_posix()

    # ---------- rendering ----------
    def _render(self, state: CameraState, frame: np.ndarray,
                tracks: list[Track], poses: list[PoseKeypoints]) -> None:
        img = frame.copy()
        for z in state.zones:
            pts = z.np_polygon.reshape(-1, 1, 2)
            cv2.polylines(img, [pts], isClosed=True, color=(0, 165, 255), thickness=2)
            if len(z.np_polygon) > 0:
                x, y = z.np_polygon[0]
                cv2.putText(img, z.name, (int(x), int(y) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1, cv2.LINE_AA)
        for t in tracks:
            x1, y1, x2, y2 = (int(v) for v in t.xyxy)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 120), 2)
            cv2.putText(img, f"id {t.track_id}", (x1, max(y1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 120), 1, cv2.LINE_AA)
        for pk in poses:
            for (x, y), c in zip(pk.xy, pk.conf):
                if c >= 0.3:
                    cv2.circle(img, (int(x), int(y)), 2, (180, 220, 255), -1)
        cv2.putText(img, f"{state.cfg.id}  {state.fps:4.1f} fps",
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2, cv2.LINE_AA)
        state.set_frame(img)
