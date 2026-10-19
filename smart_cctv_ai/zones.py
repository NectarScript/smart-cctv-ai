from __future__ import annotations
import numpy as np
from .config import ZoneCfg


class Zone:
    __slots__ = ("name", "polygon", "rules", "_poly_np")

    def __init__(self, cfg: ZoneCfg):
        self.name = cfg.name
        self.polygon = cfg.polygon
        self.rules = set(cfg.rules)
        self._poly_np = np.asarray(cfg.polygon, dtype=np.int32)

    def contains(self, x: float, y: float) -> bool:
        """Even-odd rule point-in-polygon. No OpenCV import to keep this testable."""
        poly = self._poly_np
        n = len(poly)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
                inside = not inside
            j = i
        return inside

    def contains_box(self, xyxy) -> bool:
        """Use bottom-center of the bbox as the ground point."""
        x1, y1, x2, y2 = xyxy
        return self.contains((x1 + x2) / 2.0, y2)

    @property
    def np_polygon(self) -> np.ndarray:
        return self._poly_np
