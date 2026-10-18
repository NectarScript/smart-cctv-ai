from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/privacy")
_pipeline = None


def set_pipeline(p) -> None:
    global _pipeline
    _pipeline = p


class PrivacyBody(BaseModel):
    enabled: bool


@router.get("")
def get():
    if _pipeline is None:
        return {"enabled": False}
    return {"enabled": _pipeline.privacy_mode}


@router.post("")
def set_(body: PrivacyBody):
    if _pipeline is None:
        return {"enabled": False, "error": "pipeline not running"}
    _pipeline.privacy_mode = body.enabled
    return {"enabled": _pipeline.privacy_mode}
