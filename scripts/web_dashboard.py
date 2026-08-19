"""Web dashboard for Smart CCTV AI.

Usage:
    python scripts/web_dashboard.py                     # webcam 0
    python scripts/web_dashboard.py --source 1           # webcam 1
    python scripts/web_dashboard.py --source video.mp4   # video file
    python scripts/web_dashboard.py --port 5000          # custom port

Open http://localhost:8080 in your browser.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import AppConfig, CameraConfig, load_config
from src.core.constants import SourceType
from src.core.logger import setup_logging


def parse_source(source_str: str):
    try:
        return int(source_str), SourceType.WEBCAM
    except ValueError:
        pass
    if source_str.startswith("rtsp://"):
        return source_str, SourceType.RTSP
    return source_str, SourceType.FILE


def main():
    parser = argparse.ArgumentParser(description="Smart CCTV AI — Web Dashboard")
    parser.add_argument("--source", default="0", help="Camera index, video path, or RTSP URL")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config.log_level)

    source, source_type = parse_source(args.source)
    config.cameras = [CameraConfig(
        source_id="cam0",
        source=source,
        source_type=source_type,
    )]

    from src.web.app import create_app
    app = create_app(config)

    print(f"\n  Smart CCTV AI Dashboard")
    print(f"  http://localhost:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
