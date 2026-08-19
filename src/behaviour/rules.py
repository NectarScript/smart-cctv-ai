from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from src.core.config import BehaviourConfig
from src.core.constants import (
    BehaviourLabel,
    EventType,
    LEFT_ANKLE,
    LEFT_HIP,
    LEFT_KNEE,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_ANKLE,
    RIGHT_HIP,
    RIGHT_KNEE,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)
from src.core.types import BehaviourEvent
from src.detection.track_store import TrackHistory

logger = logging.getLogger(__name__)

LIMB_INDICES = [LEFT_WRIST, RIGHT_WRIST, LEFT_ANKLE, RIGHT_ANKLE]
SEVERITY_ORDER = {
    BehaviourLabel.CRITICAL: 3,
    BehaviourLabel.SUSPICIOUS: 2,
    BehaviourLabel.NORMAL: 1,
}


class RuleBasedClassifier:
    """Heuristic behaviour classification from track history and pose keypoints."""

    def __init__(self, config: BehaviourConfig):
        self._cfg = config

    def classify(
        self,
        track_id: int,
        track_history: TrackHistory,
        keypoint_seq: Optional[np.ndarray],
        all_active_tracks: List[TrackHistory],
        timestamp: float,
    ) -> BehaviourEvent:
        candidates: List[BehaviourEvent] = []

        fighting = self._check_fighting(track_id, track_history, keypoint_seq, all_active_tracks, timestamp)
        if fighting:
            candidates.append(fighting)

        running = self._check_sudden_running(track_id, track_history, timestamp)
        if running:
            candidates.append(running)

        crowd = self._check_crowd_surge(track_id, track_history, all_active_tracks, timestamp)
        if crowd:
            candidates.append(crowd)

        loitering = self._check_loitering(track_id, track_history, timestamp)
        if loitering:
            candidates.append(loitering)

        if self._cfg.theft_posture_enabled:
            theft = self._check_theft_posture(track_id, track_history, keypoint_seq, timestamp)
            if theft:
                candidates.append(theft)

        if not candidates:
            return BehaviourEvent(
                track_id=track_id,
                camera_id=track_history.camera_id,
                label=BehaviourLabel.NORMAL,
                event_type=EventType.NORMAL,
                confidence=1.0,
                timestamp=timestamp,
            )

        candidates.sort(key=lambda e: SEVERITY_ORDER.get(e.label, 0), reverse=True)
        return candidates[0]

    def _check_loitering(
        self,
        track_id: int,
        history: TrackHistory,
        timestamp: float,
    ) -> Optional[BehaviourEvent]:
        duration = history.duration
        if duration < self._cfg.loiter_time_threshold:
            return None

        n_recent = min(len(history.centroids), int(self._cfg.loiter_time_threshold * 25))
        if n_recent < 25:
            return None
        recent = list(history.centroids)[-n_recent:]
        pts = np.array(recent)
        median = np.median(pts, axis=0)
        dists = np.sqrt(np.sum((pts - median) ** 2, axis=1))
        max_disp = float(np.max(dists))

        if max_disp >= self._cfg.loiter_radius_px:
            return None

        avg_vel = self._avg_velocity(recent)
        if avg_vel < self._cfg.loiter_min_displacement_px:
            return None

        severity = BehaviourLabel.CRITICAL if duration > self._cfg.loiter_time_threshold * 2 else BehaviourLabel.SUSPICIOUS
        confidence = min(1.0, duration / (self._cfg.loiter_time_threshold * 2))

        return BehaviourEvent(
            track_id=track_id,
            camera_id=history.camera_id,
            label=severity,
            event_type=EventType.LOITERING,
            confidence=confidence,
            timestamp=timestamp,
            details={
                "duration_sec": round(duration, 1),
                "max_displacement_px": round(max_disp, 1),
                "radius_threshold_px": self._cfg.loiter_radius_px,
            },
        )

    def _check_sudden_running(
        self,
        track_id: int,
        history: TrackHistory,
        timestamp: float,
    ) -> Optional[BehaviourEvent]:
        if history.duration < self._cfg.sudden_run_min_history_sec:
            return None
        if len(history.centroids) < 50:
            return None

        pts = list(history.centroids)
        n = len(pts)
        recent_window = min(25, n // 3)
        baseline_window = min(75, n - recent_window)

        if baseline_window < 20:
            return None

        recent = pts[-recent_window:]
        baseline = pts[-(recent_window + baseline_window):-recent_window]

        recent_vel = self._avg_velocity(recent)
        baseline_vel = self._avg_velocity(baseline)

        if recent_vel < self._cfg.sudden_run_min_velocity:
            return None

        if baseline_vel < self._cfg.velocity_min_baseline:
            baseline_vel = self._cfg.velocity_min_baseline

        ratio = recent_vel / baseline_vel
        if ratio < self._cfg.velocity_spike_factor:
            return None

        return BehaviourEvent(
            track_id=track_id,
            camera_id=history.camera_id,
            label=BehaviourLabel.SUSPICIOUS,
            event_type=EventType.SUDDEN_RUNNING,
            confidence=min(1.0, ratio / (self._cfg.velocity_spike_factor * 2)),
            timestamp=timestamp,
            details={
                "recent_velocity_px_frame": round(recent_vel, 2),
                "baseline_velocity_px_frame": round(baseline_vel, 2),
                "ratio": round(ratio, 2),
            },
        )

    def _check_fighting(
        self,
        track_id: int,
        history: TrackHistory,
        keypoint_seq: Optional[np.ndarray],
        all_tracks: List[TrackHistory],
        timestamp: float,
    ) -> Optional[BehaviourEvent]:
        current = history.current_centroid
        if current is None:
            return None

        nearby = []
        for other in all_tracks:
            if other.track_id == track_id:
                continue
            oc = other.current_centroid
            if oc is None:
                continue
            dist = np.sqrt((current[0] - oc[0]) ** 2 + (current[1] - oc[1]) ** 2)
            if dist < self._cfg.proximity_threshold_px:
                nearby.append(other)

        if not nearby:
            return None

        if keypoint_seq is None or len(keypoint_seq) < self._cfg.fighting_sustained_frames:
            return None

        rapid = self._detect_rapid_limb_movement(keypoint_seq)
        if not rapid:
            return None

        return BehaviourEvent(
            track_id=track_id,
            camera_id=history.camera_id,
            label=BehaviourLabel.CRITICAL,
            event_type=EventType.FIGHTING,
            confidence=0.7,
            timestamp=timestamp,
            details={
                "nearby_track_ids": [t.track_id for t in nearby],
                "proximity_px": self._cfg.proximity_threshold_px,
            },
        )

    def _check_crowd_surge(
        self,
        track_id: int,
        history: TrackHistory,
        all_tracks: List[TrackHistory],
        timestamp: float,
    ) -> Optional[BehaviourEvent]:
        current = history.current_centroid
        if current is None:
            return None

        nearby_count = 0
        min_tid_in_cluster = track_id
        for other in all_tracks:
            oc = other.current_centroid
            if oc is None:
                continue
            dist = np.sqrt((current[0] - oc[0]) ** 2 + (current[1] - oc[1]) ** 2)
            if dist < self._cfg.crowd_region_radius_px:
                nearby_count += 1
                min_tid_in_cluster = min(min_tid_in_cluster, other.track_id)

        if nearby_count < self._cfg.crowd_density_threshold:
            return None

        if track_id != min_tid_in_cluster:
            return None

        return BehaviourEvent(
            track_id=track_id,
            camera_id=history.camera_id,
            label=BehaviourLabel.CRITICAL,
            event_type=EventType.CROWD_SURGE,
            confidence=min(1.0, nearby_count / (self._cfg.crowd_density_threshold * 2)),
            timestamp=timestamp,
            details={
                "cluster_size": nearby_count,
                "threshold": self._cfg.crowd_density_threshold,
            },
        )

    def _check_theft_posture(
        self,
        track_id: int,
        history: TrackHistory,
        keypoint_seq: Optional[np.ndarray],
        timestamp: float,
    ) -> Optional[BehaviourEvent]:
        if keypoint_seq is None or len(keypoint_seq) < 15:
            return None

        crouch_frames = 0
        for kp in keypoint_seq[-30:]:
            l_shoulder_y = kp[LEFT_SHOULDER][1]
            r_shoulder_y = kp[RIGHT_SHOULDER][1]
            l_hip_y = kp[LEFT_HIP][1]
            r_hip_y = kp[RIGHT_HIP][1]
            l_wrist_y = kp[LEFT_WRIST][1]
            r_wrist_y = kp[RIGHT_WRIST][1]

            shoulder_y = (l_shoulder_y + r_shoulder_y) / 2
            hip_y = (l_hip_y + r_hip_y) / 2
            wrist_y = min(l_wrist_y, r_wrist_y)

            torso_ratio = abs(hip_y - shoulder_y)
            if torso_ratio < 0.15 and wrist_y > hip_y:
                crouch_frames += 1

        fps_approx = 25
        required_frames = int(self._cfg.theft_posture_duration_sec * fps_approx)
        if crouch_frames < required_frames:
            return None

        return BehaviourEvent(
            track_id=track_id,
            camera_id=history.camera_id,
            label=BehaviourLabel.SUSPICIOUS,
            event_type=EventType.THEFT_POSTURE,
            confidence=0.4,
            timestamp=timestamp,
            details={
                "crouch_frames": crouch_frames,
                "note": "Experimental — high false-positive rate expected",
            },
        )

    def _detect_rapid_limb_movement(self, keypoint_seq: np.ndarray) -> bool:
        if len(keypoint_seq) < self._cfg.fighting_sustained_frames + 1:
            return False

        seq = keypoint_seq[-self._cfg.fighting_sustained_frames - 1:]
        consecutive = 0
        for i in range(1, len(seq)):
            velocities = []
            for idx in LIMB_INDICES:
                dx = seq[i][idx][0] - seq[i - 1][idx][0]
                dy = seq[i][idx][1] - seq[i - 1][idx][1]
                velocities.append(np.sqrt(dx * dx + dy * dy))
            avg_vel = np.mean(velocities)
            if avg_vel > self._cfg.limb_velocity_threshold / 100.0:
                consecutive += 1
            else:
                consecutive = 0
            if consecutive >= self._cfg.fighting_sustained_frames:
                return True
        return False

    @staticmethod
    def _avg_velocity(points: list) -> float:
        if len(points) < 2:
            return 0.0
        dists = []
        for i in range(1, len(points)):
            dx = points[i][0] - points[i - 1][0]
            dy = points[i][1] - points[i - 1][1]
            dists.append(np.sqrt(dx * dx + dy * dy))
        return float(np.mean(dists))

    @staticmethod
    def _total_path_length(points: list) -> float:
        if len(points) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i - 1][0]
            dy = points[i][1] - points[i - 1][1]
            total += np.sqrt(dx * dx + dy * dy)
        return total
