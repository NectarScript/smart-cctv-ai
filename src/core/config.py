from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Union

import yaml
from pydantic import BaseModel, field_validator, model_validator

from src.core.constants import SourceType

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


class CameraConfig(BaseModel):
    source_id: str
    source: Union[int, str]
    source_type: Optional[SourceType] = None
    fps_target: int = 25
    resolution: Tuple[int, int] = (640, 480)

    @model_validator(mode="after")
    def infer_source_type(self):
        if self.source_type is not None:
            return self
        if isinstance(self.source, int):
            self.source_type = SourceType.WEBCAM
        elif isinstance(self.source, str) and self.source.startswith("rtsp"):
            self.source_type = SourceType.RTSP
        else:
            self.source_type = SourceType.FILE
        return self


class DetectionConfig(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.45
    person_class_id: int = 0
    device: str = "cpu"
    input_size: int = 640


class TrackingConfig(BaseModel):
    track_activation_threshold: float = 0.25
    lost_track_buffer: int = 30
    minimum_matching_threshold: float = 0.8
    frame_rate: int = 25


class BehaviourConfig(BaseModel):
    keypoint_window_size: int = 30
    min_keypoint_frames: int = 15
    loiter_time_threshold: float = 30.0
    loiter_radius_px: int = 40
    loiter_min_displacement_px: float = 2.0
    velocity_spike_factor: float = 4.0
    velocity_min_baseline: float = 3.0
    sudden_run_min_velocity: float = 8.0
    sudden_run_min_history_sec: float = 5.0
    proximity_threshold_px: int = 60
    limb_velocity_threshold: float = 20.0
    fighting_sustained_frames: int = 8
    crowd_density_threshold: int = 6
    crowd_region_radius_px: int = 200
    theft_posture_enabled: bool = False
    theft_posture_duration_sec: float = 3.0


class AppConfig(BaseModel):
    cameras: List[CameraConfig] = []
    detection: DetectionConfig = DetectionConfig()
    tracking: TrackingConfig = TrackingConfig()
    behaviour: BehaviourConfig = BehaviourConfig()
    frame_queue_maxsize: int = 64
    log_level: str = "INFO"
    pose_every_n_frames: int = 3


def load_config(path: Optional[Union[str, Path]] = None) -> AppConfig:
    if path is None:
        path = CONFIG_DIR / "default.yaml"
    path = Path(path)
    if not path.exists():
        return AppConfig()
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return AppConfig(**data)
