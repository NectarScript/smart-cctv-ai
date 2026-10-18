from __future__ import annotations
import asyncio
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()
_pipeline = None  # set by app.py on startup


def set_pipeline(p) -> None:
    global _pipeline
    _pipeline = p


def _placeholder(text: str) -> bytes:
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(img, text, (20, 180), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (200, 200, 200), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes() if ok else b""


async def _mjpeg(camera_id: str):
    boundary = b"--frame"
    while True:
        img = None
        if _pipeline is not None and camera_id in _pipeline.states:
            img = _pipeline.states[camera_id].get_frame()
        if img is None:
            jpg = _placeholder(f"{camera_id}: waiting for frames...")
        else:
            ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            jpg = buf.tobytes() if ok else b""
        if jpg:
            yield (boundary + b"\r\n"
                   b"Content-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
                   + jpg + b"\r\n")
        await asyncio.sleep(1 / 20)


@router.get("/stream/{camera_id}")
def stream(camera_id: str):
    if _pipeline is None or camera_id not in _pipeline.states:
        raise HTTPException(404, f"unknown camera: {camera_id}")
    return StreamingResponse(_mjpeg(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/cameras")
def cameras():
    if _pipeline is None:
        return []
    return [{"id": cid, "name": s.cfg.name or cid,
             "alive": _pipeline.cams.get(cid).alive if _pipeline.cams.get(cid) else False,
             "fps": round(s.fps, 1)}
            for cid, s in _pipeline.states.items()]
