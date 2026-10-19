from __future__ import annotations
from pathlib import Path
from typing import Any
import os
import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class ZoneCfg(BaseModel):
    name: str
    polygon: list[list[int]]
    rules: list[str] = Field(default_factory=list)


class CameraCfg(BaseModel):
    id: str
    name: str = ""
    source: str
    fps: int = 15
    zones: list[ZoneCfg] = Field(default_factory=list)


class DetectionCfg(BaseModel):
    model: str = "yolo11n.pt"
    conf: float = 0.35
    iou: float = 0.5
    imgsz: int = 640
    tracker: str = "bytetrack.yaml"
    person_class: int = 0


class IntrusionCfg(BaseModel):
    enabled: bool = True


class LoiteringCfg(BaseModel):
    enabled: bool = True
    dwell_seconds: float = 10.0


class BehaviourCfg(BaseModel):
    cooldown_seconds: float = 20.0
    intrusion: IntrusionCfg = IntrusionCfg()
    loitering: LoiteringCfg = LoiteringCfg()


class AppCfg(BaseModel):
    name: str = "Smart CCTV AI"
    host: str = "0.0.0.0"
    port: int = 8000
    device: str = "auto"
    log_level: str = "INFO"


class TelegramCfg(BaseModel):
    enabled: bool = False
    chat_id: str = ""


class AlertsCfg(BaseModel):
    telegram: TelegramCfg = TelegramCfg()


class VlmCfg(BaseModel):
    enabled: bool = False
    model: str = "qwen2.5vl:3b"
    ollama_url: str = "http://127.0.0.1:11434"


class Config(BaseModel):
    app: AppCfg = AppCfg()
    detection: DetectionCfg = DetectionCfg()
    behaviour: BehaviourCfg = BehaviourCfg()
    cameras: list[CameraCfg] = Field(default_factory=list)
    alerts: AlertsCfg = AlertsCfg()
    vlm: VlmCfg = VlmCfg()

    # Secrets injected from .env, never from yaml
    telegram_bot_token: str = ""


def load_config(path: Path | str = "config.yaml") -> Config:
    load_dotenv()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {p.resolve()}")
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg = Config(**raw)
    cfg.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    env_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if env_chat:
        cfg.alerts.telegram.chat_id = env_chat
    env_dev = os.getenv("DEVICE", "")
    if env_dev:
        cfg.app.device = env_dev
    return cfg
