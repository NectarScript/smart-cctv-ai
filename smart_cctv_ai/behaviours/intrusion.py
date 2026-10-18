from __future__ import annotations
from typing import Iterable
from .base import Behaviour, BehaviourContext, Candidate
from ..schema import BehaviourType, Severity


class Intrusion(Behaviour):
    """Fire once per (track, zone) when a person enters a zone with 'intrusion' rule.

    The pipeline-level cooldown prevents repeat spam while the track stays inside.
    """
    name = "intrusion"

    def process(self, ctx: BehaviourContext) -> Iterable[Candidate]:
        out: list[Candidate] = []
        for z in ctx.zones:
            if self.name not in z.rules:
                continue
            for t in ctx.tracks:
                if z.contains_box(t.xyxy):
                    out.append(Candidate(
                        type=BehaviourType.intrusion,
                        severity=Severity.suspicious,
                        track_ids=[t.track_id],
                        zone=z.name,
                        meta={"bbox": list(t.xyxy)},
                    ))
        return out
