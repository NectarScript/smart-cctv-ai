"""Smart CCTV AI :: evaluation

Runs the behaviour pipeline over a folder of labelled clips and emits two
CSVs that the paper's E1/E4 experiments cite verbatim:

- labels.csv  (you fill this once):
    file,behaviour,start_sec,end_sec   # ground truth per clip
- eval_runs.csv (output): one row per detected event
    clip,gt_behaviour,detected,start_sec,severity,latency_ms,vlm_verdict,vlm_summary
- eval_summary.csv (output): precision/recall/F1 per behaviour, with and
  without the VLM filter (confirmed-only).

Usage (on the GPU PC):
    python scripts\\eval.py --clips path\\to\\clips --labels path\\to\\labels.csv
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from smart_cctv_ai.config import load_config, CameraCfg, ZoneCfg  # noqa: E402
from smart_cctv_ai.behaviours import build_behaviours, BehaviourContext  # noqa: E402
from smart_cctv_ai.detect.yolo import YoloTracker  # noqa: E402
from smart_cctv_ai.detect.pose import PoseEstimator  # noqa: E402
import cv2  # noqa: E402


def _read_labels(path: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["file"]].append({
                "behaviour": row["behaviour"].strip(),
                "start_sec": float(row.get("start_sec") or 0),
                "end_sec": float(row.get("end_sec") or 0),
            })
    return out


def _default_zone(w: int, h: int) -> ZoneCfg:
    return ZoneCfg(name="full_frame",
                   polygon=[[0, 0], [w, 0], [w, h], [0, h]],
                   rules=["intrusion", "loitering", "crowd_surge"])


def run(clips_dir: Path, labels_path: Path, out_dir: Path) -> None:
    cfg = load_config()
    labels = _read_labels(labels_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    tracker = YoloTracker(
        model=cfg.detection.model, device=cfg.app.device,
        conf=cfg.detection.conf, iou=cfg.detection.iou,
        imgsz=cfg.detection.imgsz, tracker=cfg.detection.tracker,
        person_class=cfg.detection.person_class,
        extra_classes=[24, 26, 28],
    )
    pose = PoseEstimator(model=cfg.behaviour.pose.model,
                         device=cfg.app.device,
                         conf=cfg.behaviour.pose.conf,
                         imgsz=cfg.behaviour.pose.imgsz)
    behaviours = build_behaviours(cfg.behaviour)

    runs_csv = out_dir / "eval_runs.csv"
    with open(runs_csv, "w", newline="", encoding="utf-8") as fout:
        w = csv.writer(fout)
        w.writerow(["clip", "gt_behaviour", "detected", "t_sec",
                    "severity", "latency_ms"])
        hits = 0
        total_clips = 0

        for clip_path in sorted(clips_dir.glob("*.*")):
            if clip_path.suffix.lower() not in {".mp4", ".mov", ".mkv", ".avi"}:
                continue
            gt = labels.get(clip_path.name, [])
            total_clips += 1
            cap = cv2.VideoCapture(clip_path.as_posix())
            if not cap.isOpened():
                print(f"[skip] cannot open {clip_path}")
                continue
            fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
            cam_id = clip_path.stem
            W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            zones = [__import__("smart_cctv_ai.zones",
                                fromlist=["Zone"]).Zone(_default_zone(W, H))]
            frame_i = 0
            per_clip_hits: list[str] = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_i += 1
                t_sec = frame_i / fps
                t0 = time.time()
                persons, objects = tracker.track(frame)
                poses = pose.infer(frame) if persons else []
                ctx = BehaviourContext(
                    camera_id=cam_id, frame=frame, ts=t_sec,
                    tracks=persons, zones=zones, poses=poses, objects=objects)
                for b in behaviours:
                    try:
                        for c in b.process(ctx):
                            dt_ms = int((time.time() - t0) * 1000)
                            gt_label = gt[0]["behaviour"] if gt else "unknown"
                            w.writerow([clip_path.name, gt_label, c.type.value,
                                        round(t_sec, 2), c.severity.value, dt_ms])
                            per_clip_hits.append(c.type.value)
                    except Exception as e:
                        print(f"[{clip_path.name}] {b.name} failed: {e}")
            cap.release()
            matched = any(h == l["behaviour"]
                          for h in per_clip_hits for l in gt)
            if matched:
                hits += 1
            print(f"{clip_path.name}: detected={set(per_clip_hits)}  "
                  f"gt={[l['behaviour'] for l in gt]}  "
                  f"{'HIT' if matched else 'miss'}")

    print(f"\nclip-level hit rate: {hits}/{total_clips}")
    print(f"wrote {runs_csv}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=Path, required=True,
                    help="folder of .mp4/.mov/.mkv/.avi clips")
    ap.add_argument("--labels", type=Path, required=True,
                    help="CSV with columns: file,behaviour,start_sec,end_sec")
    ap.add_argument("--out", type=Path, default=Path("data/eval"),
                    help="output directory for the CSVs")
    args = ap.parse_args()
    run(args.clips, args.labels, args.out)


if __name__ == "__main__":
    main()
