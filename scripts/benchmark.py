"""Performance benchmark.

Usage:
    python scripts/benchmark.py --input video.mp4 --frames 300
    python scripts/benchmark.py --source 0 --frames 200
"""
import argparse
import sys
import time
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import load_config
from src.core.constants import BehaviourLabel
from src.core.logger import setup_logging
from src.core.timer import PerfTimer
from src.detection.person_detector import PersonDetector
from src.detection.tracker import Tracker
from src.detection.track_store import TrackStore
from src.behaviour.pose_estimator import PoseEstimator
from src.behaviour.keypoint_buffer import KeypointBuffer
from src.behaviour.classifier import BehaviourClassifier
from src.ingestion.preprocessor import crop_bbox, preprocess_for_pose


def main():
    parser = argparse.ArgumentParser(description="Smart CCTV AI — Benchmark")
    parser.add_argument("--input", default=None, help="Video file path")
    parser.add_argument("--source", default=None, help="Camera index")
    parser.add_argument("--frames", type=int, default=300, help="Frames to process")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging("WARNING")

    source = args.input or (int(args.source) if args.source else 0)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Cannot open: {source}")
        return

    detector = PersonDetector(config.detection)
    tracker = Tracker(config.tracking)
    track_store = TrackStore()
    pose_est = PoseEstimator()
    kp_buffer = KeypointBuffer(config.behaviour.keypoint_window_size)
    classifier = BehaviourClassifier(config.behaviour)

    detector.warmup()

    t_detect = PerfTimer(window=args.frames)
    t_track = PerfTimer(window=args.frames)
    t_pose = PerfTimer(window=args.frames)
    t_classify = PerfTimer(window=args.frames)
    t_total = PerfTimer(window=args.frames)

    person_counts = []
    event_counts = defaultdict(int)

    print(f"Benchmarking on {source} for {args.frames} frames...")
    start = time.time()

    for i in range(args.frames):
        ret, frame = cap.read()
        if not ret:
            print(f"Video ended at frame {i}")
            break

        with t_total:
            with t_detect:
                detections = detector.detect(frame)

            with t_track:
                tracked = tracker.update(detections)

            track_store.update(tracked, "bench", time.time())
            n_persons = len(tracked) if tracked.tracker_id is not None else 0
            person_counts.append(n_persons)

            if tracked.tracker_id is not None:
                for j, tid in enumerate(tracked.tracker_id):
                    tid = int(tid)
                    crop = crop_bbox(frame, tracked.xyxy[j])
                    crop_rgb = preprocess_for_pose(crop)
                    with t_pose:
                        kp = pose_est.estimate(crop_rgb)
                    if kp is not None:
                        kp_buffer.push(tid, kp)

                    history = track_store.get(tid)
                    if history:
                        kp_seq = kp_buffer.get_sequence(tid)
                        active = track_store.get_active_tracks()
                        with t_classify:
                            event = classifier.classify(tid, history, kp_seq, active, time.time())
                        if event.label != BehaviourLabel.NORMAL:
                            event_counts[event.event_type.value] += 1

    elapsed = time.time() - start
    cap.release()
    pose_est.close()

    frames_done = len(person_counts)
    avg_persons = np.mean(person_counts) if person_counts else 0

    print(f"\n{'='*50}")
    print(f"  BENCHMARK RESULTS")
    print(f"{'='*50}")
    print(f"  Frames processed:     {frames_done}")
    print(f"  Total wall time:      {elapsed:.1f}s")
    print(f"  Overall FPS:          {frames_done / elapsed:.1f}")
    print(f"  Avg persons/frame:    {avg_persons:.1f}")
    print(f"")
    print(f"  --- Latency (avg ms) ---")
    print(f"  Detection (YOLO):     {t_detect.avg_ms:.1f}ms")
    print(f"  Tracking (ByteTrack): {t_track.avg_ms:.1f}ms")
    print(f"  Pose (MediaPipe):     {t_pose.avg_ms:.1f}ms  (per person)")
    print(f"  Classification:       {t_classify.avg_ms:.2f}ms (per person)")
    print(f"  Total pipeline:       {t_total.avg_ms:.1f}ms")
    print(f"  Pipeline FPS:         {t_total.fps:.1f}")
    print(f"")
    print(f"  --- Events ---")
    for etype, count in sorted(event_counts.items()):
        print(f"  {etype}: {count}")
    if not event_counts:
        print(f"  (none detected)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
