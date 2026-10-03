#!/usr/bin/env python3
"""Reproducible local benchmark for the production OCR service path.

This measures real OCR engine calls plus the canonical OCR correction stage.
It intentionally does not invent a baseline: the script prints measured
P50/P95 values from the supplied image and runtime.

Example:
    python scripts/benchmark_ocr_service.py --image ./sample.png --warmup 1 --runs 10
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import cv2

from app.services import ocr_service


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def measure(name: str, fn, warmup: int, runs: int) -> dict[str, float | int | str]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - started)
    return {
        "stage": name,
        "runs": runs,
        "min_s": min(samples),
        "mean_s": statistics.fmean(samples),
        "p50_s": percentile(samples, 0.50),
        "p95_s": percentile(samples, 0.95),
        "max_s": max(samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()

    if args.warmup < 0 or args.runs < 1:
        parser.error("--warmup must be >= 0 and --runs must be >= 1")

    image = cv2.imread(str(args.image))
    if image is None:
        parser.error(f"unable to read image: {args.image}")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    results: list[dict[str, float | int | str]] = []
    paddle = ocr_service.get_paddle_ocr()
    if paddle is not None:
        results.append(
            measure(
                "paddleocr",
                lambda: ocr_service._run_paddle_ocr(image),
                args.warmup,
                args.runs,
            )
        )
    if ocr_service.has_tesseract():
        results.append(
            measure(
                "tesseract",
                lambda: ocr_service._run_tesseract(image),
                args.warmup,
                args.runs,
            )
        )

    # Keep correction timing separate from engine timing so the baseline can
    # distinguish OCR latency from the safety-critical correction stage.
    results.append(
        measure(
            "canonical_ocr_correction",
            lambda: ocr_service._auto_correct_ocr("باراسيتبمول 500 mg"),
            args.warmup,
            args.runs,
        )
    )

    print(json.dumps({"image": str(args.image), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
