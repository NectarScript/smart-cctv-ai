from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from src.core.config import BehaviourConfig
from src.core.types import BehaviourEvent
from src.behaviour.rules import RuleBasedClassifier
from src.detection.track_store import TrackHistory

logger = logging.getLogger(__name__)


class BehaviourClassifier:
    """Facade: dispatches to rule-based (now) or ML-based (future) engine."""

    def __init__(self, config: BehaviourConfig, mode: str = "rules"):
        self._mode = mode
        if mode == "rules":
            self._engine = RuleBasedClassifier(config)
        else:
            raise ValueError(f"Unknown classifier mode: {mode}")
        logger.info("Behaviour classifier: mode=%s", mode)

    def classify(
        self,
        track_id: int,
        track_history: TrackHistory,
        keypoint_seq: Optional[np.ndarray],
        all_active_tracks: List[TrackHistory],
        timestamp: float,
    ) -> BehaviourEvent:
        return self._engine.classify(
            track_id, track_history, keypoint_seq, all_active_tracks, timestamp
        )

    @property
    def mode(self) -> str:
        return self._mode
