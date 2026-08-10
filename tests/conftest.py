import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import AppConfig, BehaviourConfig, DetectionConfig, TrackingConfig


@pytest.fixture
def sample_frame():
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_person_crop():
    return np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8)


@pytest.fixture
def default_config():
    return AppConfig()


@pytest.fixture
def behaviour_config():
    return BehaviourConfig()


@pytest.fixture
def detection_config():
    return DetectionConfig()


@pytest.fixture
def tracking_config():
    return TrackingConfig()
