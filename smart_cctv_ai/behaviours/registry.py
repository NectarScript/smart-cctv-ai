from __future__ import annotations
from ..config import BehaviourCfg
from .base import Behaviour
from .intrusion import Intrusion
from .loitering import Loitering


def build_behaviours(cfg: BehaviourCfg) -> list[Behaviour]:
    out: list[Behaviour] = []
    if cfg.intrusion.enabled:
        out.append(Intrusion())
    if cfg.loitering.enabled:
        out.append(Loitering(dwell_seconds=cfg.loitering.dwell_seconds))
    return out
