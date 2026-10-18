"""Smoke test. py_compile also runs on the main PC; this test runs on the GPU PC."""
from datetime import datetime, timezone
from smart_cctv_ai.schema import Event, BehaviourType, Severity
from smart_cctv_ai.zones import Zone
from smart_cctv_ai.config import ZoneCfg


def test_event_roundtrip():
    now = datetime.now(timezone.utc)
    ev = Event(camera_id="cam1", type=BehaviourType.intrusion,
               severity=Severity.suspicious, track_ids=[1, 2],
               zone="A", start_ts=now, end_ts=now)
    assert ev.type == BehaviourType.intrusion
    assert ev.track_ids == [1, 2]


def test_zone_contains():
    z = Zone(ZoneCfg(name="t", polygon=[[0, 0], [100, 0], [100, 100], [0, 100]],
                    rules=["intrusion"]))
    assert z.contains(50, 50)
    assert not z.contains(150, 50)
    assert z.contains_box((40, 40, 60, 90))
