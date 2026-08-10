# Phase 1 — Core AI Pipeline Documentation

## PTSS-2 Deliverable: Modules M1 + M2 + M3

---

# Module 1 — Multi-Camera Ingestion & AI Vision

## Literature Review

Video ingestion for surveillance systems has evolved from single-camera frame grabbing to distributed multi-source architectures. Key works include:

- **OpenCV VideoCapture** remains the standard for camera interfacing in Python-based systems. It supports USB cameras, IP cameras (RTSP/ONVIF), and video files through a unified API. The blocking nature of `read()` necessitates threaded capture for real-time systems (Bradski, 2000; OpenCV documentation).

- **RTSP streaming** (RFC 2326, RFC 7826) is the dominant protocol for IP camera feeds. FFmpeg's backend in OpenCV provides robust RTSP handling with automatic reconnection and codec negotiation.

- **Frame buffering strategies** in real-time systems face a fundamental trade-off: large buffers increase latency but survive processing spikes; small buffers maintain low latency but risk frame drops. The drop-oldest policy (discarding stale frames when the buffer is full) is established practice in surveillance pipelines (Chen et al., 2019).

- **Thread-per-camera vs async I/O**: For OpenCV-based systems, threading is preferred over asyncio because `cv2.VideoCapture.read()` is a blocking C++ call that releases the GIL, making threads both correct and efficient for I/O-bound capture (Adrian Rosebrock, PyImageSearch, 2016).

## Existing Approaches

| Approach | Strengths | Limitations |
|----------|-----------|-------------|
| Single-threaded sequential capture | Simple | Cannot keep up with multiple cameras |
| Thread pool with shared queue | Good parallelism | Queue management complexity |
| Multiprocessing with shared memory | True parallelism | IPC overhead, memory duplication |
| GStreamer pipeline | Hardware acceleration | Complex setup, less portable |

## Research/Technical Gaps

1. Most open-source surveillance systems use single-camera ingestion. Multi-camera systems typically require proprietary VMS (Video Management Software) such as Milestone or Genetec.
2. Frame synchronization across cameras is rarely addressed in academic literature — most systems process cameras independently.
3. Adaptive frame rate adjustment based on processing load is uncommon in current implementations.

## What We Implemented

- **CameraSource**: Thread-per-camera capture wrapping `cv2.VideoCapture`. Supports webcam indices, RTSP URLs, and video files through a unified interface.
- **CameraManager**: Manages multiple CameraSource instances with per-camera bounded queues. Supports dynamic add/remove of cameras at runtime.
- **Drop-oldest buffering**: When the processing pipeline falls behind, the oldest queued frame is discarded to maintain temporal relevance. This prioritizes recency over completeness.
- **Preprocessor**: Frame cropping with configurable padding, BGR→RGB conversion for MediaPipe, and letterbox resizing for YOLO.

## How We Implemented It

- Each camera runs in a daemon thread, continuously calling `cv2.VideoCapture.read()` and pushing `FramePacket` dataclass instances to a bounded `queue.Queue`.
- `CameraManager` provides round-robin frame retrieval across all active cameras via `get_any_frame()`.
- FPS measurement uses a rolling 1-second window counter in the capture thread.
- RTSP sources use the FFmpeg backend (`cv2.CAP_FFMPEG`) for better codec support and reconnection handling.
- Buffer size set to 1 (`CAP_PROP_BUFFERSIZE`) on the VideoCapture to minimize internal latency.

## Results and Performance

*To be measured with actual hardware. Run `scripts/benchmark.py` for real numbers.*

Expected:
- Webcam capture: 25-30 FPS (limited by camera hardware)
- Video file capture: limited only by disk I/O
- RTSP capture: depends on network conditions, typically 15-25 FPS
- Queue overhead: < 1ms per frame

## Problems Encountered and Solutions

| Problem | Solution |
|---------|----------|
| RTSP streams dropping after timeout | Set `CAP_PROP_BUFFERSIZE=1` + retry loop with 100ms backoff |
| Queue blocking when processing is slow | Drop-oldest policy: `get_nowait()` before `put()` when full |
| Video file sources reaching EOF | Detect EOF via `read()` returning False, set running flag to stop gracefully |
| Thread cleanup on shutdown | Daemon threads + `join(timeout=3.0)` + explicit `VideoCapture.release()` |

