"""
Export corrections from HF Space SQLite database to training-hub JSONL format.

This script runs INSIDE the HF Space container and exports:
1. word_crops/corrections_{date}.jsonl  — per-word correction data
2. A summary JSON with counts and stats

The exported files are designed to be committed to the training-hub GitHub repo.

Usage:
    python export_to_training_hub.py [--output-dir /data/training_hub] [--min-confidence 0.0]
"""

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Default paths (inside HF Space container)
DEFAULT_DB_PATH = Path("/app/corrections.db")
DEFAULT_OUTPUT_DIR = Path("/data/training_hub")


def get_db(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the corrections database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Corrections DB not found at {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def classify_language(text: str) -> str:
    """Detect if text is Arabic, English, mixed, or numeric."""
    if not text:
        return "unknown"
    has_arabic = any("\u0600" <= c <= "\u06FF" for c in text)
    has_latin = any(c.isascii() and c.isalpha() for c in text)
    has_digits = any(c.isdigit() for c in text)
    if has_arabic and has_latin:
        return "mixed"
    if has_arabic:
        return "arabic"
    if has_latin:
        return "english"
    if has_digits:
        return "numeric"
    return "unknown"


def export_corrections(
    db_path: Path = DEFAULT_DB_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    min_confidence: float = 0.0,
) -> Dict:
    """Export all corrections from SQLite to training-hub JSONL format."""
    conn = get_db(db_path)

    # Fetch all corrections
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.crop_base64,
            c.raw_text,
            c.corrected_text,
            c.all_engine_texts,
            c.best_engine,
            c.confidence,
            c.created_at,
            c.image_hash,
            p.frequency as pattern_frequency
        FROM corrections c
        LEFT JOIN correction_patterns p
            ON p.pattern = c.raw_text COLLATE NOCASE
        ORDER BY c.id ASC
        """
    ).fetchall()

    conn.close()

    if not rows:
        logger.warning("No corrections found in database")
        return {"exported": 0, "files": []}

    # Prepare output directories
    crops_dir = output_dir / "training_data" / "word_crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = crops_dir / f"corrections_{timestamp}.jsonl"

    stats = {
        "total": len(rows),
        "changed": 0,
        "unchanged": 0,
        "arabic": 0,
        "english": 0,
        "mixed": 0,
        "numeric": 0,
        "avg_confidence": 0.0,
        "low_confidence_corrected": 0,  # valuable: low conf but corrected
    }

    conf_sum = 0.0
    entries: List[Dict] = []

    for row in rows:
        raw = row["raw_text"] or ""
        corrected = row["corrected_text"] or ""
        is_changed = (raw.strip() != corrected.strip())

        if is_changed:
            stats["changed"] += 1
        else:
            stats["unchanged"] += 1

        conf = float(row["confidence"] or 0.0)
        conf_sum += conf

        lang = classify_language(corrected or raw)
        stats[lang] = stats.get(lang, 0) + 1

        if conf < 0.7 and is_changed:
            stats["low_confidence_corrected"] += 1

        # Parse engine texts
        all_engine_texts = {}
        if row["all_engine_texts"]:
            try:
                all_engine_texts = json.loads(row["all_engine_texts"])
            except (json.JSONDecodeError, TypeError):
                pass

        entry = {
            "id": f"hf_{row['id']:06d}",
            "timestamp": row["created_at"],
            "source": "hf_space_correction",
            "crop_base64": row["crop_base64"] or "",
            "raw_text": raw,
            "corrected_text": corrected,
            "is_changed": is_changed,
            "engine_predictions": all_engine_texts,
            "confidence_scores": {},  # filled from patterns if available
            "best_engine": row["best_engine"] or "",
            "language": lang,
            "image_hash": row["image_hash"] or "",
            "from_db_cache": False,
            "verified": False,
            "verification_count": row["pattern_frequency"] or 0,
        }

        # Derive confidence scores from engine texts (if not stored separately)
        # The HF DB stores all_engine_texts as {engine: display_text}
        # Confidence is stored per-region, not per-engine in current schema
        if conf > 0:
            entry["confidence_scores"][row["best_engine"] or "paddle"] = conf

        entries.append(entry)

    stats["avg_confidence"] = conf_sum / max(len(rows), 1)

    # Write JSONL
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(
        "Exported %d corrections to %s (%d changed, %d unchanged, avg conf %.1f%%)",
        len(entries), output_file.name, stats["changed"], stats["unchanged"],
        stats["avg_confidence"] * 100,
    )

    # Write summary
    summary = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_db": str(db_path),
        "output_file": str(output_file.relative_to(output_dir)),
        "stats": stats,
        "file_count": len(entries),
    }
    summary_file = crops_dir / f"summary_{timestamp}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return {
        "exported": len(entries),
        "files": [str(output_file.relative_to(output_dir)), str(summary_file.relative_to(output_dir))],
        "stats": stats,
    }


def copy_ground_truth_to_hub(
    gt_source: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
):
    """Copy existing ground truth JSONL files to the training hub structure."""
    gt_dir = output_dir / "training_data" / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    if not gt_source.exists():
        logger.warning("Ground truth source not found: %s", gt_source)
        return

    for f in gt_source.glob("*.jsonl"):
        target = gt_dir / f.name
        if not target.exists():
            shutil.copy2(f, target)
            logger.info("Copied ground truth: %s", f.name)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export HF corrections to training hub format")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-confidence", type=float, default=0.0)
    args = parser.parse_args()

    result = export_corrections(
        db_path=args.db_path,
        output_dir=args.output_dir,
        min_confidence=args.min_confidence,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))