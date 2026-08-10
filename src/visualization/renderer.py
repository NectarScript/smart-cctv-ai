from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np
import supervision as sv

from src.core.constants import BehaviourLabel, EventType, MEDIAPIPE_CONNECTIONS
from src.core.types import BehaviourEvent

COLOR_MAP = {
    BehaviourLabel.NORMAL: (0, 200, 0),
    BehaviourLabel.SUSPICIOUS: (0, 165, 255),
    BehaviourLabel.CRITICAL: (0, 0, 255),
}

SKELETON_COLOR = (200, 200, 200)


class Renderer:
    """Draws bounding boxes, track IDs, behaviour labels, and pose skeletons."""

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

        if tracked.tracker_id is not None:
            for i, tid in enumerate(tracked.tracker_id):
                tid = int(tid)
                bbox = tracked.xyxy[i].astype(int)
                x1, y1, x2, y2 = bbox

                event = event_map.get(tid)
                label = event.label if event else BehaviourLabel.NORMAL
                color = COLOR_MAP.get(label, (0, 200, 0))

                thickness = 3 if label == BehaviourLabel.CRITICAL else 2
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

                text_parts = [f"ID:{tid}"]
                if event and event.event_type != EventType.NORMAL:
                    text_parts.append(event.event_type.value)
                    text_parts.append(f"{event.confidence:.0%}")
                text = " ".join(text_parts)

                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                cv2.putText(annotated, text, (x1 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                if keypoints and tid in keypoints:
                    self._draw_skeleton(annotated, keypoints[tid], bbox)

        cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(annotated, f"Tracks: {len(tracked) if tracked.tracker_id is not None else 0}",
                    (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        return annotated

    def _draw_skeleton(
        self,
        frame: np.ndarray,
        keypoints: np.ndarray,
        bbox: np.ndarray,
    ) -> None:
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
                if pts[a][2] > 0.3 and pts[b][2] > 0.3:
                    cv2.line(frame,
                             (pts[a][0], pts[a][1]),
                             (pts[b][0], pts[b][1]),
                             SKELETON_COLOR, 1)

        for px, py, vis in pts:
            if vis > 0.3:
                cv2.circle(frame, (px, py), 2, (0, 255, 255), -1)
