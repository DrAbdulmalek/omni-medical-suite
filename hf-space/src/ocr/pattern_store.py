# src/ocr/pattern_store.py
"""Glyph Pattern Store — مخزن الأنماط (字模)

ABBYY-FineReader-style *pattern recognition* foundation:
the system learns glyph templates (characters, sub-words, whole words) from
human-annotated slices and later uses them to recognize the same shapes in
new scans — improving accuracy without any cloud engine.

محرك الأنماط على طريقة ABBYY FineReader:
يتعلم النظام قوالب الحروف/الكلمات من القصاصات التي علّق عليها الإنسان،
ثم يستخدمها لاحقاً للتعرف على الأشكال نفسها في مسح ضوئي جديد —
تحسّن الدقة دون أي محرك سحابي.

Storage layout (under the training DB dir):
    patterns/patterns.json      # index: key -> {label, script, level, bitmap_b64, count, ...}

Bitmaps are stored as base64 PNG of a binarized, aspect-preserving,
fixed-canvas (96x48) glyph image — small enough for git, precise enough
for template matching.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

CANVAS_W, CANVAS_H = 96, 48
DEFAULT_MATCH_THRESHOLD = 0.90
DEFAULT_SCHEMA_VERSION = 1


def _default_training_db_dir() -> str:
    """data/training_db relative to the suite repository root (src/ocr/..)."""
    env = os.getenv("OMNI_TRAINING_DB_DIR")
    if env:
        return env
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "training_db"))


def normalize_glyph(image: np.ndarray, canvas_w: int = CANVAS_W, canvas_h: int = CANVAS_H) -> Optional[np.ndarray]:
    """Binarize + center a glyph crop on a fixed canvas, preserving aspect ratio.

    Returns a single-channel uint8 image (0/255) sized ``canvas_w x canvas_h``.
    """
    if image is None or image.size == 0:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = cv2.resize(gray, (max(canvas_w // 2, gray.shape[1] // 2), max(canvas_h // 2, gray.shape[0] // 2)),
                      interpolation=cv2.INTER_AREA) if gray.shape[0] > canvas_h * 4 else gray
    # Otsu binarization; ink = white on black for matching consistency
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ys, xs = np.where(bw > 0)
    if len(xs) == 0:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    ink = bw[y0:y1 + 1, x0:x1 + 1]

    scale = min((canvas_w - 4) / ink.shape[1], (canvas_h - 4) / ink.shape[0])
    scale = max(scale, 0.01)
    new_w, new_h = max(1, int(ink.shape[1] * scale)), max(1, int(ink.shape[0] * scale))
    ink = cv2.resize(ink, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

    canvas = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    off_x = (canvas_w - new_w) // 2
    off_y = (canvas_h - new_h) // 2
    canvas[off_y:off_y + new_h, off_x:off_x + new_w] = ink
    return canvas


def _bitmap_to_b64(bitmap: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", bitmap)
    if not ok:
        raise ValueError("bitmap encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _b64_to_bitmap(b64: str) -> np.ndarray:
    buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("bitmap decode failed")
    return img


class PatternStore:
    """Persistent glyph-pattern library with template matching.

    مكتبة أنماط دائمة مع مطابقة قوالب للتعرف على الحروف والكلمات.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or _default_training_db_dir()
        self.patterns_dir = os.path.join(self.base_dir, "patterns")
        self.index_path = os.path.join(self.patterns_dir, "patterns.json")
        os.makedirs(self.patterns_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._index: Dict[str, Dict[str, Any]] = self._load()

    # ---------------------------------------------------------------- io
    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(self.index_path):
            return {}
        try:
            with open(self.index_path, encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get("patterns", {})
        except Exception as exc:  # corrupted index should not kill the app
            logger.error("pattern index load failed: %s", exc)
            return {}

    def _save(self) -> None:
        tmp = self.index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": DEFAULT_SCHEMA_VERSION, "patterns": self._index},
                      fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.index_path)

    # ------------------------------------------------------------- keys
    @staticmethod
    def make_key(label: str, script: str, level: str) -> str:
        raw = f"{label.strip()}|{script}|{level}".lower()
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    # ------------------------------------------------------------- crud
    def add_pattern(self, label: str, glyph_image: np.ndarray, level: str = "word",
                    script: str = "ar", source_ref: str = "") -> Dict[str, Any]:
        """Register/refresh a pattern from a glyph crop.

        يسجّل نمطاً جديداً أو يحدّث عدّاد نمط موجود.
        """
        bitmap = normalize_glyph(glyph_image)
        if bitmap is None:
            raise ValueError("empty glyph — nothing to learn")
        label = (label or "").strip()
        if not label:
            raise ValueError("pattern label is required")

        key = self.make_key(label, script, level)
        b64 = _bitmap_to_b64(bitmap)
        now = int(time.time())
        with self._lock:
            existing = self._index.get(key)
            if existing:
                existing["count"] = int(existing.get("count", 0)) + 1
                existing["updated_at"] = now
                existing["bitmap_b64"] = b64  # refresh template with latest specimen
                if source_ref and source_ref not in existing.get("examples", []):
                    existing.setdefault("examples", []).append(source_ref)
                    existing["examples"] = existing["examples"][-20:]
                self._index[key] = existing
            else:
                self._index[key] = {
                    "key": key, "label": label, "script": script, "level": level,
                    "width": CANVAS_W, "height": CANVAS_H, "bitmap_b64": b64,
                    "count": 1, "created_at": now, "updated_at": now,
                    "examples": [source_ref] if source_ref else [],
                }
            self._save()
        record = dict(self._index[key])
        record.pop("bitmap_b64", None)
        return record

    def match(self, glyph_image: np.ndarray, top_k: int = 5,
              min_score: float = DEFAULT_MATCH_THRESHOLD,
              script: Optional[str] = None, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Template-match a glyph against the library.

        Returns list of {key, label, level, script, score} sorted by score.
        """
        bitmap = normalize_glyph(glyph_image)
        if bitmap is None or not self._index:
            return []
        query = bitmap.astype(np.float32) / 255.0
        scored: List[Tuple[float, Dict[str, Any]]] = []
        with self._lock:
            items = list(self._index.values())
        for entry in items:
            if script and entry.get("script") != script:
                continue
            if level and entry.get("level") != level:
                continue
            try:
                cand = _b64_to_bitmap(entry["bitmap_b64"]).astype(np.float32) / 255.0
            except Exception:
                continue
            if cand.shape != query.shape:
                cand = cv2.resize(cand, (query.shape[1], query.shape[0]))
            # normalized cross-correlation over the single overlapped position
            score = float(cv2.matchTemplate(query, cand, cv2.TM_CCOEFF_NORMED)[0][0])
            if score >= min_score:
                scored.append((score, entry))
        scored.sort(key=lambda t: t[0], reverse=True)
        out = []
        for score, entry in scored[:top_k]:
            out.append({"key": entry["key"], "label": entry["label"], "level": entry["level"],
                        "script": entry["script"], "score": round(score, 4)})
        return out

    def bitmap_of(self, key: str) -> Optional[np.ndarray]:
        with self._lock:
            entry = self._index.get(key)
            if not entry:
                return None
            try:
                return _b64_to_bitmap(entry["bitmap_b64"])
            except Exception:
                return None

    def list_patterns(self) -> List[Dict[str, Any]]:
        """Metadata list (without bitmaps) sorted by usage count."""
        with self._lock:
            items = []
            for entry in self._index.values():
                items.append({k: v for k, v in entry.items() if k != "bitmap_b64"})
        items.sort(key=lambda e: (-int(e.get("count", 0)), e["label"]))
        return items

    def count(self) -> int:
        with self._lock:
            return len(self._index)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            entries = list(self._index.values())
        by_script: Dict[str, int] = {}
        by_level: Dict[str, int] = {}
        total_occurrences = 0
        for e in entries:
            by_script[e.get("script", "?")] = by_script.get(e.get("script", "?"), 0) + 1
            by_level[e.get("level", "?")] = by_level.get(e.get("level", "?"), 0) + 1
            total_occurrences += int(e.get("count", 0))
        return {"patterns": len(entries), "occurrences": total_occurrences,
                "by_script": by_script, "by_level": by_level}
