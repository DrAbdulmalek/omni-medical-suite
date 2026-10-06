# src/ocr/slice_store.py
"""Slice Store — مخزن القصاصات (Slices/Clippings)

ABBYY FineReader lets operators clip a letter/word from a scan and attach the
ground-truth text; those annotated clips become the system's learning material.
This module implements the same concept for the Omni pipeline:

    slice = (crop of a source image) + (correct text) + (level: char|word|line)
            + provenance (telegram channel / message / upload)

Everything lands under the training DB directory:

    <training_db>/slices/<id>.png     # the clipped image itself
    <training_db>/slices.jsonl        # append-only manifest (one JSON per line)
    <training_db>/sync_state.json     # which slice ids were already pushed to GitHub

The manifest is the *source of truth*; the GitHub training-database repo is a
mirror generated from it (see scripts/trainingdb_sync.py).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

VALID_LEVELS = ("char", "word", "line")


def _default_training_db_dir() -> str:
    env = os.getenv("OMNI_TRAINING_DB_DIR")
    if env:
        return env
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "training_db"))


class SliceStore:
    """Human-annotated clip store (قصاصات مع تعليق نصي)."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or _default_training_db_dir()
        self.slices_dir = os.path.join(self.base_dir, "slices")
        self.manifest_path = os.path.join(self.base_dir, "slices.jsonl")
        self.sync_state_path = os.path.join(self.base_dir, "sync_state.json")
        os.makedirs(self.slices_dir, exist_ok=True)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ io
    def _append_manifest(self, record: Dict[str, Any]) -> None:
        with self._lock:
            with open(self.manifest_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_manifest(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.manifest_path):
            return []
        records: List[Dict[str, Any]] = []
        with open(self.manifest_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("skipping malformed manifest line")
        return records

    # ---------------------------------------------------------------- api
    def add_slice(self, source_image: np.ndarray, bbox: List[int], text: str,
                  level: str = "word", lang: str = "ar",
                  source_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Crop ``bbox`` (x, y, w, h) from ``source_image``, save PNG + manifest row.

        يقتطع القصاصة من الصورة الأصلية ويحفظها مع النص الصحيح.
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("slice text (annotation) is required")
        if level not in VALID_LEVELS:
            raise ValueError(f"level must be one of {VALID_LEVELS}")
        if source_image is None or source_image.size == 0:
            raise ValueError("source image is empty")
        if not bbox or len(bbox) != 4:
            raise ValueError("bbox must be [x, y, w, h]")
        x, y, w, h = [int(v) for v in bbox]
        H, W = source_image.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = max(1, min(w, W - x)), max(1, min(h, H - y))
        crop = source_image[y:y + h, x:x + w]
        if crop.size == 0:
            raise ValueError("crop is empty — check bbox against image size")

        slice_id = uuid.uuid4().hex[:16]
        png_path = os.path.join(self.slices_dir, f"{slice_id}.png")
        cv2.imwrite(png_path, crop)

        with open(png_path, "rb") as fh:
            png_sha = hashlib.sha256(fh.read()).hexdigest()

        record: Dict[str, Any] = {
            "id": slice_id,
            "created_at": int(time.time()),
            "level": level,
            "text": text,
            "lang": lang,
            "bbox": [x, y, w, h],
            "image": f"slices/{slice_id}.png",
            "image_sha256": png_sha,
            "source": source_meta or {},
        }
        self._append_manifest(record)
        logger.info("slice %s saved (level=%s text=%r)", slice_id, level, text[:24])
        return record

    def image_of(self, record: Dict[str, Any]) -> Optional[np.ndarray]:
        path = os.path.join(self.base_dir, record.get("image", ""))
        if not os.path.exists(path):
            return None
        return cv2.imread(path)

    def list_slices(self, limit: int = 50, level: Optional[str] = None,
                    pending_only: bool = False) -> List[Dict[str, Any]]:
        rows = self._read_manifest()
        if level:
            rows = [r for r in rows if r.get("level") == level]
        if pending_only:
            synced = set(self.synced_ids())
            rows = [r for r in rows if r["id"] not in synced]
        rows.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        return rows[:limit]

    def count(self) -> int:
        return len(self._read_manifest())

    # ------------------------------------------------------------ sync
    def synced_ids(self) -> List[str]:
        if not os.path.exists(self.sync_state_path):
            return []
        try:
            with open(self.sync_state_path, encoding="utf-8") as fh:
                return json.load(fh).get("synced_ids", [])
        except Exception:
            return []

    def mark_synced(self, ids: List[str], commit: str = "") -> int:
        with self._lock:
            state: Dict[str, Any] = {"synced_ids": self.synced_ids(), "last_commit": ""}
            if os.path.exists(self.sync_state_path):
                try:
                    with open(self.sync_state_path, encoding="utf-8") as fh:
                        state = json.load(fh)
                except Exception:
                    pass
            merged = set(state.get("synced_ids", [])) | set(ids)
            state["synced_ids"] = sorted(merged)
            if commit:
                state["last_commit"] = commit
            state["last_sync_at"] = int(time.time())
            tmp = self.sync_state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.sync_state_path)
        return len(state["synced_ids"])

    def stats(self) -> Dict[str, Any]:
        rows = self._read_manifest()
        synced = set(self.synced_ids())
        by_level: Dict[str, int] = {}
        by_lang: Dict[str, int] = {}
        for r in rows:
            by_level[r.get("level", "?")] = by_level.get(r.get("level", "?"), 0) + 1
            by_lang[r.get("lang", "?")] = by_lang.get(r.get("lang", "?"), 0) + 1
        return {"slices": len(rows), "synced": len(synced),
                "pending": max(0, len(rows) - len(synced & {r['id'] for r in rows})),
                "by_level": by_level, "by_lang": by_lang}
