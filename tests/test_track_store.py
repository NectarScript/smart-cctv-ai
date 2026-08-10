import time
import numpy as np
import supervision as sv
from src.detection.track_store import TrackStore


def _make_detections(bboxes, track_ids):
    xyxy = np.array(bboxes, dtype=np.float32)
    d = sv.Detections(
        xyxy=xyxy,
        confidence=np.ones(len(xyxy)),
        class_id=np.zeros(len(xyxy), dtype=int),
    )
    d.tracker_id = np.array(track_ids, dtype=int)
    return d


def test_update_creates_tracks():
    store = TrackStore()
    det = _make_detections([[10, 10, 50, 50]], [1])
    store.update(det, "cam0", time.time())
    assert store.track_count == 1
    t = store.get(1)
    assert t is not None
    assert len(t.centroids) == 1


def test_velocity_computation():
    store = TrackStore()
    ts = time.time()
    for i in range(10):
        det = _make_detections([[i * 10, 0, i * 10 + 40, 40]], [1])
        store.update(det, "cam0", ts + i * 0.04)
    vel = store.get_velocity(1, window=5)
    assert vel is not None
    assert vel > 0


def test_displacement():
    store = TrackStore()
    ts = time.time()
    det1 = _make_detections([[0, 0, 40, 40]], [1])
    store.update(det1, "cam0", ts)
    det2 = _make_detections([[100, 0, 140, 40]], [1])
    store.update(det2, "cam0", ts + 1)
    disp = store.get_displacement(1)
    assert disp is not None
    assert disp > 90


def test_prune_stale():
    store = TrackStore()
    old_time = time.time() - 20
    det = _make_detections([[0, 0, 40, 40]], [99])
    store.update(det, "cam0", old_time)
    pruned = store.prune_stale(max_age=10.0)
    assert pruned == 1
    assert store.get(99) is None


def test_active_tracks():
    store = TrackStore()
    now = time.time()
    det = _make_detections([[0, 0, 40, 40], [100, 100, 140, 140]], [1, 2])
    store.update(det, "cam0", now)
    active = store.get_active_tracks(stale_threshold=2.0)
    assert len(active) == 2
