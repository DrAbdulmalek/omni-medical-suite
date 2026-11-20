#!/usr/bin/env python3
"""
download_models.py — Download offline OCR models for Android APK
================================================================
يحمّل النماذج المطلوبة إلى assets/models/ قبل بناء APK،
حتى يكون التطبيق offline-first (لا يحتاج اتصال عند أول تشغيل).

النماذج:
  • TrOCR (ar-handwritten + ar-printed) — ONNX
  • EasyOCR Arabic
  • Tesseract ara.traineddata
  • Arabic medical spellchecker (local JSON)

Usage:
    python download_models.py            # تنزيل الكل
    python download_models.py --dry-run  # عرض ما سيُنزَّل
    python download_models.py --clean    # حذف الموجود

Total expected size: ~140 MB
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("download_models")

MODELS_DIR = Path(__file__).parent / "assets" / "models"

MODELS = [
    # (filename, repo_id, repo_path, expected_mb)
    ("trocr-ar-handwritten.onnx", "microsoft/trocr-base-handwritten", "onnx/model.onnx", 110),
    ("trocr-ar-printed.onnx", "microsoft/trocr-base-printed", "onnx/model.onnx", 95),
    ("easyocr-arabic.pth", "JaidedAI/EasyOCR", "model_arabic.pth", 45),
    ("ara.traineddata", "tesseract-ocr/tessdata_fast", "ara.traineddata", 12),
    ("ar-medical-spell.json", "DrAbdulmalek/omni-medical-suite", "data/ar-medical-spell.json", 2),
]


def download(dry_run: bool = False) -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        log.error("huggingface_hub غير مثبت. ثبّته: pip install huggingface_hub")
        return 1

    total_mb = 0
    for filename, repo, path, expected in MODELS:
        target = MODELS_DIR / filename
        if target.exists():
            actual_mb = target.stat().st_size / 1024 / 1024
            log.info("✓ exists: %s (%.1f MB)", filename, actual_mb)
            total_mb += actual_mb
            continue

        log.info("↓ %s (%d MB) from %s", filename, expected, repo)
        if dry_run:
            total_mb += expected
            continue

        try:
            local = hf_hub_download(repo_id=repo, filename=path, cache_dir=str(MODELS_DIR / "_hub"))
            shutil.copy(local, target)
            shutil.rmtree(MODELS_DIR / "_hub", ignore_errors=True)
            actual_mb = target.stat().st_size / 1024 / 1024
            total_mb += actual_mb
            log.info("  ✓ %.1f MB", actual_mb)
        except Exception as e:
            log.error("  ✗ failed: %s", e)
            log.error("    you may need: huggingface-cli login")
            return 1

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("total: %.1f MB in %s", total_mb, MODELS_DIR)
    if total_mb > 60:
        log.warning("⚠ bundled models >60MB — APK may exceed 150MB")
    else:
        log.info("✓ within APK size budget")
    return 0


def clean() -> int:
    if MODELS_DIR.exists():
        shutil.rmtree(MODELS_DIR)
        log.info("✓ removed %s", MODELS_DIR)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Download offline OCR models")
    parser.add_argument("--dry-run", action="store_true", help="show what would be downloaded")
    parser.add_argument("--clean", action="store_true", help="remove all models")
    args = parser.parse_args()

    if args.clean:
        sys.exit(clean())
    sys.exit(download(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
