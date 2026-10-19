from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
from loguru import logger
from .yolo import _resolve_device, _resolve_weights


# COCO-17 keypoint indices (ultralytics ordering)
NOSE, L_SHOULDER, R_SHOULDER = 0, 5, 6
L_HIP, R_HIP = 11, 12
L_ANKLE, R_ANKLE = 15, 16


@dataclass
class PoseKeypoints:
    """Keypoints for a single detected person. xy shape = (17, 2)."""
    xy: np.ndarray
    conf: np.ndarray  # (17,)


class PoseEstimator:
    """Thin wrapper. Runs YOLO-pose only when there is work (person present)."""

    def __init__(self, model: str = "yolo11n-pose.pt",
                 device: str = "auto", conf: float = 0.3, imgsz: int = 640):
        from ultralytics import YOLO  # local import
        self.conf = conf
        self.imgsz = imgsz
        self.device = _resolve_device(device)
        weights = _resolve_weights(model)
        logger.info(f"loading YOLO-pose weights: {weights} (device={self.device})")
        self.model = YOLO(str(weights))

    def infer(self, frame: np.ndarray) -> list[PoseKeypoints]:
        """Returns one PoseKeypoints per person detected in `frame`."""
        results = self.model.predict(
            source=frame, conf=self.conf, imgsz=self.imgsz,
            device=self.device, verbose=False,
        )
        out: list[PoseKeypoints] = []
        if not results or results[0].keypoints is None:
            return out
        kp = results[0].keypoints
        xy = kp.xy.cpu().numpy()      # (N, 17, 2)
        cfs = kp.conf.cpu().numpy() if kp.conf is not None \
            else np.ones((xy.shape[0], 17), dtype=np.float32)
        for i in range(xy.shape[0]):
            out.append(PoseKeypoints(xy[i], cfs[i]))
        return out


# ---------- geometry helpers used by behaviour rules ----------

def torso_angle_deg(pk: PoseKeypoints) -> Optional[float]:
    """Angle of the torso axis vs horizontal (0 = horizontal, 90 = upright)."""
    if pk.conf[L_SHOULDER] < 0.3 or pk.conf[R_SHOULDER] < 0.3 \
            or pk.conf[L_HIP] < 0.3 or pk.conf[R_HIP] < 0.3:
        return None
    sh = (pk.xy[L_SHOULDER] + pk.xy[R_SHOULDER]) / 2.0
    hp = (pk.xy[L_HIP] + pk.xy[R_HIP]) / 2.0
    dx, dy = hp[0] - sh[0], hp[1] - sh[1]
    if abs(dx) + abs(dy) < 1e-3:
        return None
    import math
    return abs(math.degrees(math.atan2(abs(dy), abs(dx))))


def kp_center(pk: PoseKeypoints) -> np.ndarray:
    """Mean of torso keypoints (used to associate pose -> track)."""
    pts = []
    for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP):
        if pk.conf[i] >= 0.3:
            pts.append(pk.xy[i])
    if not pts:
        return pk.xy.mean(axis=0)
    return np.mean(pts, axis=0)
