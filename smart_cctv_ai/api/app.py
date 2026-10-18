from __future__ import annotations
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger

from .. import db
from ..alerts.telegram import TelegramAlerter
from ..alerts.vlm import VlmVerifier
from ..config import Config, load_config
from ..logging_setup import setup as setup_logging
from ..pipeline import Pipeline
from . import stream as stream_mod
from .routes_events import router as events_router

_pipeline: Pipeline | None = None
_cfg: Config | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline, _cfg
    _cfg = load_config()
    setup_logging(_cfg.app.log_level)
    db.init()
    _pipeline = Pipeline(_cfg)
    stream_mod.set_pipeline(_pipeline)

    if _cfg.alerts.telegram.enabled:
        tg = TelegramAlerter(
            token=_cfg.telegram_bot_token,
            chat_id=_cfg.alerts.telegram.chat_id,
            min_severity=_cfg.alerts.telegram.min_severity,
        )
        if tg.enabled:
            tg.start()
            _pipeline.telegram = tg

    if _cfg.vlm.enabled:
        vlm = VlmVerifier(
            model=_cfg.vlm.model,
            ollama_url=_cfg.vlm.ollama_url,
            timeout_seconds=_cfg.vlm.timeout_seconds,
            verify_min_severity=_cfg.vlm.verify_min_severity,
            on_result=_pipeline.update_vlm,
        )
        vlm.start()
        _pipeline.vlm = vlm

    _pipeline.start()
    logger.info(f"{_cfg.app.name} started on {_cfg.app.host}:{_cfg.app.port}")
    try:
        yield
    finally:
        if _pipeline is not None:
            _pipeline.stop()
        logger.info("shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Smart CCTV AI", version="0.1.0", lifespan=lifespan)
    app.include_router(stream_mod.router)
    app.include_router(events_router)

    @app.get("/healthz")
    def healthz():
        if _pipeline is None:
            return JSONResponse({"ok": False, "reason": "pipeline not started"}, 503)
        return {
            "ok": True,
            "cameras": _pipeline.cams.status(),
            "telegram": bool(_pipeline.telegram and _pipeline.telegram.enabled),
            "vlm": _pipeline.vlm is not None,
            "recorder": _pipeline.recorder is not None,
            "pose": _pipeline.pose is not None,
        }

    # Static: frontend build (built by setup.bat / update.bat on friend's PC)
    dist = Path("frontend/dist")
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            # SPA fallback — don't eat API routes (they're mounted above)
            target = dist / full_path
            if target.is_file():
                return FileResponse(target)
            return FileResponse(dist / "index.html")
    else:
        @app.get("/")
        def dev_notice():
            return JSONResponse({
                "ok": True,
                "message": "Smart CCTV AI backend running. "
                           "Frontend not built yet — run setup.bat / update.bat.",
                "api": ["/healthz", "/cameras", "/events", "/stream/{camera_id}"],
            })
    return app


app = create_app()
