import time
from src.core.timer import PerfTimer


def test_timer_basic():
    t = PerfTimer()
    with t:
        time.sleep(0.01)
    assert t.elapsed_ms > 5
    assert t.elapsed_ms < 100


def test_timer_history():
    t = PerfTimer(window=5)
    for _ in range(3):
        with t:
            time.sleep(0.005)
    assert t.avg_ms > 0
    assert t.fps > 0


def test_timer_fps():
    t = PerfTimer(window=10)
    for _ in range(5):
        with t:
            time.sleep(0.01)
    assert t.fps > 5
    assert t.fps < 200
