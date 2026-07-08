"""
OmniMedical Suite — Benchmark Runner

Runs standardized benchmarks across all OCR engines and post-processing stages.
Produces JSON output suitable for dashboard visualization.

Usage:
    python evaluation/benchmark_runner.py --input-dir ./test-docs/ --output results.json
    python evaluation/benchmark_runner.py --quick  # Run with sample data
"""
import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class BenchmarkResult:
    """Single benchmark measurement."""
    engine: str
    stage: str  # ocr, postprocess, validation, review
    input_file: str
    latency_ms: float
    cer: float  # Character Error Rate
    wer: float  # Word Error Rate
    medical_term_recall: float
    throughput_pages_per_min: float
    memory_mb: float = 0
    gpu_utilization: float = 0


@dataclass
class BenchmarkSuite:
    """Complete benchmark results for a pipeline configuration."""
    profile: str  # lite, standard, gpu-production
    timestamp: str
    results: list[BenchmarkResult]
    summary: dict

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def save(self, path: str):
        Path(path).write_text(self.to_json(), encoding="utf-8")


def run_benchmark(
    input_dir: str,
    engines: list[str] | None = None,
    profile: str = "lite",
    output: str = "benchmark_results.json",
) -> BenchmarkSuite:
    """
    Run benchmark suite across specified engines.

    This is a skeleton implementation. Actual OCR engines should be
    imported from the packages/omni-ocr module.
    """
    if engines is None:
        engines = ["tesseract", "easyocr", "paddleocr"]

    print(f"Running benchmark suite — Profile: {profile}")
    print(f"Engines: {', '.join(engines)}")
    print(f"Input directory: {input_dir}")
    print("")

    results = []

    for engine in engines:
        print(f"  Benchmarking {engine}...")
        # Placeholder: replace with actual OCR engine invocation
        result = BenchmarkResult(
            engine=engine,
            stage="ocr",
            input_file="sample_medical_note.png",
            latency_ms=0,
            cer=0,
            wer=0,
            medical_term_recall=0,
            throughput_pages_per_min=0,
        )
        results.append(result)
        print(f"    CER: {result.cer:.2%} | WER: {result.wer:.2%} | Latency: {result.latency_ms}ms")

    summary = {
        "total_engines_tested": len(engines),
        "best_cer_engine": min(results, key=lambda r: r.cer).engine if results else None,
        "best_latency_engine": min(results, key=lambda r: r.latency_ms).engine if results else None,
        "avg_cer": sum(r.cer for r in results) / len(results) if results else 0,
        "avg_wer": sum(r.wer for r in results) / len(results) if results else 0,
    }

    suite = BenchmarkSuite(
        profile=profile,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        results=results,
        summary=summary,
    )

    suite.save(output)
    print(f"\nResults saved to {output}")
    return suite


def main():
    parser = argparse.ArgumentParser(description="OmniMedical Benchmark Runner")
    parser.add_argument("--input-dir", type=str, default="./test-docs/")
    parser.add_argument("--output", type=str, default="benchmark_results.json")
    parser.add_argument("--engines", nargs="+", default=["tesseract", "easyocr"])
    parser.add_argument("--profile", choices=["lite", "standard", "gpu-production"], default="lite")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmark with sample data")

    args = parser.parse_args()

    if args.quick:
        print("Quick benchmark mode — using sample data")
        args.input_dir = "./evaluation/samples/"

    run_benchmark(
        input_dir=args.input_dir,
        engines=args.engines,
        profile=args.profile,
        output=args.output,
    )


if __name__ == "__main__":
    main()