## Current Limitations

1. No frame synchronization across cameras (each camera runs at its own rate).
2. No automatic reconnection for RTSP streams (only retry on read failure, not connection loss).
3. No hardware-accelerated decoding (CPU-only via OpenCV).
4. Frame dropping under load is silent — no metric exposed for drop rate.

## What We Will Implement Next

- RTSP auto-reconnection with exponential backoff
- Frame drop rate metric
- Optional GPU-accelerated decoding via NVIDIA Video Codec SDK
- Frame timestamp synchronization for multi-camera analysis

---

# Module 2 — Detection & Tracking

## Literature Review

- **YOLOv8** (Jocher et al., Ultralytics, 2023): The latest in the YOLO family, offering multiple model sizes (nano to extra-large). YOLOv8n achieves ~37.3 mAP on COCO with 3.2M parameters, running at 80+ FPS on GPU and 25-40 FPS on modern CPUs. Compared to YOLOv5, it offers improved accuracy at similar speed. The architecture uses a CSPDarknet backbone with a PAN-FPN neck.

- **ByteTrack** (Zhang et al., ECCV 2022): A simple yet effective multi-object tracker that associates detections using byte-level matching. Unlike SORT (Bewley et al., 2016) which discards low-confidence detections, ByteTrack keeps them as secondary candidates for association. This reduces ID switches by 2-3x compared to SORT on MOT17 benchmark. Key insight: low-confidence detections often correspond to occluded or partially visible objects.

- **SORT** (Bewley et al., 2016): The foundational tracker using Kalman filter + Hungarian algorithm. Fast but suffers from high ID switch rate. ByteTrack extends SORT with the "second association" step.

- **DeepSORT** (Wojke et al., 2017): Adds appearance features (Re-ID) to SORT, reducing ID switches at the cost of additional computation (~30% slower than ByteTrack). Better for re-identification after long occlusions.

- **supervision** library (Roboflow, 2023-present): Provides clean Python wrappers for detection and tracking, including ByteTrack. Standardizes the detection/tracking interface with `sv.Detections` objects.

## Existing Approaches

| Tracker | ID Switches (MOT17) | FPS | Re-ID Support |
|---------|---------------------|-----|---------------|
| SORT | High | 260+ | No |
| DeepSORT | Medium | 20-40 | Yes |
| ByteTrack | Low | 150+ | No |
| FairMOT | Low | 25-30 | Yes |
| OC-SORT | Very Low | 200+ | No |

## Research/Technical Gaps

1. Most tracking benchmarks (MOT17, MOT20) evaluate on pre-recorded video. Real-time multi-camera tracking with live streams is underrepresented.
2. Cross-camera track association (same person across different cameras) is an open research problem that most systems solve with Re-ID networks, adding significant latency.
3. ByteTrack assumes a fixed frame rate. Variable frame rates (common with RTSP streams) degrade Kalman filter predictions.

## What We Implemented

- **PersonDetector**: Wraps Ultralytics YOLOv8n with person-class filtering. Outputs `sv.Detections` for seamless ByteTrack integration.
- **Tracker**: Wraps `sv.ByteTrack` with configurable activation threshold, lost track buffer, and matching threshold.
- **TrackStore**: Accumulates per-track spatial history (centroids, bounding boxes, timestamps) for downstream behaviour analysis. Provides velocity/displacement computation and automatic pruning of stale tracks.

## How We Implemented It

- YOLOv8n auto-downloads on first use (~6MB). Inference runs at native frame resolution (typically 640x480).
- Person-only filtering: YOLO detects 80 COCO classes; we keep only `class_id=0` (person).
- ByteTrack via `sv.ByteTrack.update_with_detections()`: takes `sv.Detections` in, returns `sv.Detections` with `tracker_id` populated.
- TrackStore stores up to 300 historical points per track using `collections.deque` for memory efficiency.
- Velocity computed as mean Euclidean distance between consecutive centroids over a configurable window.

## Results and Performance

*To be measured. Run `scripts/benchmark.py`.*

Expected (CPU, 640x480 input):
- YOLOv8n inference: 25-40ms per frame
- ByteTrack association: < 2ms per frame
- Track persistence: maintained across 30+ frame gaps (configurable via `lost_track_buffer`)

