"""Smart CCTV AI :: doctor
Pass/fail report. Prints human-readable to stdout and writes JSON to
logs/doctor.json. Never raises - every check is best-effort.
"""
from __future__ import annotations
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
report: dict = {"root": str(ROOT), "checks": []}


def check(name: str, fn):
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"exception: {e}"
    dur = round((time.time() - t0) * 1000)
    report["checks"].append({"name": name, "ok": bool(ok),
                             "detail": str(detail), "ms": dur})
    mark = "OK " if ok else "FAIL"
    print(f"[{mark}] {name:<28} {detail}  ({dur} ms)")


def c_python():
    v = sys.version_info
    return (v.major == 3 and v.minor == 11,
            f"python {v.major}.{v.minor}.{v.micro}")


def c_cuda():
    try:
        import torch  # type: ignore
    except Exception as e:
        return False, f"torch not importable: {e}"
    if not torch.cuda.is_available():
        return False, "torch.cuda.is_available() == False"
    name = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory // (1024 ** 2)
    return True, f"{name}  {vram} MiB VRAM  torch {torch.__version__}"


def c_ultralytics():
    try:
        import ultralytics  # type: ignore
        return True, f"ultralytics {ultralytics.__version__}"
    except Exception as e:
        return False, f"not importable: {e}"


def c_weights():
    det = ROOT / "models" / "yolo11n.pt"
    pose = ROOT / "models" / "yolo11n-pose.pt"
    parts = []
    parts.append("det=OK" if det.exists() else "det=MISSING")
    parts.append("pose=OK" if pose.exists() else "pose=MISSING")
    return (det.exists() and pose.exists()), ", ".join(parts)


def c_openclip():
    try:
        import open_clip  # type: ignore
        return True, f"open_clip {open_clip.__version__}"
    except Exception as e:
        return False, f"not importable: {e}"


def c_opencv():
    try:
        import cv2  # type: ignore
        return True, f"opencv {cv2.__version__}"
    except Exception as e:
        return False, f"not importable: {e}"


def c_ffmpeg():
    exe = shutil.which("ffmpeg")
    return (exe is not None, exe or "ffmpeg not on PATH")


def c_ollama():
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            data = json.loads(r.read().decode())
        models = [m.get("name") for m in data.get("models", [])]
        return True, f"ollama up, models={models}"
    except Exception as e:
        return False, f"ollama not reachable: {e}"


def c_telegram():
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not tok:
        return False, ".env missing TELEGRAM_BOT_TOKEN (M2 feature; OK for M1)"
    try:
        import urllib.request
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{tok}/getMe", timeout=5) as r:
            d = json.loads(r.read().decode())
        return bool(d.get("ok")), f"@{d.get('result', {}).get('username')}"
    except Exception as e:
        return False, f"telegram api failed: {e}"


def c_config():
    try:
        from smart_cctv_ai.config import load_config  # type: ignore
        cfg = load_config()
        return True, (f"{len(cfg.cameras)} camera(s), device={cfg.app.device}, "
                      f"port={cfg.app.port}")
    except Exception as e:
        return False, f"load_config failed: {e}"


def c_cameras():
    try:
        from smart_cctv_ai.config import load_config  # type: ignore
        import cv2  # type: ignore
    except Exception as e:
        return False, f"import failed: {e}"
    cfg = load_config()
    results = []
    for cam in cfg.cameras:
        src = cam.source
        if src.isdigit():
            cap = cv2.VideoCapture(int(src), cv2.CAP_DSHOW)
        elif src.startswith(("rtsp://", "http://", "https://")):
            cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        else:
            p = Path(src)
            if not p.exists():
                results.append(f"{cam.id}=MISSING({src})")
                continue
            cap = cv2.VideoCapture(p.as_posix())
        ok = cap.isOpened()
        cap.release()
        results.append(f"{cam.id}={'OK' if ok else 'FAIL'}")
    return all("=OK" in r for r in results), ", ".join(results) or "no cameras"


def c_port():
    port = 8000
    try:
        from smart_cctv_ai.config import load_config  # type: ignore
        port = load_config().app.port
    except Exception:
        pass
    s = socket.socket()
    try:
        s.settimeout(0.5)
        s.bind(("127.0.0.1", port))
        s.close()
        return True, f"port {port} free"
    except OSError:
        return False, f"port {port} already in use"


def c_frontend():
    p = ROOT / "frontend" / "dist" / "index.html"
    return p.exists(), str(p) if p.exists() else "frontend not built (run setup.bat)"


def c_disk():
    free = shutil.disk_usage(ROOT).free // (1024 ** 3)
    return free >= 2, f"{free} GiB free in {ROOT.anchor}"


def main() -> int:
    print(f"Smart CCTV AI :: doctor  ({ROOT})\n")
    for name, fn in [
        ("python-3.11", c_python),
        ("cuda-torch", c_cuda),
        ("ultralytics", c_ultralytics),
        ("open-clip", c_openclip),
        ("yolo-weights", c_weights),
        ("opencv", c_opencv),
        ("ffmpeg", c_ffmpeg),
        ("ollama", c_ollama),
        ("telegram", c_telegram),
        ("config.yaml", c_config),
        ("cameras", c_cameras),
        ("port-free", c_port),
        ("frontend-dist", c_frontend),
        ("disk-space", c_disk),
    ]:
        check(name, fn)

    (ROOT / "logs").mkdir(exist_ok=True)
    out = ROOT / "logs" / "doctor.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")

    # Non-blocking failures (M2 features): don't fail the overall exit code for them
    soft = {"ollama", "telegram", "yolo-weights", "frontend-dist", "open-clip"}
    hard_fail = any(not c["ok"] and c["name"] not in soft for c in report["checks"])
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
