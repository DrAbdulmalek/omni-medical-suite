#!/usr/bin/env python3
"""
Collect training data from the HF corrections dataset and local images.

Downloads metadata from DrAbdulmalek/arabic-medical-ocr-corrections,
saves a JSONL manifest, and optionally indexes local image directories.

Usage:
    python scripts/collect_training_data.py
    python scripts/collect_training_data.py --images /path/to/images/
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTPUT = Path("training_data")
HF_DATASET = "DrAbdulmalek/arabic-medical-ocr-corrections"


def collect_from_hf(output_dir: Path) -> bool:
    """Download correction metadata from Hugging Face."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: datasets not installed. Run: pip install datasets")
        return False

    print(f"Loading {HF_DATASET} ...")
    try:
        ds = load_dataset(HF_DATASET)
        df = ds["train"].to_pandas()
    except Exception as exc:
        print(f"ERROR loading dataset: {exc}")
        return False

    print(f"Loaded {len(df)} samples")

    # Save JSONL manifest
    manifest_path = output_dir / "manifest.jsonl"
    count = 0
    with open(manifest_path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            entry = {
                "id": count,
                "incorrect_text": str(row.get("incorrect_ocr_output", "")),
                "correct_text": str(row.get("correct_text", "")),
                "category": str(row.get("category", "unknown")),
                "form": str(row.get("form", "unknown")),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1

    print(f"Saved {count} entries to {manifest_path}")

    # Summary
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": HF_DATASET,
        "total_samples": count,
        "manifest": str(manifest_path),
    }
    (output_dir / "collection_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return True


def index_local_images(images_dir: Path, output_dir: Path) -> int:
    """Create JSONL entries for local image files."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    files = [p for p in images_dir.rglob("*") if p.suffix.lower() in exts]
    if not files:
        print(f"No images found in {images_dir}")
        return 0

    images_manifest = output_dir / "local_images.jsonl"
    with open(images_manifest, "w", encoding="utf-8") as f:
        for img_path in sorted(files):
            entry = {
                "id": img_path.stem,
                "image_path": str(img_path),
                "category": "real_image",
                "ground_truth": "",
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Indexed {len(files)} images to {images_manifest}")
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect OCR training data")
    parser.add_argument(
        "--images",
        type=Path,
        default=None,
        help="Directory of local images to index",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    ok = collect_from_hf(output_dir)

    if args.images:
        index_local_images(args.images, output_dir)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())