## Problems Encountered and Solutions

| Problem | Solution |
|---------|----------|
| YOLO first-inference latency (~2s cold start) | Warmup pass with dummy frame on pipeline start |
| ByteTrack losing tracks during rapid movement | Increased `lost_track_buffer` to 30 frames |
| Detection confidence too low for dim lighting | Configurable threshold (default 0.45, lower for difficult conditions) |
| Memory growth from track history | Bounded deque (maxlen=300) + periodic pruning of stale tracks |

## New Ideas / Innovations

1. **Decoupled detection and tracking stores**: Unlike most implementations that discard track history after the track is lost, we maintain a persistent TrackStore that enables long-term temporal analysis for behaviour classification. This is essential for detecting patterns like loitering (which requires >15 seconds of history).

2. **Per-camera tracker instances**: Each camera gets its own ByteTrack instance, avoiding cross-camera confusion. This is correct for independent camera views and enables future per-camera parameter tuning.

## Current Limitations

1. No cross-camera track association (same person in multiple camera views gets different IDs).
2. No GPU acceleration (CPU-only in Phase 1).
3. ByteTrack does not handle re-identification after long occlusions (>30 frames by default).
4. Detection accuracy degrades in low-light and crowded conditions.

## What We Will Implement Next

- GPU-accelerated inference via CUDA
- Benchmarking YOLOv8s vs YOLOv8n for accuracy/speed trade-off
- Cross-camera track association using appearance features
- Adaptive confidence threshold based on lighting conditions

---

# Module 3 — Behaviour Classification

## Literature Review

- **MediaPipe Pose** (Bazarevsky et al., Google, 2020): Extracts 33 body keypoints in real-time. Uses a BlazePose architecture optimized for mobile/edge deployment. Three complexity levels (lite/full/heavy) trade accuracy for speed. Achieves ~92% PCKh on MPII dataset at full complexity.

- **Skeleton-based action recognition** is a mature research area. Key approaches include:
  - **ST-GCN** (Yan et al., AAAI 2018): Spatial-Temporal Graph Convolutional Networks model skeleton sequences as graphs. Strong performance on NTU-RGB+D dataset (81.5% accuracy) but computationally expensive.
  - **LSTM/GRU approaches** (Du et al., 2015; Shahroudy et al., 2016): Treat keypoint sequences as time series. Simpler than graph-based methods, ~75% accuracy on NTU-RGB+D, faster inference.
  - **Rule-based heuristics**: Used in deployed surveillance systems (e.g., BriefCam, Avigilon) for specific events. Reliable for well-defined spatial patterns (loitering, perimeter breach) but poor at recognizing complex activities (fighting, theft).

- **Behaviour classification in surveillance** faces fundamental challenges:
  - Class imbalance: normal behaviour vastly outnumbers suspicious events
  - Context dependence: running is normal near a gym, suspicious near a jewelry store
  - No standard dataset: UCF-Crime, ShanghaiTech are closest but focus on anomaly detection, not surveillance-specific events

## Existing Approaches

| Approach | Accuracy | Speed | Training Data Needed |
|----------|----------|-------|---------------------|
| Rule-based (spatial heuristics) | Event-specific | Real-time | None |
| LSTM on keypoint sequences | ~75% NTU-RGB+D | Real-time | Thousands of samples |
| ST-GCN | ~82% NTU-RGB+D | Near real-time | Thousands of samples |
| Video transformers (ViViT, TimeSformer) | ~85% Kinetics-400 | Slow (GPU required) | Millions of samples |

## Research/Technical Gaps

1. **No standard surveillance behaviour dataset**: Existing datasets (UCF-Crime, CHAD) lack keypoint annotations for pose-based classification. Custom labeling is required.
2. **Rule-based systems are understudied in literature**: Most papers focus on ML approaches, but deployed systems predominantly use rules. The gap between academic methods and practical deployment is significant.
3. **Temporal context length** is poorly understood: how many seconds of observation are needed to reliably classify each behaviour type? Our implementation explores this empirically.
4. **Pose estimation on surveillance footage** (top-down/angled cameras, low resolution) is less studied than frontal/side views typical in action recognition datasets.

