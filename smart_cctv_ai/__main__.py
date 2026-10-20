from __future__ import annotations
import socket
import threading
import time
import webbrowser
import uvicorn
from .config import load_config
from .logging_setup import setup as setup_logging


def _local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _open_when_ready(url: str, port: int) -> None:
    """Wait until the server actually accepts a TCP connection, then open browser."""
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.5)
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass


def main() -> None:
    cfg = load_config()
    setup_logging(cfg.app.log_level)

    port = cfg.app.port
    lan_ip = _local_ip()
    url = f"http://127.0.0.1:{port}"
    print()
    print("  ==================================================")
    print(f"  Smart CCTV AI running — open in your browser:")
    print(f"     {url}")
    print(f"     http://localhost:{port}")
    print(f"     http://{lan_ip}:{port}       (from phone / other PCs)")
    print("  ==================================================")
    print()

    threading.Thread(target=_open_when_ready, args=(url, port),
                     daemon=True).start()

    uvicorn.run("smart_cctv_ai.api.app:app",
                host=cfg.app.host, port=port,
                log_level=cfg.app.log_level.lower(),
                reload=False)


if __name__ == "__main__":
    main()
