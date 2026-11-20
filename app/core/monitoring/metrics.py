"""
OmniMedical Suite — Prometheus Metrics.

Defines all Prometheus metrics for the API and OCR services.
Provides a FastAPI/Starlette middleware for automatic HTTP metrics collection,
and a standalone /metrics endpoint for Prometheus scraping.

Usage (FastAPI):
    from app.core.monitoring.metrics import add_metrics_middleware, metrics_route
    app = FastAPI()
    add_metrics_middleware(app)
    app.add_route("/metrics", metrics_route)

Usage (standalone / Gradio):
    from prometheus_client import start_http_server
    start_http_server(9091)  # Separate port for Gradio apps
"""

import time
from collections.abc import Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── HTTP Metrics ──────────────────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "omni_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "http_status"],
)

HTTP_REQUEST_LATENCY = Histogram(
    "omni_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

ACTIVE_REQUESTS = Gauge(
    "omni_http_active_requests",
    "Number of requests currently being processed",
)

# ── OCR Metrics ───────────────────────────────────────────────────────────────

OCR_PROCESSING_TIME = Histogram(
    "omni_ocr_processing_seconds",
    "OCR processing time in seconds",
    ["engine", "language"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)

OCR_REQUESTS_TOTAL = Counter(
    "omni_ocr_requests_total",
    "Total OCR processing requests",
    ["engine", "language", "status"],
)

OCR_CONFIDENCE = Histogram(
    "omni_ocr_confidence_score",
    "OCR output confidence scores",
    ["engine"],
    buckets=[0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99],
)

# ── Translation Metrics ──────────────────────────────────────────────────────

TRANSLATION_TIME = Histogram(
    "omni_translation_seconds",
    "Translation processing time in seconds",
    ["source_lang", "target_lang"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
)

TRANSLATION_REQUESTS_TOTAL = Counter(
    "omni_translation_requests_total",
    "Total translation requests",
    ["source_lang", "target_lang", "status"],
)

# ── Model Accuracy Metrics ───────────────────────────────────────────────────

MODEL_ACCURACY = Gauge(
    "omni_model_accuracy",
    "Model accuracy metrics",
    ["model_type", "metric_type"],
)

# ── System Metrics ───────────────────────────────────────────────────────────

PADDLEOCR_MODEL_LOADED = Gauge(
    "omni_paddleocr_model_loaded",
    "Whether PaddleOCR model is loaded (1=yes, 0=no)",
)

TESSERACT_AVAILABLE = Gauge(
    "omni_tesseract_available",
    "Whether Tesseract is available (1=yes, 0=no)",
)


def record_ocr_processing(
    engine: str, language: str, duration: float, status: str = "success"
):
    """Record an OCR processing event."""
    OCR_PROCESSING_TIME.labels(engine=engine, language=language).observe(duration)
    OCR_REQUESTS_TOTAL.labels(
        engine=engine, language=language, status=status
    ).inc()


def record_translation(
    source_lang: str, target_lang: str, duration: float, status: str = "success"
):
    """Record a translation event."""
    TRANSLATION_TIME.labels(
        source_lang=source_lang, target_lang=target_lang
    ).observe(duration)
    TRANSLATION_REQUESTS_TOTAL.labels(
        source_lang=source_lang, target_lang=target_lang, status=status
    ).inc()


# ── FastAPI Middleware ───────────────────────────────────────────────────────

def add_metrics_middleware(app):
    """Add Prometheus metrics middleware to a FastAPI/Starlette app."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            ACTIVE_REQUESTS.inc()
            start = time.time()
            try:
                response = await call_next(request)
                status = str(response.status_code)
                return response
            except Exception:
                status = "500"
                raise
            finally:
                duration = time.time() - start
                # Normalize endpoint path (remove IDs)
                path = request.url.path
                for pattern in [r"/\d+", r"/[^/]{8,}"]:
                    import re
                    path = re.sub(pattern, "/:id", path)
                HTTP_REQUEST_LATENCY.labels(endpoint=path).observe(duration)
                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method, endpoint=path, http_status=status
                ).inc()
                ACTIVE_REQUESTS.dec()

    app.add_middleware(MetricsMiddleware)


# ── Metrics Route ────────────────────────────────────────────────────────────

async def metrics_route(scope, receive, send):
    """ASGI endpoint for Prometheus scraping at /metrics."""
    body = generate_latest(REGISTRY)
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", CONTENT_TYPE_LATEST.encode()]],
        }
    )
    await send({"type": "http.response.body", "body": body})
