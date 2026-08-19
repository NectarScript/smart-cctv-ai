from __future__ import annotations

import time
from typing import Dict, List, Optional

import cv2
import numpy as np
import supervision as sv

from src.core.constants import BehaviourLabel, EventType, MEDIAPIPE_CONNECTIONS
from src.core.types import BehaviourEvent

COLOR_NORMAL = (76, 175, 80)
COLOR_SUSPICIOUS = (0, 165, 255)
COLOR_CRITICAL = (60, 60, 255)
COLOR_NORMAL_FILL = (76, 175, 80, 60)
COLOR_SUSPICIOUS_FILL = (0, 165, 255, 60)
COLOR_CRITICAL_FILL = (60, 60, 255, 60)

COLOR_MAP = {
    BehaviourLabel.NORMAL: COLOR_NORMAL,
    BehaviourLabel.SUSPICIOUS: COLOR_SUSPICIOUS,
    BehaviourLabel.CRITICAL: COLOR_CRITICAL,
}

LABEL_DISPLAY = {
    EventType.LOITERING: "LOITERING",
    EventType.FIGHTING: "FIGHTING",
    EventType.SUDDEN_RUNNING: "RUNNING",
    EventType.CROWD_SURGE: "CROWD",
    EventType.THEFT_POSTURE: "THEFT",
    EventType.NORMAL: "OK",
}

SKELETON_COLORS = {
    "torso": (180, 220, 255),
    "left": (255, 180, 100),
    "right": (100, 180, 255),
    "face": (200, 200, 200),
}

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SMALL = cv2.FONT_HERSHEY_PLAIN


def _overlay_rect(frame: np.ndarray, pt1, pt2, color, alpha: float) -> None:
    x1, y1 = pt1
    x2, y2 = pt2
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    overlay = np.full_like(roi, color[:3])
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)


def _rounded_rect(frame: np.ndarray, pt1, pt2, color, radius: int = 8,
                  thickness: int = 2, fill_alpha: float = 0.0) -> None:
    x1, y1 = pt1
    x2, y2 = pt2
    r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    if r < 1:
        cv2.rectangle(frame, pt1, pt2, color, thickness)
        return

    if fill_alpha > 0:
        _overlay_rect(frame, pt1, pt2, color, fill_alpha)

    cv2.line(frame, (x1 + r, y1), (x2 - r, y1), color, thickness)
    cv2.line(frame, (x1 + r, y2), (x2 - r, y2), color, thickness)
    cv2.line(frame, (x1, y1 + r), (x1, y2 - r), color, thickness)
    cv2.line(frame, (x2, y1 + r), (x2, y2 - r), color, thickness)
    cv2.ellipse(frame, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)
    cv2.ellipse(frame, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)
    cv2.ellipse(frame, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)
    cv2.ellipse(frame, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)


def _draw_badge(frame: np.ndarray, text: str, x: int, y: int,
                bg_color, text_color=(255, 255, 255), scale: float = 0.45) -> int:
    (tw, th), baseline = cv2.getTextSize(text, FONT, scale, 1)
    pad_x, pad_y = 8, 4
    bx1, by1 = x, y - th - pad_y * 2
    bx2, by2 = x + tw + pad_x * 2, y
    _overlay_rect(frame, (bx1, by1), (bx2, by2), bg_color, 0.85)
    cv2.putText(frame, text, (x + pad_x, y - pad_y - 1), FONT, scale, text_color, 1, cv2.LINE_AA)
    return bx2


