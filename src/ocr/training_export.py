# src/ocr/training_export.py
"""Training Dataset Export — تصدير بيانات التدريب

Packages the collected slices + patterns into a layout ready for future
AI-model training (e.g., CRNN / TrOCR fine-tuning for Arabic handwriting):

    <export>/
        metadata.json          # counts, provenance, split definition
        labels.jsonl           # {"image": "images/<id>.png", "text": ..., "level": ..., "split": ...}
        images/<id>.png        # copied slice crops
        patterns/labels.jsonl  # pattern templates as (bitmap, label) pairs

Splits: deterministic 80/10/10 (train/val/test) via sha-based hashing so the
same slice always lands in the same split across exports.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SPLIT_RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}


def _split_for(slice_id: str) -> str:
    h = int(hashlib.sha256(slice_id.encode()).hexdigest(), 16) % 100
    if h < 80:
        return "train"
    if h < 90:
        return "val"
    return "test"


def export_slices(training_db_dir: str, out_dir: str, copy_images: bool = True) -> Dict[str, Any]:
    """Export annotated slices as a training-ready dataset. Returns summary."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from slice_store import SliceStore  # local sibling import

    store = SliceStore(training_db_dir)
    rows = store.list_slices(limit=10_000)
    os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)

    labels_path = os.path.join(out_dir, "labels.jsonl")
    counts: Dict[str, int] = {"train": 0, "val": 0, "test": 0}
    written = 0
    with open(labels_path, "w", encoding="utf-8") as fh:
        for rec in rows:
            src_img = os.path.join(training_db_dir, rec.get("image", ""))
            if not os.path.exists(src_img):
                continue
            rel = f"images/{rec['id']}.png"
            if copy_images:
                shutil.copyfile(src_img, os.path.join(out_dir, rel))
            split = _split_for(rec["id"])
            counts[split] += 1
            fh.write(json.dumps({
                "image": rel, "text": rec["text"], "level": rec.get("level", "word"),
                "lang": rec.get("lang", "ar"), "split": split,
                "source": rec.get("source", {}),
                "created_at": rec.get("created_at"),
            }, ensure_ascii=False) + "\n")
            written += 1

    metadata = {
        "generated_at": int(time.time()),
        "dataset": "omni-ocr-slices",
        "description": "Human-annotated OCR slices (قصاصات) for Arabic/English medical documents",
        "total": written,
        "splits": counts,
        "levels": sorted({r.get("level", "word") for r in rows}),
        "languages": sorted({r.get("lang", "ar") for r in rows}),
    }
    with open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=1)
    logger.info("exported %s slices to %s", written, out_dir)
    return metadata


def export_patterns(training_db_dir: str, out_dir: str) -> Dict[str, Any]:
    """Export pattern templates as bitmap->label pairs for classifier pretraining."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from pattern_store import PatternStore

    store = PatternStore(training_db_dir)
    pdir = os.path.join(out_dir, "patterns")
    os.makedirs(pdir, exist_ok=True)
    n = 0
    with open(os.path.join(pdir, "labels.jsonl"), "w", encoding="utf-8") as fh:
        for entry in store.list_patterns():
            bmp = store.bitmap_of(entry["key"])
            if bmp is None:
                continue
            rel = f"patterns/{entry['key']}.png"
            import cv2
            cv2.imwrite(os.path.join(out_dir, rel), bmp)
            fh.write(json.dumps({"image": rel, "text": entry["label"],
                                 "level": entry.get("level", "word"),
                                 "script": entry.get("script", "ar"),
                                 "count": entry.get("count", 1)}, ensure_ascii=False) + "\n")
            n += 1
    return {"patterns": n}


def export_all(training_db_dir: str, out_dir: Optional[str] = None) -> Dict[str, Any]:
    out_dir = out_dir or os.path.join(training_db_dir, "exports", f"dataset-{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)
    slices_meta = export_slices(training_db_dir, out_dir)
    patterns_meta = export_patterns(training_db_dir, out_dir)
    summary = {"out_dir": out_dir, "slices": slices_meta, "patterns": patterns_meta}
    with open(os.path.join(out_dir, "EXPORT_SUMMARY.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    return summary
