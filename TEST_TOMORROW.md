# Smart CCTV AI — One-page test guide (GPU PC)

**Target branch:** `m3/day3` (contains everything from M1 + M2 + M3). Tagged `v0.3`.
Fallback: `m1/fresh-rebuild`.

**Target:** HP OMEN — NVIDIA RTX 4050 Laptop 6 GB (Ada) · Windows 11 · Python 3.11.9.
Also tested on RTX 5050 Laptop 8 GB (Blackwell).

**Any other NVIDIA GPU?** `setup.bat` auto-detects:
- RTX 50-series → torch 2.7.0 + cu128
- RTX 40 / 30 / 20 → torch 2.5.1 + cu121
- No NVIDIA GPU → set `app.device: "cpu"` in `config.yaml`, no reinstall needed.

## 0. Prereqs — one command (installs Python 3.11, Git, Node 20, ffmpeg, Ollama)
In the repo folder, run:
```
.\prereqs.bat
```
It uses `winget` under the hood — no manual clicking. Then close + reopen
PowerShell so new PATH entries land. The only thing you must install by
hand is the NVIDIA driver; verify with `nvidia-smi`.

Manual fallback if winget isn't available (very old Windows 10):
- NVIDIA driver (verify with `nvidia-smi`)
- Python 3.11.9 — tick *Add to PATH* + *py launcher*: https://www.python.org/downloads/release/python-3119/
- Git: https://git-scm.com/download/win
- Node 20 LTS: https://nodejs.org
- ffmpeg: https://www.gyan.dev/ffmpeg/builds/ (add `bin\` to PATH)
- (optional) Ollama: https://ollama.com/download/windows

## 1. Clone + checkout the latest branch
```
cd %USERPROFILE%\Documents
git clone https://github.com/NectarScript/smart-cctv-ai.git
cd smart-cctv-ai
git checkout m3/day3
```

## 2. One-time setup (10–20 min, downloads torch-cuda + YOLO + CLIP)
```
setup.bat
```
Expected final line: `=== setup OK ===`.
If it stops with `[ERR]`, send me the last ~30 console lines + `logs\latest.log`.

## 3. Give it something to detect
Pick **one** of these two options:

### Option A — sample video (fastest demo)
Put any short MP4 with a person walking at:
```
samples\intrusion.mp4
```
Any clip works (10–60 s, person visible). If you have UCF-Crime or a phone video, perfect.

### Option B — webcam (zero downloads)
Open `config.yaml`, under the `cameras:` block change this one line:
```yaml
    source: "samples/intrusion.mp4"
```
to:
```yaml
    source: "0"
```
Then stand in front of the webcam. The orange zone in the config covers the middle of the frame, so walking into frame fires `intrusion`.

## 4. Run
```
run.bat
```
Expected console within ~15 s:
```
loading YOLO weights: models/yolo11n.pt (device=cuda)
loading YOLO-pose weights: models/yolo11n-pose.pt (device=cuda)
Smart CCTV AI started on 0.0.0.0:8000
```
Open **http://localhost:8000** in a browser (or `http://<this-pc-ip>:8000` from my laptop).

## 5. What you should see
- Header `Smart CCTV AI v0.3 · M3` with four badges: pose · rec · tg · vlm
  - `pose` and `rec` should be **green** if everything is working
  - `tg` goes green only when you fill `TELEGRAM_BOT_TOKEN`+`TELEGRAM_CHAT_ID` in `.env`
  - `vlm` goes green only when Ollama is running + `qwen2.5vl:3b` is pulled
- A live tile `Demo (sample video)` with green person boxes + an orange zone polygon
- Enter the zone → an **intrusion** event appears in the right-hand Events list within ~1 s, with a snapshot
- Stay in the zone for 10 s → a **loitering** event (suspicious)
- Walk fast → a **running** event
- Click the **Analytics** tab → charts of events in the last 24 h + CLIP search
- Click the **Privacy OFF** button → it flips to ON and heads blur on the live view

Stop with `Ctrl+C`.

## 6. Health report
After running `run.bat` at least once, run:
```
doctor.bat
```
It writes `logs\doctor.json` and prints a pass/fail table. **Send me that file.**

## 7. What to send me after you test
Paste in chat (or send as a WhatsApp attachment):
1. `logs\doctor.json`
2. The last ~80 lines of `logs\latest.log`
3. A screenshot of the dashboard (optional but nice)
4. Anything that looked wrong: wrong detections, slow FPS, crashes

That's it — I'll do the fixing from the logs.

## FAQ / common gotchas

**`nvidia-smi` says CUDA 12.x, but `setup.bat` fails on torch install.**
Try CUDA 11.8 wheels instead. Edit `setup.bat` line that reads
`--index-url https://download.pytorch.org/whl/cu121` → `cu118`, and rerun.

**`CUDA error: no kernel image is available for execution on the device`.**
Your GPU gen isn't matched by the installed torch build. Likely a new RTX
50-series. Fix:
```powershell
Remove-Item -Recurse -Force .venv
.\setup.bat
```
Latest `setup.bat` auto-detects RTX 50 and installs the cu128 wheels.

**`run.bat` crashes with "address already in use".**
Port 8000 is taken. Edit `config.yaml` → `app.port: 8001` (or any free port).

**No CUDA at all.**
Edit `config.yaml` → `app.device: "cpu"`. Everything runs, just slower (~5 fps instead of 20+).

**Ollama not installed / chat and VLM badges stay grey.**
Fine for M1–M2 demo. If you want them: install Ollama, run `ollama pull qwen2.5vl:3b`,
restart `run.bat`.

**Firewall blocks my laptop opening http://<this-pc-ip>:8000.**
On the GPU PC, Windows Defender Firewall → Allow an app → add Python 3.11
and both private + public networks (or temporarily disable firewall for the demo).

**Dashboard loads but `No cameras configured`.**
Pipeline hasn't started yet (first ~10 s), or your `source:` path is wrong. Check `logs\latest.log`.