class Renderer:
    """Modern HUD-style renderer for surveillance feeds."""

    def __init__(self):
        self._start_time = time.time()
        self._event_flash: Dict[int, float] = {}

    def draw(
        self,
        frame: np.ndarray,
        tracked: sv.Detections,
        events: List[BehaviourEvent],
        keypoints: Optional[Dict[int, np.ndarray]] = None,
        fps: float = 0.0,
    ) -> np.ndarray:
        annotated = frame.copy()
        event_map: Dict[int, BehaviourEvent] = {}
        for e in events:
            event_map[e.track_id] = e

        now = time.time()
        alert_count = 0

        if tracked.tracker_id is not None:
            for i, tid in enumerate(tracked.tracker_id):
                tid = int(tid)
                bbox = tracked.xyxy[i].astype(int)
                x1, y1, x2, y2 = bbox

                event = event_map.get(tid)
                label = event.label if event else BehaviourLabel.NORMAL
                color = COLOR_MAP.get(label, COLOR_NORMAL)

                if label != BehaviourLabel.NORMAL:
                    alert_count += 1
                    self._event_flash[tid] = now

                is_flashing = (now - self._event_flash.get(tid, 0)) < 2.0
                fill_alpha = 0.12 if label == BehaviourLabel.NORMAL else 0.2
                thickness = 2 if label == BehaviourLabel.NORMAL else 3

                if is_flashing and label != BehaviourLabel.NORMAL:
                    pulse = 0.5 + 0.5 * np.sin(now * 6)
                    fill_alpha = 0.15 + 0.15 * pulse
                    thickness = 3

                _rounded_rect(annotated, (x1, y1), (x2, y2), color,
                              radius=6, thickness=thickness, fill_alpha=fill_alpha)

                self._draw_corner_brackets(annotated, x1, y1, x2, y2, color, thickness)

                tag_y = y1 - 4
                if tag_y < 20:
                    tag_y = y2 + 20

                id_text = f"#{tid}"
                cursor_x = _draw_badge(annotated, id_text, x1, tag_y, (40, 40, 40))

                if event and event.event_type != EventType.NORMAL:
                    evt_text = LABEL_DISPLAY.get(event.event_type, event.event_type.value)
                    conf_text = f"{evt_text} {event.confidence:.0%}"
                    _draw_badge(annotated, conf_text, cursor_x + 3, tag_y, color)

                if keypoints and tid in keypoints:
                    self._draw_skeleton(annotated, keypoints[tid], bbox, color)

        self._draw_hud(annotated, fps, tracked, alert_count)
        self._draw_timestamp(annotated)

        return annotated

    def _draw_corner_brackets(self, frame, x1, y1, x2, y2, color, thickness):
        bracket_len = min(20, (x2 - x1) // 4, (y2 - y1) // 4)
        if bracket_len < 4:
            return
        t = max(1, thickness - 1)
        cv2.line(frame, (x1, y1), (x1 + bracket_len, y1), color, t)
        cv2.line(frame, (x1, y1), (x1, y1 + bracket_len), color, t)
        cv2.line(frame, (x2, y1), (x2 - bracket_len, y1), color, t)
        cv2.line(frame, (x2, y1), (x2, y1 + bracket_len), color, t)
        cv2.line(frame, (x1, y2), (x1 + bracket_len, y2), color, t)
        cv2.line(frame, (x1, y2), (x1, y2 - bracket_len), color, t)
        cv2.line(frame, (x2, y2), (x2 - bracket_len, y2), color, t)
        cv2.line(frame, (x2, y2), (x2, y2 - bracket_len), color, t)

    def _draw_skeleton(self, frame, keypoints, bbox, color):
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1

        pts = []
        for kp in keypoints:
            px = int(x1 + kp[0] * bw)
            py = int(y1 + kp[1] * bh)
            vis = kp[2]
            pts.append((px, py, vis))

        for a, b in MEDIAPIPE_CONNECTIONS:
            if a < len(pts) and b < len(pts):
                if pts[a][2] > 0.4 and pts[b][2] > 0.4:
                    seg_color = self._segment_color(a, b)
                    cv2.line(frame, (pts[a][0], pts[a][1]),
                             (pts[b][0], pts[b][1]), seg_color, 1, cv2.LINE_AA)

        for px, py, vis in pts:
            if vis > 0.4:
                cv2.circle(frame, (px, py), 3, color, -1, cv2.LINE_AA)
                cv2.circle(frame, (px, py), 3, (255, 255, 255), 1, cv2.LINE_AA)

    @staticmethod
    def _segment_color(a: int, b: int):
        left_ids = {11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31}
        right_ids = {12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32}
        if a in left_ids and b in left_ids:
            return SKELETON_COLORS["left"]
        if a in right_ids and b in right_ids:
            return SKELETON_COLORS["right"]
        if a <= 10 and b <= 10:
            return SKELETON_COLORS["face"]
        return SKELETON_COLORS["torso"]

    def _draw_hud(self, frame, fps, tracked, alert_count):
        h, w = frame.shape[:2]

        _overlay_rect(frame, (0, 0), (220, 90), (0, 0, 0), 0.6)

        fps_color = (0, 255, 100) if fps >= 15 else (0, 200, 255) if fps >= 8 else (0, 80, 255)
        cv2.putText(frame, f"{fps:.0f} FPS", (12, 28), FONT, 0.65, fps_color, 2, cv2.LINE_AA)

        track_n = len(tracked) if tracked.tracker_id is not None else 0
        cv2.putText(frame, f"Tracks: {track_n}", (12, 52), FONT, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        if alert_count > 0:
            cv2.putText(frame, f"Alerts: {alert_count}", (12, 75), FONT, 0.45, COLOR_CRITICAL, 1, cv2.LINE_AA)
        else:
            cv2.putText(frame, "Status: Clear", (12, 75), FONT, 0.45, COLOR_NORMAL, 1, cv2.LINE_AA)

        legend_y = h - 55
        _overlay_rect(frame, (0, legend_y - 5), (170, h), (0, 0, 0), 0.5)
        for i, (lbl, clr) in enumerate([(BehaviourLabel.NORMAL, COLOR_NORMAL),
                                         (BehaviourLabel.SUSPICIOUS, COLOR_SUSPICIOUS),
                                         (BehaviourLabel.CRITICAL, COLOR_CRITICAL)]):
            ly = legend_y + i * 18
            cv2.circle(frame, (14, ly), 5, clr, -1, cv2.LINE_AA)
            cv2.putText(frame, lbl.value.upper(), (26, ly + 4), FONT, 0.38, (200, 200, 200), 1, cv2.LINE_AA)

    def _draw_timestamp(self, frame):
        h, w = frame.shape[:2]
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        (tw, th), _ = cv2.getTextSize(ts, FONT, 0.4, 1)
        tx = w - tw - 12
        _overlay_rect(frame, (tx - 6, 0), (w, th + 12), (0, 0, 0), 0.5)
        cv2.putText(frame, ts, (tx, th + 6), FONT, 0.4, (180, 180, 180), 1, cv2.LINE_AA)
