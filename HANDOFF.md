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
- First `run.bat` is slow (~15 s): ultralytics compiles kernels on first
  CUDA call.

## Milestone 2 — Day 2 (branch `m2/day2`)
On top of M1, this branch adds:
- **Pose** via `yolo11n-pose.pt` (runs every Nth frame when ≥1 person present).
- **Rules**: `running`, `fall`, `fighting`, `crowd_surge`, `unattended_object`.
- **Clip recorder**: 4 s pre + 6 s post event, written as `.mp4` into
  `data/clips/`. Served at `GET /events/{id}/clip` (dashboard shows a video player).
- **Telegram alerts**: snapshot sent immediately, clip sent when ready.
  Enable: fill `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.
  Alerter is a worker thread and never blocks the pipeline.
- **VLM verification** via local Ollama (`qwen2.5vl:3b`): on Suspicious/Critical
  events a short JSON `{verdict, summary}` is written back to the event and shown
  in the dashboard. Timeout 10 s, fails open.
- **Dashboard header** now shows live pose / recorder / telegram / vlm badges.
- **config.yaml**: new `recorder:` block, new `behaviour.*` thresholds,
  `alerts.telegram.*`, `vlm.*`.

### Day 2 extra setup on the GPU PC
Pose weights are pulled by `setup.bat` (just re-run it, or let ultralytics
auto-download on first run). For VLM:
```
ollama pull qwen2.5vl:3b
ollama serve      # usually runs automatically on Windows after install
```
For Telegram alerts:
1. Message @BotFather, create a bot, grab the token.
2. Add the bot to a group, send a message there.
3. `curl https://api.telegram.org/bot<TOKEN>/getUpdates` → chat.id.
4. Put both into `.env`:
   ```
   TELEGRAM_BOT_TOKEN=1234:ABC...
   TELEGRAM_CHAT_ID=-100xxxxxxxxxx
   ```

### Expected on `run.bat` for M2
Console lines (within ~20 s):
```
loading YOLO weights: models/yolo11n.pt (device=cuda)
loading YOLO-pose weights: models/yolo11n-pose.pt (device=cuda)
Smart CCTV AI started on 0.0.0.0:8000
```
Dashboard header shows `● pose · ● recorder · ● telegram · ● vlm` when all
features are up. A fall / fight event should land in the Events panel with:
- an inline MP4 player (clip),
- an italic VLM one-liner above it.
Your Telegram group gets the snapshot immediately and the clip when it's
done writing (~6 s later).

## Milestone 3 — Day 3 (branch `m3/day3`)
On top of M2, this branch adds:
- **CLIP semantic search** over event snapshots: `GET /search?q=red+backpack`
  (open_clip ViT-B/32; embeddings cached in `data/clip_index.npz`).
- **Ask-your-cameras chat agent**: `POST /chat {question}` — the same local
  Ollama model picks one of `count_events / list_events / get_event /
  search_events`, runs it against SQLite, and summarises the result in a
  sentence.
- **Analytics**: `GET /stats?hours=24` returns per-hour / per-type /
  per-camera / per-severity counts. New Analytics tab in the dashboard shows
  bar charts (no chart lib, pure CSS).
- **Privacy mode**: `GET/POST /privacy {enabled}`. Blurs the head region of
  every detected person on the live stream, saved snapshots and clips.
  Toggle button in the header.
- **Evaluation script** `scripts/eval.py` (for Day 4): runs the whole
  behaviour engine over a folder of labelled clips and dumps a CSV the paper
  cites verbatim.

### Day 3 extra deps
`setup.bat` installs `open-clip-torch` + its tokenizer deps automatically on
`update.bat`. First `/search` call downloads the CLIP weights (~340 MB, one
time); after that it is offline.

### Expected on `run.bat` for M3
Dashboard header has new buttons: **Live / Analytics / Privacy**. The chat
box lives on the Live tab under the camera grid. The Analytics tab shows
the stats panel on the left and the CLIP search panel on the right.

Try these to verify:
- Chat: *"how many intrusions in the last hour?"* — single-sentence answer.
- Search: *"person with backpack"* — grid of matching event snapshots.
- Privacy ON: live feed shows blurred head regions on every bbox.
