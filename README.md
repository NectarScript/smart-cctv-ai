# Smart CCTV AI

Intelligent multi-camera surveillance platform with real-time person detection, behaviour analysis, and alert generation.

## Phase 1 — Core AI Pipeline (M1 + M2 + M3)

### Architecture

```
Camera Sources → M1 Ingestion → M2 Detection+Tracking → M3 Behaviour Classification → Events
     ↓                ↓                  ↓                        ↓
  webcam/RTSP     Frame Queue     YOLOv8n + ByteTrack    MediaPipe Pose + Rules
  /video file     (threaded)       Person tracking        Normal/Suspicious/Critical
```

### Modules

| Module | Responsibility | Key Tech |
|--------|---------------|----------|
| M1 — Ingestion | Multi-camera capture, frame queuing | OpenCV, threading |
| M2 — Detection | Person detection + persistent tracking | YOLOv8n, ByteTrack (supervision) |
| M3 — Classification | Pose-based behaviour analysis | MediaPipe, rule-based heuristics |

### Detected Events

| Event | Reliability | Method |
|-------|------------|--------|
| Loitering | HIGH | Centroid displacement over time |
| Sudden Running | HIGH | Velocity spike detection |
| Fighting | MEDIUM | Proximity + rapid limb movement |
| Crowd Surge | MEDIUM | Track density threshold |
| Theft Posture | LOW (experimental) | Crouching + reaching heuristic |

## Quick Start

### Prerequisites

- Python 3.10–3.12 (3.11 recommended)
- Conda or venv
- Webcam (optional — works with video files too)

### Option A: Conda (recommended)

```bash
conda create -n smartcctv python=3.11 -y
conda activate smartcctv
pip install -r requirements.txt
```

### Option B: venv

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
pip install -r requirements.txt
```

### Verify Installation

```bash
# Check all dependencies load
python -c "import cv2, ultralytics, supervision, mediapipe, torch; print('All OK')"

# Run test suite (30 tests, no GPU needed)
pytest tests/ -v
```

## Usage

### Single camera (webcam)
```bash
python scripts/demo_single.py --source 0
```

### Video file
```bash
python scripts/demo_video.py --input path/to/video.mp4 --show
# Save annotated output:
python scripts/demo_video.py --input video.mp4 --output annotated.mp4
```

### Multi-camera
```bash
python scripts/demo_multi.py --sources 0 1 video.mp4
```

### Benchmark
```bash
python scripts/benchmark.py --input video.mp4 --frames 300
```

Press `q` to quit any demo window.

### Tests
```bash
pytest tests/ -v
```

## Configuration

Edit `config/default.yaml` to adjust detection thresholds, tracking parameters, and behaviour rules.

## Project Structure

```
src/
├── core/           # Config, types, constants, logging, timer
├── ingestion/      # M1: CameraSource, CameraManager, preprocessor
├── detection/      # M2: PersonDetector, Tracker, TrackStore
├── behaviour/      # M3: PoseEstimator, KeypointBuffer, RuleBasedClassifier
├── pipeline/       # Orchestrator (M1→M2→M3)
└── visualization/  # Renderer, Display
```

## Planned (Phase 2+)

- M4: Face recognition (FaceNet/DeepFace)
- M5: Backend API, RBAC, cloud deployment
- M6: Web dashboard, analytics, mobile alerts
