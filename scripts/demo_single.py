"""Single-camera demo.

Usage:
    python scripts/demo_single.py                     # webcam 0
    python scripts/demo_single.py --source 1           # webcam 1
    python scripts/demo_single.py --source video.mp4   # video file
    python scripts/demo_single.py --source rtsp://...  # RTSP stream
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import AppConfig, CameraConfig, load_config
from src.core.constants import SourceType, BehaviourLabel
from src.core.logger import setup_logging
from src.pipeline.orchestrator import Pipeline


def parse_source(source_str: str):
    try:
        return int(source_str), SourceType.WEBCAM
    except ValueError:
        pass
    if source_str.startswith("rtsp://") or source_str.startswith("rtsp:"):
        return source_str, SourceType.RTSP
    return source_str, SourceType.FILE


def main():
    parser = argparse.ArgumentParser(description="Smart CCTV AI — Single Camera Demo")
    parser.add_argument("--source", default="0", help="Camera index, video path, or RTSP URL")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--confidence", type=float, default=None, help="Detection confidence")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config.log_level)

    source, source_type = parse_source(args.source)
    config.cameras = [CameraConfig(
        source_id="cam0",
        source=source,
        source_type=source_type,
    )]

    if args.confidence:
        config.detection.confidence_threshold = args.confidence

    def on_events(events):
        for e in events:
            print(f"  [{e.label.value.upper()}] Track {e.track_id}: "
                  f"{e.event_type.value} (conf={e.confidence:.0%})")

    pipeline = Pipeline(config, on_events=on_events)
    print("Starting single-camera demo. Press 'q' to quit.")
    pipeline.run()


if __name__ == "__main__":
    main()
