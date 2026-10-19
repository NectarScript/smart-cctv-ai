# Smart CCTV AI

Agentic, privacy-aware, multi-camera CCTV platform. Detects suspicious
behaviour, verifies with a local vision-language model, pushes a Telegram
alert with clip + plain-English summary, and answers "what happened at
Gate 2 in the last hour?" on demand.

Final-year college project · 5-day rebuild · 100% local, no paid APIs.

## Credits / prior art
Inspiration only, re-implemented from scratch in our own code:
- **clearcam** (GPL-3.0): NVR, draw-a-zone alerts, AI notification summaries.
  https://github.com/roryclear/clearcam
- **DeepCamera** (MIT): pluggable skills, hardware auto-detect, chat agent.
  https://github.com/SharpAI/DeepCamera

## Status — Milestone 1 (Day 1)
- Multi-camera manager (file / webcam / RTSP / IP Webcam), threaded, auto-reconnect
- YOLO11n detection + ByteTrack via Ultralytics
- Polygon zones; `intrusion` + `loitering` behaviour plugins
- SQLite event log with snapshot per event
- FastAPI backend: `/stream/{cam}` (MJPEG), `/cameras`, `/events`, `/healthz`
- React + Vite + Tailwind dashboard (dark): live feed grid + event list
- `setup.bat` / `update.bat` / `run.bat` / `doctor.bat` for the GPU PC

## Quick start (GPU PC — Windows 11, RTX 4050, Python 3.11)
```
git clone <this repo>
cd smart-cctv-ai
setup.bat          # one-time: venv, torch(cuda), deps, YOLO weights, dashboard build
run.bat            # starts backend + pipeline on http://<pc-ip>:8000
doctor.bat         # pass/fail health report → logs/doctor.json
```

The dev PC (no GPU) only writes code; nothing is installed or run there.
See `HANDOFF.md` for the full remote workflow.

## Layout
```
smart_cctv_ai/         # Python package
  camera/ detect/ behaviours/ alerts/ api/
  pipeline.py schema.py config.py db.py zones.py
frontend/              # React + Vite + Tailwind dashboard
scripts/doctor.py      # health report
config.yaml            # cameras, zones, thresholds (edit this)
.env.example           # secrets template (TELEGRAM_BOT_TOKEN)
samples/               # test clips (drop your own)
data/clips/            # event snapshots + clips (runtime)
logs/                  # loguru output + doctor.json
```

## Event schema (single source of truth)
Defined once in `smart_cctv_ai/schema.py`:
`id, camera_id, type, severity, track_ids, zone, start_ts, end_ts,
snapshot, clip, vlm_verdict, vlm_summary, meta`.

## Licence
Project source: AGPL-3.0 (Ultralytics dependency). Keep the repo public at
submission, or declare the licence.
