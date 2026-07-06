"""
AI Fuel Engine - Prometheus Metrics Module

Defines the standard Prometheus metrics exposed by the AI Fuel Engine
pipeline.  Each metric is instrumented with labels that allow drill-down
by category, method, and PHI type.

Usage::

    from core.metrics import documents_processed, chunks_created

    documents_processed.labels(source_file="report.pdf").inc()
    chunks_created.labels(category="radiology", method="semantic").inc(3)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Prometheus client is optional — the module works without it by
# providing no-op metric wrappers so that the rest of the codebase
# can import these symbols unconditionally.
# ------------------------------------------------------------------

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.info(
        "prometheus_client not installed — metrics will be no-ops. "
        "Install with: pip install prometheus-client"
    )


# ======================================================================
# No-op Fallback Classes
# ======================================================================

if _PROMETHEUS_AVAILABLE:
    _Counter = Counter
    _Gauge = Gauge
    _Histogram = Histogram
else:

    class _NoOpMetric:
        """Base no-op metric that silently accepts any call."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def labels(self, **kwargs: object) -> "_NoOpMetric":
            return self

        def inc(self, amount: float = 1.0) -> None:
            pass

        def dec(self, amount: float = 1.0) -> None:
            pass

        def set(self, value: float) -> None:
            pass

        def observe(self, amount: float) -> None:
            pass

        def time(self) -> object:
            """Context-manager stub that returns itself."""
            return self

        def __enter__(self) -> "_NoOpMetric":
            return self

        def __exit__(self, *args: object) -> None:
            pass

    class _Counter(_NoOpMetric):
        pass

    class _Gauge(_NoOpMetric):
        pass

    class _Histogram(_NoOpMetric):
        pass


# ======================================================================
# Metric Definitions
# ======================================================================

# ── Counters ─────────────────────────────────────────────────────────

documents_processed: _Counter = _Counter(
    "ai_fuel_documents_processed_total",
    "Total number of documents processed through the pipeline.",
    ["source_type", "status"],
)

chunks_created: _Counter = _Counter(
    "ai_fuel_chunks_created_total",
    "Total number of chunks created during segmentation.",
    ["chunk_type"],
)

classification_operations: _Counter = _Counter(
    "ai_fuel_classification_operations_total",
    "Total number of classification operations performed.",
    ["method", "category"],
)

phi_detections: _Counter = _Counter(
    "ai_fuel_phi_detections_total",
    "Total number of PHI detections across all documents.",
    ["phi_type", "mode"],
)

dedup_duplicates_found: _Counter = _Counter(
    "ai_fuel_dedup_duplicates_found_total",
    "Total number of duplicate chunks identified.",
    ["method"],
)

export_operations: _Counter = _Counter(
    "ai_fuel_export_operations_total",
    "Total number of export operations performed.",
    ["format", "status"],
)

active_learning_samples: _Counter = _Counter(
    "ai_fuel_active_learning_samples_total",
    "Total number of samples sent for human review.",
    ["status"],
)

# ── Gauges ───────────────────────────────────────────────────────────

classification_accuracy: _Gauge = _Gauge(
    "ai_fuel_classification_accuracy",
    "Current classification accuracy (updated after human review feedback).",
    ["method"],
)

dedup_rate: _Gauge = _Gauge(
    "ai_fuel_dedup_rate",
    "Ratio of duplicate chunks to total chunks (0.0 – 1.0).",
    ["method"],
)

avg_confidence_score: _Gauge = _Gauge(
    "ai_fuel_avg_confidence_score",
    "Rolling average classification confidence score.",
)

pending_review_count: _Gauge = _Gauge(
    "ai_fuel_pending_review_count",
    "Number of samples currently pending human review.",
)

pipeline_health: _Gauge = _Gauge(
    "ai_fuel_pipeline_health",
    "Pipeline health indicator (1 = healthy, 0 = unhealthy).",
)

# ── Histograms ───────────────────────────────────────────────────────

processing_duration: _Histogram = _Histogram(
    "ai_fuel_processing_duration_seconds",
    "Time taken to process a single document through the full pipeline.",
    ["source_type"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

segmentation_duration: _Histogram = _Histogram(
    "ai_fuel_segmentation_duration_seconds",
    "Time taken to segment a single document into chunks.",
    ["chunk_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

classification_duration: _Histogram = _Histogram(
    "ai_fuel_classification_duration_seconds",
    "Time taken to classify a single chunk.",
    ["method"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

chunk_token_count: _Histogram = _Histogram(
    "ai_fuel_chunk_token_count",
    "Distribution of chunk sizes in tokens.",
    buckets=(50, 100, 200, 500, 1000, 2000, 3000, 4000, 5000),
)


# ======================================================================
# Helper Functions
# ======================================================================


def start_metrics_server(port: int = 8000) -> None:
    """Start a Prometheus metrics HTTP server on the given port.

    This is a no-op if ``prometheus_client`` is not installed.

    Args:
        port: Port to serve metrics on (default 8000).
    """
    if not _PROMETHEUS_AVAILABLE:
        logger.warning("Cannot start metrics server — prometheus_client not installed")
        return

    try:
        start_http_server(port)
        logger.info("Prometheus metrics server started on port %d (/metrics)", port)
    except OSError as exc:
        logger.error("Failed to start Prometheus metrics server on port %d: %s", port, exc)


def is_metrics_available() -> bool:
    """Check whether Prometheus metrics are available (client library installed).

    Returns:
        ``True`` if ``prometheus_client`` is importable.
    """
    return _PROMETHEUS_AVAILABLE
