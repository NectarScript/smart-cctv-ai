from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional
import numpy as np
from ..detect.yolo import Track
from ..schema import BehaviourType, Severity
from ..zones import Zone


@dataclass
class BehaviourContext:
    camera_id: str
    frame: np.ndarray
    ts: float
    tracks: list[Track]
    zones: list[Zone]


@dataclass
class Candidate:
    """A rule's output. The pipeline turns a Candidate into an Event."""
    type: BehaviourType
    severity: Severity
    track_ids: list[int]
    zone: Optional[str] = None
    meta: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.meta is None:
            self.meta = {}


class Behaviour:
    """Plugin interface. Each rule is one class, one process() call per frame."""
    name: str = "base"

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        return []
