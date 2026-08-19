import pytest
from src.core.config import AppConfig, CameraConfig, load_config
from src.core.constants import SourceType


def test_default_config_loads():
    config = AppConfig()
    assert config.detection.model_name == "yolov8n.pt"
    assert config.detection.confidence_threshold == 0.45
    assert config.tracking.lost_track_buffer == 30
    assert config.behaviour.loiter_time_threshold == 30.0


def test_camera_config_infers_webcam():
    cam = CameraConfig(source_id="test", source=0)
    assert cam.source_type == SourceType.WEBCAM


def test_camera_config_infers_file():
    cam = CameraConfig(source_id="test", source="video.mp4")
    assert cam.source_type == SourceType.FILE


def test_camera_config_infers_rtsp():
    cam = CameraConfig(source_id="test", source="rtsp://192.168.1.1:554/stream")
    assert cam.source_type == SourceType.RTSP


def test_load_config_default():
    config = load_config()
    assert isinstance(config, AppConfig)
    assert config.log_level == "INFO"


def test_load_config_missing_file():
    config = load_config("/nonexistent/path.yaml")
    assert isinstance(config, AppConfig)
