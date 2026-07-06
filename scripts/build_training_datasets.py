#!/usr/bin/env python3
"""
Build training datasets from the hub's word_crops and ground_truth data.

Reads from training_data/word_crops/ and training_data/ground_truth/
Writes to training_data/exports/ in formats ready for each model.

Usage:
    python build_training_datasets.py [--all] [--trocr] [--paddleocr] [--postprocessor]
"""

import json
import logging
import os
import shutil
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HUB_ROOT = Path(__file__).parent.parent
WORD_CROPS_DIR = HUB_ROOT / "training_data" / "word_crops"
GROUND_TRUTH_DIR = HUB_ROOT / "training_data" / "ground_truth"
EXPORTS_DIR = HUB_ROOT / "training_data" / "exports"


def load_all_word_corrections() -> List[Dict]:
    """Load all correction entries from word_crops JSONL files."""
    entries = []
    for f in sorted(WORD_CROPS_DIR.glob("corrections_*.jsonl")):
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    logger.info("Loaded %d word corrections from %s", len(entries), WORD_CROPS_DIR)
    return entries


def load_all_ground_truth() -> List[Dict]:
    """Load all ground truth entries."""
    entries = []
    for f in sorted(GROUND_TRUTH_DIR.glob("*.jsonl")):
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    logger.info("Loaded %d ground truth entries from %s", len(entries), GROUND_TRUTH_DIR)
    return entries


def build_trocr_dataset(corrections: List[Dict], ground_truth: List[Dict]):
    """
    Build TrOCR fine-tuning dataset.
    Format: images/ + metadata.jsonl with {file_name, text}
    """
    output_dir = EXPORTS_DIR / "trocr_hf"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Use corrections that have crop images and were changed (valuable training signal)
    trainable = [c for c in corrections if c.get("is_changed") and c.get("crop_base64")]
    logger.info("TrOCR: %d trainable entries (changed + have crop)", len(trainable))

    if not trainable:
        # Also include unchanged high-confidence as positive examples
        trainable = [c for c in corrections if c.get("crop_base64")]
        logger.info("TrOCR: falling back to %d entries with crops", len(trainable))

    metadata = []
    for i, entry in enumerate(trainable):
        crop_b64 = entry.get("crop_base64", "")
        if not crop_b64:
            continue

        # Save crop image
        image_name = f"crop_{i:06d}_{entry.get('id', 'unknown')}.png"
        image_path = images_dir / image_name

        try:
            img_data = b64decode(crop_b64)
            with open(image_path, "wb") as f:
                f.write(img_data)
        except Exception as e:
            logger.warning("Failed to save crop %s: %s", image_name, e)
            continue

        metadata.append({
            "file_name": f"images/{image_name}",
            "text": entry.get("corrected_text", entry.get("raw_text", "")),
            "original_text": entry.get("raw_text", ""),
            "language": entry.get("language", "unknown"),
            "source_id": entry.get("id", ""),
        })

    # Write metadata
    meta_path = output_dir / "metadata.jsonl"
    with open(meta_path, "w", encoding="utf-8") as f:
        for m in metadata:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    logger.info("TrOCR dataset: %d images saved to %s", len(metadata), output_dir)
    return len(metadata)


def build_paddleocr_dataset(corrections: List[Dict]):
    """
    Build PaddleOCR custom dictionary and LM training data.
    Extracts unique characters and word patterns from corrections.
    """
    output_dir = EXPORTS_DIR / "paddleocr_custom"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract unique characters from corrected text
    all_chars = set()
    word_freq = {}

    for entry in corrections:
        corrected = entry.get("corrected_text", "")
        for ch in corrected:
            all_chars.add(ch)

        # Word frequency (for dictionary building)
        for word in corrected.split():
            word = word.strip()
            if word and len(word) > 1:
                word_freq[word] = word_freq.get(word, 0) + 1

    # Write custom character dictionary
    dict_path = output_dir / "custom_dict.txt"
    # Sort: Arabic chars first, then Latin, then digits/symbols
    arabic = sorted([c for c in all_chars if "\u0600" <= c <= "\u06FF"])
    latin = sorted([c for c in all_chars if c.isascii() and c.isalpha()])
    other = sorted([c for c in all_chars if c not in arabic and c not in latin])

    with open(dict_path, "w", encoding="utf-8") as f:
        for c in arabic + latin + other:
            f.write(c + "\n")

    # Write word frequency dictionary
    words_path = output_dir / "word_frequency.json"
    sorted_words = sorted(word_freq.items(), key=lambda x: -x[1])
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump(sorted_words[:5000], f, ensure_ascii=False, indent=2)

    # Write correction patterns for postprocessing
    patterns = []
    for entry in corrections:
        if entry.get("is_changed"):
            patterns.append({
                "raw": entry.get("raw_text", ""),
                "corrected": entry.get("corrected_text", ""),
                "frequency": entry.get("verification_count", 1),
            })

    patterns_path = output_dir / "correction_patterns.json"
    with open(patterns_path, "w", encoding="utf-8") as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)

    logger.info(
        "PaddleOCR dataset: %d chars, %d words, %d correction patterns",
        len(all_chars), len(word_freq), len(patterns),
    )
    return {"chars": len(all_chars), "words": len(word_freq), "patterns": len(patterns)}


def build_postprocessor_dataset(corrections: List[Dict]):
    """
    Build correction pairs for the postprocessor.
    Format: one JSONL with {raw, corrected, frequency, language}
    """
    output_dir = EXPORTS_DIR / "correction_pairs"
    output_dir.mkdir(parents=True, exist_ok=True)

    pairs = []
    for entry in corrections:
        if entry.get("is_changed"):
            pairs.append({
                "raw": entry.get("raw_text", ""),
                "corrected": entry.get("corrected_text", ""),
                "frequency": entry.get("verification_count", 1) + 1,
                "language": entry.get("language", "unknown"),
            })

    output_path = output_dir / "correction_pairs.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    logger.info("Postprocessor dataset: %d correction pairs", len(pairs))
    return len(pairs)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build training datasets from hub data")
    parser.add_argument("--all", action="store_true", help="Build all datasets")
    parser.add_argument("--trocr", action="store_true", help="Build TrOCR dataset")
    parser.add_argument("--paddleocr", action="store_true", help="Build PaddleOCR dataset")
    parser.add_argument("--postprocessor", action="store_true", help="Build postprocessor dataset")
    args = parser.parse_args()

    if not any([args.all, args.trocr, args.paddleocr, args.postprocessor]):
        args.all = True

    corrections = load_all_word_corrections()
    ground_truth = load_all_ground_truth()

    if not corrections and not ground_truth:
        logger.error("No training data found. Add corrections via HF Space first.")
        return

    results = {}

    if args.all or args.trocr:
        results["trocr"] = build_trocr_dataset(corrections, ground_truth)

    if args.all or args.paddleocr:
        results["paddleocr"] = build_paddleocr_dataset(corrections)

    if args.all or args.postprocessor:
        results["postprocessor"] = build_postprocessor_dataset(corrections)

    # Write build summary
    summary = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_corrections": len(corrections),
        "source_ground_truth": len(ground_truth),
        "results": results,
    }
    summary_path = EXPORTS_DIR / f"build_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nBuild complete. Summary: {json.dumps(results, indent=2)}")
    print(f"Details: {summary_path}")


if __name__ == "__main__":
    main()