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
from .behaviours import build_behaviours, BehaviourContext, Candidate
from .detect.yolo import YoloTracker, Track
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
        self.cooldown: dict[tuple[str, int, Optional[str]], float] = {}
        self.fps: float = 0.0
        self._lock = threading.Lock()

    def set_frame(self, img: np.ndarray) -> None:
        with self._lock:
            self.last_rendered = img

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self.last_rendered is None else self.last_rendered.copy()


class Pipeline(threading.Thread):
    """Single worker: pull latest frame from each camera, detect+track, run rules,
    persist events. One YOLO instance shared across cameras to stay inside VRAM.
    """

    def __init__(self, cfg: Config):
        super().__init__(daemon=True, name="pipeline")
        self.cfg = cfg
        self._stop = threading.Event()
        self.cams = CameraManager()
        self.states: dict[str, CameraState] = {}
        self.tracker: Optional[YoloTracker] = None  # lazy
        self.behaviours = build_behaviours(cfg.behaviour)
        self.cooldown_s = cfg.behaviour.cooldown_seconds
        Path("data/clips").mkdir(parents=True, exist_ok=True)
        db.init()

    def start_cameras(self) -> None:
        for cam in self.cfg.cameras:
            self.states[cam.id] = CameraState(cam)
            self.cams.add(cam.id, cam.source, fps=cam.fps)

    def _ensure_tracker(self) -> YoloTracker:
        if self.tracker is None:
            d = self.cfg.detection
            self.tracker = YoloTracker(
                model=d.model, device=self.cfg.app.device,
                conf=d.conf, iou=d.iou, imgsz=d.imgsz,
                tracker=d.tracker, person_class=d.person_class,
            )
        return self.tracker

    def stop(self) -> None:
        self._stop.set()
        self.cams.stop_all()

    def run(self) -> None:
        self.start_cameras()
        try:
            tracker = self._ensure_tracker()
        except Exception as e:
            logger.error(f"YOLO failed to load: {e}")
            logger.error("pipeline will keep cameras running without detection")
            tracker = None

        last_tick = time.monotonic()
        frames_since = 0

        while not self._stop.is_set():
            did_work = False
            for cam_id, w in list(self.cams._workers.items()):
                f = w.read()
                if f is None:
                    continue
                state = self.states[cam_id]
                tracks: list[Track] = []
                if tracker is not None:
                    try:
                        tracks = tracker.track(f.frame)
                    except Exception as e:
                        logger.error(f"[{cam_id}] detect error: {e}")
                state.last_tracks = tracks
                self._run_rules(state, f, tracks)
                self._render(state, f.frame, tracks)
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

    def _run_rules(self, state: CameraState, f: Frame, tracks: list[Track]) -> None:
        ctx = BehaviourContext(camera_id=f.camera_id, frame=f.frame,
                               ts=f.ts, tracks=tracks, zones=state.zones)
        candidates: list[Candidate] = []
        for b in self.behaviours:
            try:
                candidates.extend(b.process(ctx))
            except Exception as e:
                logger.error(f"[{f.camera_id}] behaviour {b.name} failed: {e}")
        for c in candidates:
            if not self._cooldown_ok(state, f.camera_id, c, f.ts):
                continue
            self._persist(state, f, c)

    def _cooldown_ok(self, state: CameraState, cam_id: str,
                     c: Candidate, ts: float) -> bool:
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
        logger.info(f"EVENT #{ev.id} {ev.type.value} on {ev.camera_id} "
                    f"zone={ev.zone} tracks={ev.track_ids}")

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
                tracks: list[Track]) -> None:
        img = frame.copy()
        # zones
        for z in state.zones:
            pts = z.np_polygon.reshape(-1, 1, 2)
            cv2.polylines(img, [pts], isClosed=True, color=(0, 165, 255), thickness=2)
            if len(z.np_polygon) > 0:
                x, y = z.np_polygon[0]
                cv2.putText(img, z.name, (int(x), int(y) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1, cv2.LINE_AA)
        # tracks
        for t in tracks:
            x1, y1, x2, y2 = (int(v) for v in t.xyxy)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 120), 2)
            cv2.putText(img, f"id {t.track_id}", (x1, max(y1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 120), 1, cv2.LINE_AA)
        cv2.putText(img, f"{state.cfg.id}  {state.fps:4.1f} fps",
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2, cv2.LINE_AA)
        state.set_frame(img)
