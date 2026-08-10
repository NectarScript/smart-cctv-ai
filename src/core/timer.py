import time
from collections import deque
from typing import Optional


class PerfTimer:
    def __init__(self, window: int = 60):
        self._start: Optional[float] = None
        self._elapsed: float = 0.0
        self._history: deque = deque(maxlen=window)

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self._elapsed = (time.perf_counter() - self._start) * 1000
        self._history.append(self._elapsed)
        self._start = None

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed

    @property
    def avg_ms(self) -> float:
        if not self._history:
            return 0.0
        return sum(self._history) / len(self._history)

    @property
    def fps(self) -> float:
        avg = self.avg_ms
        return 1000.0 / avg if avg > 0 else 0.0
