"""
OpenTelemetry tracing and metrics setup for OmniMedical Suite.
Provides distributed tracing with Grafana Tempo and Prometheus metrics.
"""
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_tracer = None
_meter = None
_counter_ocr_total = None
_histogram_ocr_duration = None
_initialized = False


def init_telemetry(
    service_name: Optional[str] = None,
    endpoint: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> None:
    """
    Initialize OpenTelemetry tracing and metrics.
    Gracefully handles missing opentelemetry packages.
    """
    global _tracer, _meter, _counter_ocr_total, _histogram_ocr_duration, _initialized
    
    if _initialized:
        return
    
    try:
        from app.core.config import settings as cfg
        
        svc = service_name or cfg.OTEL_SERVICE_NAME
        ep = endpoint or cfg.OTEL_EXPORTER_OTLP_ENDPOINT
        is_enabled = enabled if enabled is not None else cfg.OTEL_ENABLED
        
        if not is_enabled:
            logger.info("OpenTelemetry is disabled by configuration.")
            return
        
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        
        resource = Resource.create({SERVICE_NAME: svc})
        
        # Tracing setup
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        
        otlp_exporter = OTLPSpanExporter(endpoint=ep)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        _tracer = trace.get_tracer(svc)
        
        # Metrics setup
        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=ep))
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        
        _meter = metrics.get_meter(svc)
        
        _counter_ocr_total = _meter.create_counter(
            name="ocr_requests_total",
            description="Total OCR processing requests",
            unit="1",
        )
        
        _histogram_ocr_duration = _meter.create_histogram(
            name="ocr_request_duration_seconds",
            description="OCR request processing duration",
            unit="s",
        )
        
        _initialized = True
        logger.info(f"OpenTelemetry initialized: service={svc}, endpoint={ep}")
        
    except ImportError:
        logger.warning("OpenTelemetry packages not installed. Tracing disabled.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")


def get_tracer():
    """Get the configured tracer instance."""
    if _tracer is None:
        init_telemetry()
    return _tracer


def record_ocr_request(engine: str, duration: float, success: bool = True):
    """Record an OCR processing metric."""
    global _counter_ocr_total, _histogram_ocr_duration
    if _counter_ocr_total is None:
        return
    attrs = {"ocr.engine": engine, "ocr.success": str(success).lower()}
    _counter_ocr_total.add(1, attributes=attrs)
    _histogram_ocr_duration.record(duration, attributes=attrs)


@contextmanager
def trace_operation(name: str, attributes: Optional[dict] = None):
    """Context manager for tracing an operation."""
    tracer = get_tracer()
    if tracer is None:
        yield None
        return
    
    with tracer.start_as_current_span(name, attributes=attributes or {}) as span:
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise


class PeriodicExportingMetricReader:
    """Lightweight fallback for metric reader."""
    def __init__(self, exporter):
        self.exporter = exporter
