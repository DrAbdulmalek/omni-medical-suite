"""
OmniMedical Suite — OCR Benchmark Tracker.

Records OCR processing benchmarks (latency, accuracy) and provides
aggregation methods for reporting. Benchmarks are persisted to a JSONL
file for long-term tracking and can be exported to Prometheus metrics.

Usage:
    from app.core.monitoring.benchmarks import BenchmarkTracker
    tracker = BenchmarkTracker()
    tracker.record(engine="paddleocr", language="ar", duration=2.3, cer=0.042, wer=0.089)
    stats = tracker.get_stats("paddleocr")
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.monitoring.metrics import MODEL_ACCURACY, OCR_PROCESSING_TIME


@dataclass
class OCRBenchmark:
    """Single OCR processing benchmark record."""
    engine: str
    language: str
    duration: float  # seconds
    cer: float | None = None  # Character Error Rate
    wer: float | None = None  # Word Error Rate
    confidence: float | None = None  # Average confidence
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    image_id: str | None = None


class BenchmarkTracker:
    """
    Tracks OCR benchmarks in memory and optionally persists to disk.
    Thread-safe for single-process usage (FastAPI/Gradio).
    """

    def __init__(self, storage_path: str | None = None):
        """
        Args:
            storage_path: Path to JSONL file for persistent storage.
                         If None, benchmarks are kept in memory only.
        """
        self._benchmarks: list[OCRBenchmark] = []
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path and self._storage_path.exists():
            self._load_from_disk()

    def record(
        self,
        engine: str,
        language: str,
        duration: float,
        cer: float | None = None,
        wer: float | None = None,
        confidence: float | None = None,
        image_id: str | None = None,
    ):
        """Record an OCR benchmark and push to Prometheus."""
        benchmark = OCRBenchmark(
            engine=engine,
            language=language,
            duration=duration,
            cer=cer,
            wer=wer,
            confidence=confidence,
            image_id=image_id,
        )
        self._benchmarks.append(benchmark)

        # Push to Prometheus metrics
        OCR_PROCESSING_TIME.labels(engine=engine, language=language).observe(duration)
        if cer is not None:
            MODEL_ACCURACY.labels(model_type=engine, metric_type="cer").set(cer)
        if wer is not None:
            MODEL_ACCURACY.labels(model_type=engine, metric_type="wer").set(wer)

        # Persist to disk
        if self._storage_path:
            self._append_to_disk(benchmark)

    def get_stats(self, engine: str | None = None) -> dict:
        """Get aggregated statistics for an engine (or all engines)."""
        filtered = (
            [b for b in self._benchmarks if b.engine == engine]
            if engine
            else self._benchmarks
        )
        if not filtered:
            return {"count": 0}

        durations = [b.duration for b in filtered]
        cers = [b.cer for b in filtered if b.cer is not None]
        wers = [b.wer for b in filtered if b.wer is not None]
        confs = [b.confidence for b in filtered if b.confidence is not None]

        return {
            "count": len(filtered),
            "duration": {
                "avg": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
                "p95": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 20 else max(durations),
            },
            "cer": {
                "avg": sum(cers) / len(cers) if cers else None,
                "min": min(cers) if cers else None,
                "max": max(cers) if cers else None,
            },
            "wer": {
                "avg": sum(wers) / len(wers) if wers else None,
                "min": min(wers) if wers else None,
                "max": max(wers) if wers else None,
            },
            "confidence": {
                "avg": sum(confs) / len(confs) if confs else None,
            },
        }

    def get_recent(self, n: int = 20) -> list[dict]:
        """Get the last N benchmarks."""
        return [asdict(b) for b in self._benchmarks[-n:]]

    def _append_to_disk(self, benchmark: OCRBenchmark):
        """Append a single benchmark as JSONL."""
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(benchmark), default=str) + "\n")

    def _load_from_disk(self):
        """Load benchmarks from JSONL file."""
        if self._storage_path and self._storage_path.exists():
            with open(self._storage_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            self._benchmarks.append(OCRBenchmark(**data))
                        except (json.JSONDecodeError, TypeError):
                            continue
