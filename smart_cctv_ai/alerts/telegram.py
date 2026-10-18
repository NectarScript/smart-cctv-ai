from __future__ import annotations
import threading
from pathlib import Path
from queue import Queue, Empty
from typing import Optional
import httpx
from loguru import logger
from ..schema import Event, Severity

_SEV_ORDER = {Severity.normal: 0, Severity.suspicious: 1, Severity.critical: 2}


class TelegramAlerter(threading.Thread):
    """Sends event alerts to Telegram in a worker thread.

    Fails open: a missing token, missing chat id, or network failure never
    blocks the pipeline. Snapshot sends first (fast), then clip once ready.
    """

    def __init__(self, token: str, chat_id: str, min_severity: str = "suspicious"):
        super().__init__(daemon=True, name="telegram-alerter")
        self.token = token.strip()
        self.chat_id = chat_id.strip()
        self.min = _SEV_ORDER.get(Severity(min_severity), 1)
        self._q: Queue = Queue()
        self._stop = threading.Event()
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            logger.warning("Telegram alerter disabled (missing token or chat_id)")

    def submit_event(self, ev: Event) -> None:
        if not self.enabled:
            return
        if _SEV_ORDER[ev.severity] < self.min:
            return
        self._q.put(("event", ev))

    def submit_clip(self, event_id: int, clip_path: Path) -> None:
        if not self.enabled:
            return
        self._q.put(("clip", event_id, clip_path))

    def stop(self) -> None:
        self._stop.set()
        self._q.put(("stop",))

    def run(self) -> None:
        if not self.enabled:
            return
        with httpx.Client(timeout=15.0) as client:
            while not self._stop.is_set():
                try:
                    msg = self._q.get(timeout=1.0)
                except Empty:
                    continue
                try:
                    kind = msg[0]
                    if kind == "stop":
                        break
                    if kind == "event":
                        self._send_event(client, msg[1])
                    elif kind == "clip":
                        self._send_clip(client, msg[1], msg[2])
                except Exception as e:
                    logger.error(f"telegram send failed: {e}")

    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    def _send_event(self, client: httpx.Client, ev: Event) -> None:
        emoji = {"normal": "ℹ️", "suspicious": "⚠️", "critical": "🚨"}[ev.severity.value]
        text = (f"{emoji} <b>{ev.severity.value.upper()}</b> "
                f"<i>{ev.type.value}</i>\n"
                f"camera: <b>{ev.camera_id}</b>")
        if ev.zone:
            text += f"\nzone: <b>{ev.zone}</b>"
        if ev.vlm_summary:
            text += f"\n\n{ev.vlm_summary}"
        if ev.snapshot and Path(ev.snapshot).exists():
            with open(ev.snapshot, "rb") as f:
                r = client.post(self._api("sendPhoto"),
                                data={"chat_id": self.chat_id,
                                      "caption": text, "parse_mode": "HTML"},
                                files={"photo": ("snap.jpg", f, "image/jpeg")})
            r.raise_for_status()
        else:
            r = client.post(self._api("sendMessage"),
                            data={"chat_id": self.chat_id,
                                  "text": text, "parse_mode": "HTML"})
            r.raise_for_status()

    def _send_clip(self, client: httpx.Client, event_id: int,
                   clip_path: Path) -> None:
        if not clip_path.exists():
            return
        with open(clip_path, "rb") as f:
            r = client.post(self._api("sendVideo"),
                            data={"chat_id": self.chat_id,
                                  "caption": f"clip · event #{event_id}"},
                            files={"video": (clip_path.name, f, "video/mp4")})
        r.raise_for_status()
