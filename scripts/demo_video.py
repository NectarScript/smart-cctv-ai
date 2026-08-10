"""Process a video file, write annotated output.

Usage:
    python scripts/demo_video.py --input video.mp4 --output annotated.mp4
    python scripts/demo_video.py --input video.mp4  # display only, no save
"""
import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import load_config
from src.core.constants import BehaviourLabel
from src.core.logger import setup_logging
from src.pipeline.orchestrator import Pipeline


def main():
    parser = argparse.ArgumentParser(description="Smart CCTV AI — Video Processing")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", default=None, help="Output video path")
    parser.add_argument("--config", default=None, help="Config YAML path")
    parser.add_argument("--show", action="store_true", default=True, help="Display output")
    parser.add_argument("--no-show", dest="show", action="store_false")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config.log_level)
    config.cameras = []

    pipeline = Pipeline(config)
    pipeline._detector.warmup()

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        print(f"Cannot open: {args.input}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    writer = None
    if args.output:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.output, fourcc, fps, (w, h))

    print(f"Processing: {args.input} ({total} frames, {fps:.0f} FPS, {w}x{h})")

    frame_count = 0
    all_events = []
    start = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        events, annotated = pipeline.process_single_frame(frame, camera_id="video")
        non_normal = [e for e in events if e.label != BehaviourLabel.NORMAL]
        all_events.extend(non_normal)

        if writer:
            writer.write(annotated)
        if args.show:
            cv2.imshow("Smart CCTV AI - Video", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        if frame_count % 100 == 0:
            elapsed = time.time() - start
            print(f"  Frame {frame_count}/{total} | "
                  f"FPS: {frame_count / elapsed:.1f} | "
                  f"Events: {len(all_events)}")

    elapsed = time.time() - start
    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
    pipeline._pose_estimator.close()

    print(f"\n=== Results ===")
    print(f"Frames processed: {frame_count}")
    print(f"Total time: {elapsed:.1f}s")
    print(f"Average FPS: {frame_count / elapsed:.1f}")
    print(f"Events detected: {len(all_events)}")

    event_types = {}
    for e in all_events:
        key = f"{e.event_type.value} ({e.label.value})"
        event_types[key] = event_types.get(key, 0) + 1
    for k, v in sorted(event_types.items()):
        print(f"  {k}: {v}")

    if args.output:
        print(f"Output saved: {args.output}")

    stats = pipeline.stats
    print(f"\nLatency breakdown:")
    print(f"  Detection: {stats['detect_ms']}ms")
    print(f"  Tracking:  {stats['track_ms']}ms")
    print(f"  Pose:      {stats['pose_ms']}ms")


if __name__ == "__main__":
    main()
