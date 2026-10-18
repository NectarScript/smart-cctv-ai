"""Single source of truth for the event contract.

Used by: SQLite storage, FastAPI responses, Telegram alerts, VLM prompts.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Column, JSON


class Severity(str, Enum):
    normal = "normal"
    suspicious = "suspicious"
    critical = "critical"


class BehaviourType(str, Enum):
    intrusion = "intrusion"
    loitering = "loitering"
    running = "running"
    fighting = "fighting"
    fall = "fall"
    unattended_object = "unattended_object"
    crowd_surge = "crowd_surge"


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)
    camera_id: str = Field(index=True)
    type: BehaviourType = Field(index=True)
    severity: Severity = Field(index=True)
    track_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    zone: Optional[str] = None
    start_ts: datetime = Field(index=True)
    end_ts: datetime
    snapshot: Optional[str] = None
    clip: Optional[str] = None
    vlm_verdict: Optional[str] = None
    vlm_summary: Optional[str] = None
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))


class EventRead(BaseModel):
    """Response model (no SQLModel session leakage)."""
    id: int
    camera_id: str
    type: BehaviourType
    severity: Severity
    track_ids: list[int]
    zone: Optional[str]
    start_ts: datetime
    end_ts: datetime
    snapshot: Optional[str]
    clip: Optional[str]
    vlm_verdict: Optional[str]
    vlm_summary: Optional[str]
    meta: dict
