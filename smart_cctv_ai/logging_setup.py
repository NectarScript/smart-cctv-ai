from __future__ import annotations
from pathlib import Path
from loguru import logger
import sys

_CONFIGURED = False

def setup(level: str = "INFO", log_dir: Path | str = "logs") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=level, enqueue=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | "
                      "<cyan>{name}</cyan>: {message}")
    logger.add(log_path / "latest.log", level=level, enqueue=True, rotation="10 MB",
               retention=5, encoding="utf-8",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}: {message}")
    _CONFIGURED = True
