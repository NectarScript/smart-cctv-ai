from enum import Enum


class BehaviourLabel(str, Enum):
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    CRITICAL = "critical"


class EventType(str, Enum):
    LOITERING = "loitering"
    FIGHTING = "fighting"
    SUDDEN_RUNNING = "sudden_running"
    CROWD_SURGE = "crowd_surge"
    THEFT_POSTURE = "theft_posture"
    NORMAL = "normal"


class SourceType(str, Enum):
    WEBCAM = "webcam"
    RTSP = "rtsp"
    FILE = "file"


MEDIAPIPE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (27, 31),
    (24, 26), (26, 28), (28, 30), (28, 32),
]

LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
