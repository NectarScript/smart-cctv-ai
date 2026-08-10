import numpy as np
from src.behaviour.keypoint_buffer import KeypointBuffer


def test_push_and_retrieve():
    buf = KeypointBuffer(window_size=10)
    kp = np.random.rand(33, 3).astype(np.float32)
    buf.push(1, kp)
    seq = buf.get_sequence(1)
    assert seq is not None
    assert seq.shape == (1, 33, 3)


def test_sliding_window():
    buf = KeypointBuffer(window_size=5)
    for i in range(10):
        kp = np.full((33, 3), i, dtype=np.float32)
        buf.push(1, kp)
    seq = buf.get_sequence(1)
    assert seq.shape == (5, 33, 3)
    assert seq[0][0][0] == 5.0


def test_is_ready():
    buf = KeypointBuffer(window_size=30)
    for i in range(8):
        buf.push(1, np.zeros((33, 3)))
    assert not buf.is_ready(1, min_frames=10)
    buf.push(1, np.zeros((33, 3)))
    buf.push(1, np.zeros((33, 3)))
    assert buf.is_ready(1, min_frames=10)


def test_prune():
    buf = KeypointBuffer(window_size=10)
    buf.push(1, np.zeros((33, 3)))
    buf.push(2, np.zeros((33, 3)))
    buf.push(3, np.zeros((33, 3)))
    pruned = buf.prune(active_track_ids={2})
    assert pruned == 2
    assert buf.buffer_count == 1
    assert buf.get_sequence(2) is not None


def test_unknown_track():
    buf = KeypointBuffer()
    assert buf.get_sequence(999) is None
    assert not buf.is_ready(999)
