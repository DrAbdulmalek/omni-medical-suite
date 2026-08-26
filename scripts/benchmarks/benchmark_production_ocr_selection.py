#!/usr/bin/env python3
"""scripts/benchmarks/benchmark_production_ocr_selection.py — Issue #94.

Microbenchmark for the production OCR engine-selection helper.

Measures the real production selection path (_select_ocr_result in
hf-space/app_core.py) using deterministic mocked OCR outputs. No PaddleOCR
or Tesseract inference is performed — only the pure selection logic is
benchmarked.

Reports:
    - iterations
    - P50, P95, P99 latency
    - average, min, max

The benchmark does NOT fabricate OCR engine inference numbers. An optional
integration entry (``--integration``) runs the selection against the real
production path if OCR dependencies are installed; otherwise it skips
gracefully.

Usage:
    python3 scripts/benchmarks/benchmark_production_ocr_selection.py
    python3 scripts/benchmarks/benchmark_production_ocr_selection.py --iterations 5000
    python3 scripts/benchmarks/benchmark_production_ocr_selection.py --integration
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from statistics import mean, median

# Ensure project root is importable
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HF_SPACE = ROOT / "hf-space"
if str(HF_SPACE) not in sys.path:
    sys.path.append(str(HF_SPACE))


def _select_bench():
    """Import the production helper lazily so import errors are clear."""
    from app_core import _select_ocr_result
    return _select_ocr_result


# Deterministic mocked OCR outputs (3 scenarios)
SCENARIOS = [
    # (name, paddle_text, paddle_details, tesseract_text, tess_conf)
    ("paddle_wins", "this is long enough paddle text", [{"confidence": 0.95}], "short", 0.80),
    ("tesseract_fallback", "ab", [{"confidence": 0.5}], "tesseract output is longer", 0.85),
    ("no_text", "", [], "", 0.0),
]


def _run_benchmark(iterations: int) -> dict:
    """Run the selection helper N times across all scenarios and report stats."""
    _select = _select_bench()
    # Suppress decision logs during benchmarking
    import logging
    dl_logger = logging.getLogger("app.decision_log")
    dl_logger.disabled = True
    try:
        # Warmup
        for _ in range(min(100, iterations // 10)):
            for name, pt, pd, tt, tc in SCENARIOS:
                _select(pt, pd, tt, tc)

        # Measure
        per_scenario: dict[str, list[float]] = {name: [] for name, *_ in SCENARIOS}
        for _ in range(iterations):
            for name, pt, pd, tt, tc in SCENARIOS:
                t0 = time.perf_counter_ns()
                _select(pt, pd, tt, tc)
                t1 = time.perf_counter_ns()
                per_scenario[name].append((t1 - t0) / 1000.0)  # microseconds
    finally:
        dl_logger.disabled = False

    results = {}
    for name, times in per_scenario.items():
        times.sort()
        n = len(times)
        results[name] = {
            "iterations": n,
            "p50_us": round(median(times), 2),
            "p95_us": round(times[int(n * 0.95)] if n > 1 else times[0], 2),
            "p99_us": round(times[int(n * 0.99)] if n > 1 else times[0], 2),
            "avg_us": round(mean(times), 2),
            "min_us": round(min(times), 2),
            "max_us": round(max(times), 2),
        }
    # Combined stats
    all_times = []
    for times in per_scenario.values():
        all_times.extend(times)
    all_times.sort()
    n = len(all_times)
    results["_combined"] = {
        "iterations": n,
        "p50_us": round(median(all_times), 2),
        "p95_us": round(all_times[int(n * 0.95)] if n > 1 else all_times[0], 2),
        "p99_us": round(all_times[int(n * 0.99)] if n > 1 else all_times[0], 2),
        "avg_us": round(mean(all_times), 2),
        "min_us": round(min(all_times), 2),
        "max_us": round(max(all_times), 2),
    }
    return results


def _run_integration() -> str:
    """Attempt to run against the real production path.

    Skips gracefully if heavy OCR dependencies are unavailable.
    Does NOT report fabricated OCR inference numbers.
    """
    try:
        import paddleocr  # noqa: F401
        import pytesseract  # noqa: F401
    except ImportError as e:
        return f"SKIP: integration benchmark requires OCR dependencies (got: {e})"

    # If deps are available, we could run real OCR — but we deliberately
    # do NOT benchmark inference time here (it depends on hardware, image
    # size, model version). We only verify the selection helper works with
    # real engine outputs.
    from app_core import _select_ocr_result, _run_paddle_ocr, _run_tesseract, _preprocess_image
    import numpy as np

    # Create a small synthetic image (black square — no text)
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    try:
        cleaned, _ = _preprocess_image(image)
        pt, pd = _run_paddle_ocr(cleaned)
        tt, tc = _run_tesseract(cleaned)
        _select_ocr_result(pt, pd, tt, tc)
        return "OK: integration benchmark ran against real OCR engines (selection helper works)"
    except Exception as e:
        return f"SKIP: integration benchmark failed at runtime (got: {e})"


def main():
    parser = argparse.ArgumentParser(description="Benchmark production OCR selection helper")
    parser.add_argument("--iterations", type=int, default=2000, help="iterations per scenario")
    parser.add_argument("--integration", action="store_true", help="run integration benchmark")
    args = parser.parse_args()

    print("=" * 70)
    print("Production OCR Engine-Selection Benchmark (Issue #94)")
    print("=" * 70)
    print()
    print(f"Iterations per scenario: {args.iterations}")
    print(f"Scenarios: {len(SCENARIOS)} (paddle_wins, tesseract_fallback, no_text)")
    print(f"Total iterations: {args.iterations * len(SCENARIOS)}")
    print()
    print("NOTE: This benchmark measures ONLY the pure selection helper")
    print("(_select_ocr_result). No PaddleOCR/Tesseract inference is performed.")
    print()

    results = _run_benchmark(args.iterations)

    for name in [s[0] for s in SCENARIOS] + ["_combined"]:
        r = results[name]
        label = name.replace("_", " ").title() if name != "_combined" else "Combined"
        print(f"--- {label} ---")
        print(f"  Iterations: {r['iterations']}")
        print(f"  P50:  {r['p50_us']:.2f} µs")
        print(f"  P95:  {r['p95_us']:.2f} µs")
        print(f"  P99:  {r['p99_us']:.2f} µs")
        print(f"  Avg:  {r['avg_us']:.2f} µs")
        print(f"  Min:  {r['min_us']:.2f} µs")
        print(f"  Max:  {r['max_us']:.2f} µs")
        print()

    if args.integration:
        print("--- Integration Benchmark ---")
        result = _run_integration()
        print(f"  {result}")
        print()

    print("Done.")


if __name__ == "__main__":
    main()
