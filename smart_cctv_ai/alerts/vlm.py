from __future__ import annotations
import base64
import threading
from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Optional
import httpx
from loguru import logger
from ..schema import Event, Severity

_SEV_ORDER = {Severity.normal: 0, Severity.suspicious: 1, Severity.critical: 2}

_PROMPT = (
    "You are a CCTV reviewer. Look at the attached frames from a surveillance "
    "camera. A rule-based system flagged a '{event_type}' event in zone "
    "'{zone}'. In 1 short sentence, confirm or reject the alert and describe "
    "what you actually see. "
    'Reply strictly as JSON: {{"verdict": "confirmed" | "rejected", "summary": "<one sentence>"}}'
)


class VlmVerifier(threading.Thread):
    """Posts snapshots to a local Ollama VLM; writes verdict + summary back.

    Fails open: ollama down or timeout → event stays as-is with a short note.
    """

    def __init__(self, model: str, ollama_url: str,
                 timeout_seconds: float,
                 verify_min_severity: str,
                 on_result: Callable[[int, str, str], None]):
        super().__init__(daemon=True, name="vlm-verifier")
        self.model = model
        self.url = ollama_url.rstrip("/")
        self.timeout = timeout_seconds
        self.min = _SEV_ORDER.get(Severity(verify_min_severity), 1)
        self._q: Queue = Queue()
        self._stop = threading.Event()
        self._on_result = on_result

    def submit(self, ev: Event) -> None:
        if _SEV_ORDER[ev.severity] < self.min:
            return
        if not ev.snapshot or not Path(ev.snapshot).exists():
            return
        self._q.put(ev)

    def stop(self) -> None:
        self._stop.set()
        self._q.put(None)

    def run(self) -> None:
        with httpx.Client(timeout=self.timeout) as client:
            while not self._stop.is_set():
                try:
                    ev = self._q.get(timeout=1.0)
                except Empty:
                    continue
                if ev is None:
                    break
                try:
                    verdict, summary = self._ask(client, ev)
                    self._on_result(ev.id, verdict, summary)
                except Exception as e:
                    logger.warning(f"VLM verify failed for #{ev.id}: {e}")

    def _ask(self, client: httpx.Client, ev: Event) -> tuple[str, str]:
        img_bytes = Path(ev.snapshot).read_bytes()
        b64 = base64.b64encode(img_bytes).decode()
        prompt = _PROMPT.format(event_type=ev.type.value, zone=ev.zone or "n/a")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        r = client.post(f"{self.url}/api/generate", json=payload)
        r.raise_for_status()
        text = r.json().get("response", "").strip()
        verdict, summary = _parse(text)
        logger.info(f"VLM #{ev.id} {ev.type.value}: {verdict} — {summary}")
        return verdict, summary


def _parse(text: str) -> tuple[str, str]:
    """Best-effort JSON extraction from VLM output."""
    import json, re
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(0))
            v = str(d.get("verdict", "")).lower()
            s = str(d.get("summary", "")).strip()
            if v in ("confirmed", "rejected") and s:
                return v, s
        except Exception:
            pass
    # Fallback: treat raw text as summary, no verdict
    return "unverified", (text[:280] or "(empty VLM response)")
