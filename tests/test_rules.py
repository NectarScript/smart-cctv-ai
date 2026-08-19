import time
from collections import deque

import numpy as np

from src.core.config import BehaviourConfig
from src.core.constants import BehaviourLabel, EventType
from src.behaviour.rules import RuleBasedClassifier
from src.detection.track_store import TrackHistory


def _make_history(track_id, centroids, duration=0, camera_id="cam0"):
    now = time.time()
    h = TrackHistory(
        track_id=track_id,
        camera_id=camera_id,
        centroids=deque(centroids, maxlen=300),
        bboxes=deque(maxlen=300),
        timestamps=deque(maxlen=300),
        first_seen=now - duration,
        last_seen=now,
    )
    for i, c in enumerate(centroids):
        h.bboxes.append(np.array([c[0] - 20, c[1] - 40, c[0] + 20, c[1] + 40]))
        h.timestamps.append(now - duration + i * (duration / max(len(centroids), 1)))
    return h


def test_loitering_detected():
    cfg = BehaviourConfig(
        loiter_time_threshold=5.0, loiter_radius_px=50, loiter_min_displacement_px=1.0,
    )
    classifier = RuleBasedClassifier(cfg)
    # Simulate wandering in a small area — consistent movement but within radius
    centroids = []
    for i in range(200):
        angle = i * 0.15
        r = 15
        centroids.append((100 + r * np.cos(angle), 100 + r * np.sin(angle)))
    history = _make_history(1, centroids, duration=10.0)
    event = classifier.classify(1, history, None, [], time.time())
    assert event.event_type == EventType.LOITERING
    assert event.label in (BehaviourLabel.SUSPICIOUS, BehaviourLabel.CRITICAL)


def test_no_loitering_when_moving():
    cfg = BehaviourConfig(
        loiter_time_threshold=5.0, loiter_radius_px=50, loiter_min_displacement_px=1.0,
    )
    classifier = RuleBasedClassifier(cfg)
    centroids = [(i * 5, 100) for i in range(200)]
    history = _make_history(1, centroids, duration=10.0)
    event = classifier.classify(1, history, None, [], time.time())
    assert event.event_type != EventType.LOITERING


def test_sudden_running_detected():
    cfg = BehaviourConfig(
        velocity_spike_factor=3.0, sudden_run_min_history_sec=1.0,
        velocity_min_baseline=0.5, sudden_run_min_velocity=3.0,
    )
    classifier = RuleBasedClassifier(cfg)
    slow = [(100, 100 + i * 0.5) for i in range(80)]
    fast = [(100, 140 + i * 20) for i in range(30)]
    centroids = slow + fast
    history = _make_history(1, centroids, duration=4.0)
    event = classifier.classify(1, history, None, [], time.time())
    assert event.event_type == EventType.SUDDEN_RUNNING


def test_crowd_surge_detected():
    cfg = BehaviourConfig(crowd_density_threshold=3, crowd_region_radius_px=200)
    classifier = RuleBasedClassifier(cfg)
    tracks = []
    for i in range(5):
        h = _make_history(i, [(100 + i * 10, 100 + i * 5)], duration=2.0)
        tracks.append(h)
    event = classifier.classify(0, tracks[0], None, tracks, time.time())
    assert event.event_type == EventType.CROWD_SURGE


def test_normal_when_no_issues():
    cfg = BehaviourConfig()
    classifier = RuleBasedClassifier(cfg)
    centroids = [(100 + i, 200 + i) for i in range(20)]
    history = _make_history(1, centroids, duration=2.0)
    event = classifier.classify(1, history, None, [history], time.time())
    assert event.label == BehaviourLabel.NORMAL
