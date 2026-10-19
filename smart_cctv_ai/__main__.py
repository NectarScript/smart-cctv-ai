from __future__ import annotations
import uvicorn
from .config import load_config
from .logging_setup import setup as setup_logging


def main() -> None:
    cfg = load_config()
    setup_logging(cfg.app.log_level)
    uvicorn.run("smart_cctv_ai.api.app:app",
                host=cfg.app.host, port=cfg.app.port,
                log_level=cfg.app.log_level.lower(),
                reload=False)


if __name__ == "__main__":
    main()
