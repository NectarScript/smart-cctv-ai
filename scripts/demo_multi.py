"""Multi-camera demo.

Usage:
    python scripts/demo_multi.py --config config/default.yaml
    python scripts/demo_multi.py --sources 0 1 video.mp4
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import AppConfig, CameraConfig, load_config
from src.core.constants import SourceType
from src.core.logger import setup_logging
from src.pipeline.orchestrator import Pipeline


def parse_source(source_str: str, idx: int):
    try:
        return CameraConfig(source_id=f"cam{idx}", source=int(source_str), source_type=SourceType.WEBCAM)
    except ValueError:
        pass
    if source_str.startswith("rtsp://"):
        return CameraConfig(source_id=f"cam{idx}", source=source_str, source_type=SourceType.RTSP)
    return CameraConfig(source_id=f"cam{idx}", source=source_str, source_type=SourceType.FILE)


def main():
    parser = argparse.ArgumentParser(description="Smart CCTV AI — Multi-Camera Demo")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--sources", nargs="+", help="Camera indices, paths, or RTSP URLs")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config.log_level)

    if args.sources:
        config.cameras = [parse_source(s, i) for i, s in enumerate(args.sources)]

    if not config.cameras:
        print("No cameras configured. Use --sources or --config.")
        return

    def on_events(events):
        for e in events:
            print(f"  [{e.label.value.upper()}] Cam:{e.camera_id} Track:{e.track_id} "
                  f"{e.event_type.value} ({e.confidence:.0%})")

    pipeline = Pipeline(config, on_events=on_events)
    print(f"Starting multi-camera demo with {len(config.cameras)} sources. Press 'q' to quit.")
    pipeline.run()


if __name__ == "__main__":
    main()
