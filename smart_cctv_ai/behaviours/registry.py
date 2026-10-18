from __future__ import annotations
from ..config import BehaviourCfg
from .base import Behaviour
from .intrusion import Intrusion
from .loitering import Loitering
from .running import Running
from .fall import Fall
from .fighting import Fighting
from .crowd_surge import CrowdSurge
from .unattended import UnattendedObject


def build_behaviours(cfg: BehaviourCfg) -> list[Behaviour]:
    out: list[Behaviour] = []
    if cfg.intrusion.enabled:
        out.append(Intrusion())
    if cfg.loitering.enabled:
        out.append(Loitering(dwell_seconds=cfg.loitering.dwell_seconds))
    if cfg.running.enabled:
        out.append(Running(min_speed_hpersec=cfg.running.min_speed_hpersec,
                           window_seconds=cfg.running.window_seconds))
    if cfg.fall.enabled:
        out.append(Fall(horizontal_angle_deg=cfg.fall.horizontal_angle_deg,
                        down_seconds=cfg.fall.down_seconds))
    if cfg.fighting.enabled:
        out.append(Fighting(min_overlap_iou=cfg.fighting.min_overlap_iou,
                            min_motion_px=cfg.fighting.min_motion_px))
    if cfg.crowd_surge.enabled:
        out.append(CrowdSurge(max_people=cfg.crowd_surge.max_people))
    if cfg.unattended_object.enabled:
        out.append(UnattendedObject(
            stationary_seconds=cfg.unattended_object.stationary_seconds,
            abandon_distance_px=cfg.unattended_object.abandon_distance_px,
        ))
    return out


def pose_needed(cfg: BehaviourCfg) -> bool:
    return cfg.fall.enabled or cfg.fighting.enabled


def object_classes_needed(cfg: BehaviourCfg) -> list[int]:
    """COCO class ids for bag/backpack/suitcase/handbag."""
    if not cfg.unattended_object.enabled:
        return []
    # COCO: 24=backpack, 26=handbag, 28=suitcase (no generic 'bag')
    return [24, 26, 28]