## What We Implemented

A **rule-based classifier** with 5 heuristic detectors, operating on track history (centroids over time) and pose keypoint sequences (MediaPipe output).

### Implemented Rules

**1. Loitering (HIGH reliability)**
- Condition: Track centroid stays within a radius of R pixels for > T seconds
- Algorithm: Compute median centroid over observation window. If max displacement from median < radius threshold for > time threshold: loitering detected.
- Severity: SUSPICIOUS (1-2x threshold), CRITICAL (>2x threshold)

**2. Sudden Running (HIGH reliability)**
- Condition: Velocity spike — ratio of recent velocity to baseline velocity exceeds threshold
- Algorithm: Compare average centroid velocity over last 1s vs previous 2s. If ratio > 3x: sudden running.
- Detects transition from slow to fast movement, not constant running.

**3. Fighting / Aggression (MEDIUM reliability)**
- Condition: Two tracks in close proximity AND rapid limb movement detected
- Algorithm: (a) Check if any other track centroid is within proximity threshold. (b) If yes, check if wrist/ankle keypoints show high frame-to-frame displacement for 5+ consecutive frames.
- Known false positives: vigorous exercise, animated conversation, dancing.

**4. Crowd Surge (MEDIUM reliability)**
- Condition: Track density exceeds threshold in a spatial region
- Algorithm: Count tracks within radius around each track centroid. If count >= threshold, fire event. De-duplicated: only the lowest track_id in each cluster reports the event.

**5. Theft Posture (LOW reliability, experimental, disabled by default)**
- Condition: Sustained crouching with wrists below hip level
- Algorithm: Check shoulder-to-hip vertical ratio (torso compression) and wrist position relative to hips. Requires persistence for > 3 seconds.
- Known false positives: tying shoes, picking up dropped items, gardening.

### Unattended Objects — Honestly Deferred

The documentation lists "unattended objects" as a supported event. We did NOT implement this because it requires: (a) detecting non-person objects (bags, packages) via multi-class YOLO, (b) associating an object with the person who placed it, (c) detecting when that person leaves while the object remains. This is a fundamentally different problem from person-behaviour analysis and is deferred to a future phase.

## How We Implemented It

- **PoseEstimator** wraps MediaPipe Pose, called per-person-crop (not per-frame) for better keypoint quality.
- **KeypointBuffer** maintains a per-track sliding window (deque, configurable size) of keypoint arrays.
- **RuleBasedClassifier** runs all 5 rules in priority order (fighting > running > crowd > loitering > theft). Returns the highest-severity match.
- **BehaviourClassifier** is a facade that dispatches to RuleBasedClassifier now, with a seam for ML-based classifiers later.

## Results and Performance

*To be measured with actual surveillance footage. Rule accuracy depends heavily on camera angle, resolution, and scene context.*

Expected latency:
- MediaPipe Pose: 10-20ms per person crop (CPU)
- Rule evaluation: < 1ms per track
- Total M3 overhead: dominated by pose estimation

### Reliability Assessment (Honest)

| Rule | Expected Precision | Expected Recall | Notes |
|------|-------------------|-----------------|-------|
| Loitering | HIGH (>80%) | HIGH (>85%) | Clear spatial signal. Main false positive: sitting in view. |
| Sudden Running | HIGH (>75%) | MEDIUM (>65%) | Detects transitions well. Misses constant running. |
| Fighting | MEDIUM (>50%) | LOW-MEDIUM | High false positive rate in active environments. |
| Crowd Surge | MEDIUM (>60%) | HIGH (>80%) | Density-based, reliable if threshold is tuned. |
| Theft Posture | LOW (<40%) | LOW (<30%) | Too many legitimate reasons to crouch. Experimental. |

These numbers are estimates based on similar systems. Actual measurement requires labeled test footage.

## Problems Encountered and Solutions

| Problem | Solution |
|---------|----------|
| MediaPipe fails on very small crops (< 10px) | Skip pose estimation for tiny bounding boxes |
| Normalized keypoint coordinates need mapping to image space | Map using bbox dimensions for skeleton drawing |
| Loitering false positives from stationary cameras | Threshold tuning: 15s default, configurable per deployment |
| Fighting detection without proximity context | Added multi-track awareness: requires 2+ tracks in proximity |

