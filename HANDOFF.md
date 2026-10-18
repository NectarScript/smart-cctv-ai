# Smart CCTV AI — Handoff (dev PC → GPU PC)

## Who runs what
- **Dev PC** (no GPU): write code with Claude, `git push`. No pip/npm here.
- **GPU PC** (Windows 11, RTX 4050 6 GB, 16 GB RAM, Python 3.11): installs
  and runs everything via the four `.bat` scripts below.

## One-time setup on the GPU PC (Day 1, ~1 hour)
Install first (user must do these by hand):
1. NVIDIA driver (verify with `nvidia-smi`).
2. **Python 3.11** — tick *"Add to PATH"* during install.
3. **Git**.
4. **Node.js 20 LTS**.
5. **ffmpeg** — put on PATH.
6. (M2+) **Ollama** — https://ollama.com/download/windows.

Then:
```
git clone https://github.com/<org>/smart-cctv-ai.git
cd smart-cctv-ai
setup.bat
```
Expected: `=== setup OK ===` at the end. Takes 10–20 min on first run
(downloads torch-cuda wheels, YOLO weights, npm packages).

If it fails: send `logs\latest.log` and the last 40 lines of the console.

## Milestone 1 demo loop
```
run.bat
```
Expected console (within ~10 s):
```
Smart CCTV AI started on 0.0.0.0:8000
[cam1] opened: samples/intrusion.mp4
loading YOLO weights: models/yolo11n.pt (device=cuda)
```
Open **http://localhost:8000** (or `http://<gpu-pc-ip>:8000` from the dev PC
on the same network). Expected:
- Header shows "Smart CCTV AI · 1 camera".
- Live tile `Demo (sample video)` streams the clip with green boxes and the
  orange `restricted_A` polygon.
- When a person enters the zone: an **intrusion** event (orange) appears in
  the Events panel on the right with a snapshot.
- After 10 s of dwell inside the zone: a **loitering** event appears.

Stop with `Ctrl+C`.

## Everyday loop
On the dev PC:
```
git push
```
On the GPU PC:
```
update.bat      # git pull + reinstall deps/frontend only if changed
run.bat         # starts the backend again
doctor.bat      # pass/fail health report
```

### What to send back if it fails
Paste these into chat:
1. `logs\latest.log` (last ~80 lines are usually enough).
2. `logs\doctor.json` (produced by `doctor.bat`).
3. The console output of `run.bat` up to the error.
4. **Do not guess the fix.** Send logs; the dev PC side finds the root cause.

## Sample clips
`config.yaml` points `cam1` at `samples/intrusion.mp4`. Drop any short clip
with a person walking into frame there. The repo ignores `samples/*.mp4`
by design — copy clips in by hand.

## Configuration
- `config.yaml` — cameras, zones, thresholds. Edit freely; no code change
  needed to add a camera or a zone.
- `.env` — secrets. For M1 you only need `TELEGRAM_BOT_TOKEN` later (M2).
  `setup.bat` auto-copies `.env.example` → `.env` on first run.

## Known limitations (Milestone 1)
- Telegram alerts, VLM verification, pose-based rules (fighting / fall /
  running), event clips (vs snapshots), zone editor UI, CLIP search, and
  the chat agent are **M2–M3**. The pipeline keeps running without them.
- First `run.bat` is slow (~15 s): ultralytics compiles kernels on first
  CUDA call.
