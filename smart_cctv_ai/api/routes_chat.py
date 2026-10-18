from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from ..agent.chat import ChatAgent
from ..config import Config

router = APIRouter(prefix="/chat")
_agent: ChatAgent | None = None
_cfg_cached: Config | None = None


def configure(cfg: Config) -> None:
    global _agent, _cfg_cached
    _cfg_cached = cfg
    if cfg.vlm.enabled:  # reuse the same Ollama model + url
        _agent = ChatAgent(model=cfg.vlm.model, ollama_url=cfg.vlm.ollama_url,
                           timeout_seconds=max(cfg.vlm.timeout_seconds, 20.0))


class AskBody(BaseModel):
    question: str


@router.post("")
def ask(body: AskBody):
    if _agent is None:
        return {"answer": "(chat offline: VLM/Ollama disabled in config.yaml)",
                "tool": None, "args": {}, "result": None}
    return _agent.ask(body.question)
