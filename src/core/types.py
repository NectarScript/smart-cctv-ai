from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.core.constants import BehaviourLabel, EventType


@dataclass
class FramePacket:
    camera_id: str
    frame: np.ndarray
    timestamp: float
    frame_number: int


@dataclass
class BehaviourEvent:
    track_id: int
    camera_id: str
    label: BehaviourLabel
    event_type: EventType
    confidence: float
    timestamp: float
    details: dict = field(default_factory=dict)
