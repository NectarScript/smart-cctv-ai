"""CLIP semantic search over event snapshots.

Lazy design: image embeddings are computed on first search for events that
don't have one yet, then cached in a numpy file next to the SQLite DB.
Text queries hit CLIP's text encoder on the fly.
"""
from __future__ import annotations
import threading
from pathlib import Path
from typing import Optional
import numpy as np
from loguru import logger
from sqlmodel import Session, select
from ..schema import Event
from .. import db

_CACHE_PATH = Path("data/clip_index.npz")


class ClipIndex:
    def __init__(self, model_name: str = "ViT-B-32",
                 pretrained: str = "laion2b_s34b_b79k",
                 device: str = "auto"):
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device
        self._lock = threading.Lock()
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._emb: dict[int, np.ndarray] = {}  # event_id -> (D,) float32
        self._load_cache()

    def _lazy_init(self) -> None:
        if self._model is not None:
            return
        import open_clip  # local import
        import torch
        dev = ("cuda" if (self.device == "auto" and torch.cuda.is_available())
               else ("cpu" if self.device == "auto" else self.device))
        self._torch_device = dev
        logger.info(f"loading CLIP {self.model_name}/{self.pretrained} on {dev}")
        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained=self.pretrained, device=dev)
        model.eval()
        self._model = model
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer(self.model_name)

    def _load_cache(self) -> None:
        if not _CACHE_PATH.exists():
            return
        try:
            data = np.load(_CACHE_PATH, allow_pickle=False)
            ids = data["ids"]
            embs = data["embs"]
            self._emb = {int(ids[i]): embs[i] for i in range(len(ids))}
            logger.info(f"loaded {len(self._emb)} CLIP embeddings from cache")
        except Exception as e:
            logger.warning(f"CLIP cache load failed: {e}")

    def _save_cache(self) -> None:
        if not self._emb:
            return
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ids = np.array(list(self._emb.keys()), dtype=np.int64)
        embs = np.stack(list(self._emb.values())).astype(np.float32)
        tmp = _CACHE_PATH.with_suffix(".tmp.npz")
        np.savez(tmp, ids=ids, embs=embs)
        tmp.replace(_CACHE_PATH)

    def _embed_image(self, path: Path) -> Optional[np.ndarray]:
        try:
            from PIL import Image
            import torch
            img = Image.open(path).convert("RGB")
            with torch.no_grad():
                t = self._preprocess(img).unsqueeze(0).to(self._torch_device)
                feat = self._model.encode_image(t)
                feat = feat / feat.norm(dim=-1, keepdim=True)
            return feat.cpu().numpy()[0].astype(np.float32)
        except Exception as e:
            logger.warning(f"CLIP image encode failed for {path}: {e}")
            return None

    def _embed_text(self, query: str) -> Optional[np.ndarray]:
        import torch
        with torch.no_grad():
            tok = self._tokenizer([query]).to(self._torch_device)
            feat = self._model.encode_text(tok)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        return feat.cpu().numpy()[0].astype(np.float32)

    def _ensure_indexed(self) -> None:
        """Backfill embeddings for events whose snapshots we have but didn't index."""
        with Session(db.engine()) as s:
            rows = s.exec(select(Event.id, Event.snapshot)).all()
        new = 0
        for ev_id, snap in rows:
            if ev_id in self._emb or not snap:
                continue
            p = Path(snap)
            if not p.exists():
                continue
            emb = self._embed_image(p)
            if emb is not None:
                self._emb[ev_id] = emb
                new += 1
        if new:
            logger.info(f"indexed {new} new event snapshots")
            self._save_cache()

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Returns [(event_id, score)] sorted descending by cosine similarity."""
        with self._lock:
            self._lazy_init()
            self._ensure_indexed()
            if not self._emb:
                return []
            q = self._embed_text(query)
            if q is None:
                return []
            ids = np.array(list(self._emb.keys()))
            embs = np.stack(list(self._emb.values()))
            scores = embs @ q
            order = np.argsort(-scores)[:top_k]
            return [(int(ids[i]), float(scores[i])) for i in order]
