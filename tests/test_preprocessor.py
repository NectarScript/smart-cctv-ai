import numpy as np
from src.ingestion.preprocessor import crop_bbox, preprocess_for_pose, letterbox


def test_crop_bbox_basic():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:200, 100:200] = 128
    bbox = np.array([100, 100, 200, 200])
    crop = crop_bbox(frame, bbox, padding=0.0)
    assert crop.shape == (100, 100, 3)
    assert crop.mean() == 128


def test_crop_bbox_with_padding():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bbox = np.array([100, 100, 200, 200])
    crop = crop_bbox(frame, bbox, padding=0.1)
    assert crop.shape[0] > 100
    assert crop.shape[1] > 100


def test_crop_bbox_clamps():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bbox = np.array([0, 0, 50, 50])
    crop = crop_bbox(frame, bbox, padding=0.5)
    assert crop.shape[0] > 0
    assert crop.shape[1] > 0


def test_crop_bbox_empty():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bbox = np.array([100, 100, 100, 100])
    crop = crop_bbox(frame, bbox, padding=0.0)
    assert crop.shape == (64, 64, 3)


def test_preprocess_for_pose():
    bgr = np.zeros((100, 50, 3), dtype=np.uint8)
    bgr[:, :, 0] = 255
    rgb = preprocess_for_pose(bgr)
    assert rgb[:, :, 2].mean() == 255


def test_letterbox():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = letterbox(frame, target_size=640)
    assert result.shape == (640, 640, 3)
