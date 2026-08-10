from __future__ import annotations

from typing import Dict

import cv2
import numpy as np


class Display:
    """OpenCV window management for single or multi-camera views."""

    def __init__(self, window_prefix: str = "Smart CCTV AI"):
        self._prefix = window_prefix
        self._windows: set = set()

    def show(self, camera_id: str, frame: np.ndarray) -> None:
        name = f"{self._prefix} - {camera_id}"
        if name not in self._windows:
            cv2.namedWindow(name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(name, frame.shape[1], frame.shape[0])
            self._windows.add(name)
        cv2.imshow(name, frame)

    def show_grid(self, frames: Dict[str, np.ndarray], cols: int = 2) -> None:
        if not frames:
            return
        frame_list = list(frames.values())
        h, w = frame_list[0].shape[:2]

        for i in range(len(frame_list)):
            if frame_list[i].shape[:2] != (h, w):
                frame_list[i] = cv2.resize(frame_list[i], (w, h))

        rows_needed = (len(frame_list) + cols - 1) // cols
        while len(frame_list) < rows_needed * cols:
            frame_list.append(np.zeros((h, w, 3), dtype=np.uint8))

        row_imgs = []
        for r in range(rows_needed):
            row = frame_list[r * cols:(r + 1) * cols]
            row_imgs.append(np.hstack(row))
        grid = np.vstack(row_imgs)

        name = f"{self._prefix} - Grid"
        if name not in self._windows:
            cv2.namedWindow(name, cv2.WINDOW_NORMAL)
            self._windows.add(name)
        cv2.imshow(name, grid)

    def check_quit(self) -> bool:
        return cv2.waitKey(1) & 0xFF == ord("q")

    def destroy_all(self) -> None:
        cv2.destroyAllWindows()
        self._windows.clear()