## New Ideas / Innovations

1. **Pose-per-crop architecture**: Running MediaPipe on individual person crops instead of the full frame improves keypoint quality, especially for distant subjects. Most implementations run pose on the full frame and then associate keypoints to detections — our approach is more accurate but scales linearly with person count.

2. **Hierarchical rule evaluation**: Rules are evaluated in severity order with early termination. A CRITICAL fighting event short-circuits further checks, reducing unnecessary computation.

3. **Configurable rule parameters in YAML**: All thresholds are exposed in `config/default.yaml`, enabling deployment-specific tuning without code changes. This is unusual for academic implementations but essential for practical use.

## Current Limitations

1. **No ML-based classifier**: Rule-based only. Cannot learn from data or adapt to novel behaviours.
2. **No labeled training data**: LSTM/GRU classifier requires labeled surveillance footage that doesn't exist yet.
3. **Pose quality on surveillance footage**: MediaPipe is optimized for frontal/side views. Top-down camera angles common in surveillance produce lower quality keypoints.
4. **Single-person classification**: Each track is classified independently. Group behaviours (coordinated theft, organized crowd movement) are not modeled.
5. **No context awareness**: Cannot distinguish "running in a gym" from "running from a crime scene."

## What We Will Implement Next

- Collect and label surveillance footage for training data
- Train LSTM classifier on keypoint sequences for major event types
- Benchmark LSTM vs GRU vs rule-based accuracy
- Add zone-based context (define zones where specific behaviours are normal/suspicious)
- Implement temporal event aggregation (sustained vs momentary events)

---

# Phase 1 Integration

## Pipeline Architecture

```
M1: CameraSource → Queue → CameraManager
                              ↓
M2: PersonDetector.detect(frame) → sv.Detections
                              ↓
    Tracker.update(detections) → sv.Detections + tracker_id
                              ↓
    TrackStore.update(tracked) → per-track history
                              ↓
M3: crop_bbox → PoseEstimator.estimate(crop) → keypoints
                              ↓
    KeypointBuffer.push(track_id, keypoints)
                              ↓
    BehaviourClassifier.classify(track_id, history, kp_seq) → BehaviourEvent
                              ↓
    Renderer.draw(frame, detections, events, keypoints) → annotated frame
                              ↓
    Display.show(camera_id, annotated)
```

## Data Flow

- **FramePacket**: camera_id, BGR frame, timestamp, frame_number
- **sv.Detections**: xyxy bboxes, confidences, class_ids, tracker_ids
- **TrackHistory**: centroid deque, bbox deque, timestamps, first/last seen
- **Keypoint array**: (33, 3) float32 — x_norm, y_norm, visibility
- **BehaviourEvent**: track_id, camera_id, label, event_type, confidence, timestamp, details

## Threading Model

- N capture threads (one per camera), each pushing to its own queue
- 1 main processing thread: pulls frames round-robin, runs detect → track → pose → classify
- Processing is single-threaded intentionally: YOLO and MediaPipe use internal parallelism

## References

1. Jocher, G. et al. (2023). "Ultralytics YOLOv8." GitHub repository.
2. Zhang, Y. et al. (2022). "ByteTrack: Multi-Object Tracking by Associating Every Detection Box." ECCV 2022.
3. Bazarevsky, V. et al. (2020). "BlazePose: On-device Real-time Body Pose Tracking." CVPR 2020 Workshop.
4. Bewley, A. et al. (2016). "Simple Online and Realtime Tracking." ICIP 2016.
5. Wojke, N. et al. (2017). "Simple Online and Realtime Tracking with a Deep Association Metric." ICIP 2017.
6. Yan, S. et al. (2018). "Spatial Temporal Graph Convolutional Networks for Skeleton-Based Action Recognition." AAAI 2018.
7. Bradski, G. (2000). "The OpenCV Library." Dr. Dobb's Journal.
8. Roboflow (2023). "supervision" Python library. GitHub repository.
9. Sultani, W. et al. (2018). "Real-World Anomaly Detection in Surveillance Videos." CVPR 2018. (UCF-Crime dataset)
10. Du, Y. et al. (2015). "Hierarchical Recurrent Neural Network for Skeleton Based Action Recognition." CVPR 2015.
