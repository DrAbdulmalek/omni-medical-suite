# Monitoring Guide — OmniMedical Suite

> **Last updated:** Phase 5 — Full observability stack across all deployment tiers.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Structured Logging](#2-structured-logging)
3. [Prometheus Metrics](#3-prometheus-metrics)
4. [Alerting](#4-alerting)
5. [Sentry Error Tracking](#5-sentry-error-tracking)
6. [Grafana Dashboards](#6-grafana-dashboards)
7. [Benchmark Tracking](#7-benchmark-tracking)
8. [Docker Compose Monitoring](#8-docker-compose-monitoring)
9. [HF Spaces Monitoring](#9-hf-spaces-monitoring)

---

## 1. Overview

OmniMedical Suite uses a **three-layer monitoring approach** to provide complete operational visibility across every deployment tier (lite, standard, production). Each layer answers a different class of questions and together they form a comprehensive observability story that covers everything from low-level infrastructure health to high-level business KPIs.

### Layer 1 — Application Metrics (Prometheus)

The application layer captures everything the code explicitly instruments: HTTP request rates and latencies, OCR processing times per engine and language, translation durations, model accuracy gauges (CER, WER), and system readiness flags (PaddleOCR model loaded, Tesseract available). These metrics are exposed at the `/metrics` endpoint in Prometheus exposition format and scraped every 10 seconds in standard deployments. This layer answers questions like "How long does PaddleOCR take on Arabic prescriptions?" or "What is our P95 API latency right now?"

### Layer 2 — Infrastructure (Prometheus exporters + cAdvisor)

Infrastructure metrics cover the resources that the application depends on: PostgreSQL connection pool utilization (via `postgres-exporter`), Redis memory and hit rates (via `redis-exporter`), Qdrant vector store health (via its built-in `/metrics` endpoint), container CPU/memory/disk usage (via cAdvisor), and container restart counts. The Prometheus scrape configuration in `config/prometheus.yml` defines separate jobs for each of these targets, ensuring that every component of the stack is monitored uniformly.

### Layer 3 — Business KPIs (Benchmarks + Feedback)

The business layer tracks outcomes that matter to users and stakeholders: OCR accuracy over time (CER/WER trends), user feedback ratings (1–5 scale, broken down by category), benchmark processing counts, and model accuracy gauges pushed directly into Prometheus. The `BenchmarkTracker` in `app/core/monitoring/benchmarks.py` records every OCR run with latency, confidence, and error rates, then aggregates them into statistical summaries. The `FeedbackCollector` in `app/core/monitoring/feedback.py` captures user ratings and persists them to JSONL for trend analysis.

### How the Stack Fits Together

```
┌──────────────┐     scrape /metrics      ┌─────────────┐
│  FastAPI App │ ◄─────────────────────── │  Prometheus  │
│  + /metrics  │     every 10s             │  (port 9090)│
└──────┬───────┘                          └──────┬──────┘
       │                                         │
       │  JSON logs to stdout                     │  evaluates rules
       ▼                                         ▼
┌──────────────┐                          ┌─────────────┐
│  Container   │                          │ Alertmanager│
│  stdout/stderr│                         │  (port 9093)│
└──────────────┘                          └──────┬──────┘
       │                                         │
       │  ERROR-level logs                       │  routes to
       ▼                                         ▼
┌──────────────┐                          ┌─────────────┐
│   Sentry     │                          │  Slack/Discord│
│  (DSN-based) │                          │  webhooks   │
└──────────────┘                          └─────────────┘
                                                   ▲
                                                   │ queries
┌──────────────┐                                  │
│   Grafana    │ ──────────────────────────────────┘
│  (port 3001) │   datasource: http://prometheus:9090
└──────────────┘
```

All components communicate over the Docker network. Prometheus scrapes application metrics at `/metrics`, evaluates alerting rules from `config/prometheus-rules.yml`, and forwards alerts to Alertmanager. Alertmanager groups and routes them based on severity (`critical` vs `default` receivers). Grafana reads from Prometheus to render dashboards. Sentry operates independently via its DSN, capturing unhandled exceptions and explicit `capture_error()` calls.

---

## 2. Structured Logging

All services in OmniMedical Suite emit **structured JSON logs** through the module at `app/core/monitoring/logging.py`. This design ensures that every log line is machine-parseable and can be ingested by any log aggregation system (ELK, Loki, CloudWatch, Datadog) without custom parsing rules.

### How It Works

The `JSONFormatter` class extends Python's standard `logging.Formatter`. Every log record is serialized to a single-line JSON object containing a UTC ISO-8601 timestamp, the log level, the logger name, the message, the source file and line number, an auto-generated request ID, and any extra fields attached to the record (such as `duration_ms`, `engine`, or `lang`). Exception stack traces are included inline when present.

The root logger is named `omni_medical`. Child loggers are created with `get_logger(name)`, which returns `logging.getLogger("omni_medical.<name>")`. This hierarchy lets you adjust log levels per-subsystem via environment variables or configuration.

### Log Format

```python
{
    "timestamp": "2025-01-15T10:23:45.678901+00:00",
    "level": "INFO",
    "logger": "omni_medical.ocr",
    "message": "Processing complete",
    "request_id": "a1b2c3d4",
    "duration_ms": 450,
    "engine": "paddleocr",
    "file": "/app/app/routers/ocr.py",
    "line": 87
}
```

### Configuration via Environment Variables

| Environment Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Minimum log level. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Set to `DEBUG` for verbose output during development. |
| `LOG_FILE` | *(none)* | Path to a rotating log file. When set, a `RotatingFileHandler` is added alongside the stdout handler. Files rotate at 10 MB with 5 backups retained. |

### Enabling File Logging

File logging is disabled by default (logs go to stdout for Docker/container environments). To enable it, set the `LOG_FILE` environment variable:

```bash
# Local development with file logging
export LOG_LEVEL=DEBUG
export LOG_FILE=/var/log/omni-medical/app.log
python app/main.py
```

The `setup_logging()` function handles the configuration automatically on module import. It creates a `JSONFormatter`, attaches a `StreamHandler` to stdout, and conditionally adds a `RotatingFileHandler` if `LOG_FILE` is set. The function is idempotent — calling it multiple times returns the same configured logger without adding duplicate handlers.

### Sample JSON Log Line

```json
{"timestamp":"2025-01-15T10:23:45.678901+00:00","level":"INFO","logger":"omni_medical.ocr","message":"OCR processing complete","request_id":"a1b2c3d4","duration_ms":2340,"engine":"paddleocr","lang":"ar","file":"/app/app/routers/ocr.py","line":87}
```

### Usage in Application Code

```python
from app.core.monitoring.logging import get_logger

logger = get_logger("ocr")

# Basic logging
logger.info("Processing started", extra={"engine": "paddleocr", "lang": "ar"})

# With duration
logger.info("Processing complete", extra={"duration_ms": 450, "engine": "paddleocr"})

# Error with stack trace (automatically included)
try:
    result = ocr_engine.process(image)
except Exception as e:
    logger.error("OCR processing failed", exc_info=True, extra={"engine": "paddleocr"})
```

---

## 3. Prometheus Metrics

All Prometheus metrics are defined in `app/core/monitoring/metrics.py` using the `prometheus_client` library. The module provides both the raw metric objects (for direct use in application code) and convenience functions for recording common operations like OCR processing and translation.

### Complete Metrics Catalog

#### HTTP Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `omni_http_requests_total` | Counter | `method`, `endpoint`, `http_status` | Total number of HTTP requests received by the API. Incremented on every request completion (including 500 errors caught by middleware). Endpoint paths are normalized — UUIDs and long path segments are replaced with `/:id`. |
| `omni_http_request_duration_seconds` | Histogram | `endpoint` | Measures the wall-clock duration of HTTP requests in seconds. Buckets: `[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]`. Use with `histogram_quantile()` to compute percentiles. |
| `omni_http_active_requests` | Gauge | *(none)* | Current number of in-flight requests. Incremented on request entry, decremented in the `finally` block. Useful for detecting request storms. |

#### OCR Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `omni_ocr_processing_seconds` | Histogram | `engine`, `language` | OCR processing time per engine/language combination. Buckets: `[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]`. Used by alerting rules to detect slow processing (P95 > 30s). |
| `omni_ocr_requests_total` | Counter | `engine`, `language`, `status` | Total OCR requests. The `status` label distinguishes `success`, `error`, and `timeout` outcomes. |
| `omni_ocr_confidence_score` | Histogram | `engine` | Distribution of OCR output confidence scores. Buckets: `[0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99]`. The LowOCRConfidence alert triggers when the median drops below 0.5. |

#### Translation Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `omni_translation_seconds` | Histogram | `source_lang`, `target_lang` | Translation processing duration per language pair. Buckets: `[0.5, 1.0, 2.0, 5.0, 10.0, 20.0]`. |
| `omni_translation_requests_total` | Counter | `source_lang`, `target_lang`, `status` | Total translation requests by language pair and outcome status. |

#### Model Accuracy Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `omni_model_accuracy` | Gauge | `model_type`, `metric_type` | Latest accuracy measurement for a model. `model_type` is the engine name (e.g., `paddleocr`, `tesseract`), and `metric_type` is the metric name (`cer`, `wer`). Updated by `BenchmarkTracker.record()`. |

#### System Readiness Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `omni_paddleocr_model_loaded` | Gauge | *(none)* | Indicates whether the PaddleOCR model has been loaded into memory. `1` = loaded, `0` = not loaded. Set during application startup. |
| `omni_tesseract_available` | Gauge | *(none)* | Indicates whether Tesseract OCR binary is available on the system. `1` = available, `0` = not found. Checked at startup via `shutil.which()`. |

### Convenience Functions

```python
from app.core.monitoring.metrics import record_ocr_processing, record_translation

# Record an OCR processing event
record_ocr_processing(
    engine="paddleocr",
    language="ar",
    duration=2.3,
    status="success"  # or "error", "timeout"
)

# Record a translation event
record_translation(
    source_lang="ar",
    target_lang="en",
    duration=1.5,
    status="success"
)
```

### Integrating with FastAPI

To enable automatic HTTP metrics collection and expose the `/metrics` endpoint, add the metrics middleware and route to your FastAPI application:

```python
from fastapi import FastAPI
from app.core.monitoring.metrics import add_metrics_middleware, metrics_route

app = FastAPI()

# Middleware automatically records request count, latency, and active request count
add_metrics_middleware(app)

# Expose Prometheus metrics at /metrics
app.add_route("/metrics", metrics_route)
```

The middleware (implemented as a `BaseHTTPMiddleware` subclass) increments `omni_http_active_requests` on entry, measures elapsed time, normalizes the endpoint path (replacing numeric IDs and UUIDs with `/:id` to prevent metric cardinality explosion), and records both the latency histogram observation and the request counter increment in a `finally` block to ensure metrics are always recorded even when exceptions occur.

### Standalone / Gradio Mode

For Gradio apps that do not use FastAPI, you can expose metrics on a separate port:

```python
from prometheus_client import start_http_server

# Start a minimal HTTP server for Prometheus scraping on port 9091
start_http_server(9091)
```

This is useful in HF Spaces or standalone Gradio deployments where you want to monitor OCR/translation metrics without modifying the Gradio server itself. Prometheus can then be configured to scrape `gradio-host:9091`.

---

## 4. Alerting

Alerting rules are defined in `config/prometheus-rules.yml` and evaluated by Prometheus every 15 seconds (configured via `evaluation_interval` in `config/prometheus.yml`). When an alert fires, Prometheus sends it to Alertmanager, which groups, deduplicates, and routes notifications to the appropriate receiver.

### Alert Rules

#### Application Alerts (group: `omni_medical_app`)

| Alert | Severity | Condition | Duration | Description |
|---|---|---|---|---|
| **HighErrorRate** | `critical` | `rate(omni_http_requests_total{http_status=~"5.."}[5m]) / rate(omni_http_requests_total[5m]) > 0.05` | 5m | Triggers when more than 5% of HTTP requests return 5xx errors over a 5-minute window. This is a critical alert because sustained error rates indicate a systemic problem — database failures, out-of-memory crashes, or configuration errors. The alert includes a runbook link in `MAINTENANCE.md`. |
| **HighLatency** | `warning` | `histogram_quantile(0.95, sum(rate(omni_http_request_duration_seconds_bucket[5m])) by (le, endpoint)) > 5.0` | 5m | Triggers when the P95 request latency for any endpoint exceeds 5 seconds. This uses `histogram_quantile` to compute the 95th percentile from bucketed histograms, which is the recommended approach for accurate percentile calculations in Prometheus. |
| **OCRProcessingSlow** | `warning` | `histogram_quantile(0.95, sum(rate(omni_ocr_processing_seconds_bucket[5m])) by (le)) > 30` | 5m | Triggers when the P95 OCR processing time across all engines exceeds 30 seconds. Medical document OCR can legitimately be slow for large scanned PDFs, but sustained P95 above 30s suggests resource contention or model loading issues. |
| **LowOCRConfidence** | `warning` | `histogram_quantile(0.5, sum(rate(omni_ocr_confidence_score_bucket[10m])) by (le, engine)) < 0.5` | 10m | Triggers when the median OCR confidence score for any engine drops below 50% over a 10-minute window. Low confidence may indicate degraded image quality, model drift, or a batch of unusual documents. The alert identifies the specific engine via the `engine` label. |

#### Infrastructure Alerts (group: `omni_medical_infra`)

| Alert | Severity | Condition | Duration | Description |
|---|---|---|---|---|
| **HighMemoryUsage** | `warning` | `process_resident_memory_bytes / (1024^3) > 4` | 10m | Triggers when the application process uses more than 4 GB of RSS memory. PaddleOCR and large language models are memory-intensive, so this threshold accounts for normal operation while catching memory leaks. |
| **HFSpaceBuildFailing** | `critical` | `up{job="hf-space"} == 0` | 15m | Triggers when the HuggingFace Space health check fails for 15 consecutive minutes. This catches Space build failures or runtime crashes that leave the Space unresponsive. |
| **ContainerRestartLoop** | `critical` | `rate(container_restarts_total[15m]) > 0.1` | 5m | Triggers when any container is restarting more than once per 10 minutes (0.1 restarts/minute). A restart loop indicates a crash-loop-back-off pattern, usually caused by missing configuration, failed dependency connections, or out-of-memory kills. |

### Alertmanager Routing

The Alertmanager configuration in `config/alertmanager.yml` defines two severity-based receivers:

```yaml
route:
  group_by: ["alertname", "severity"]
  group_wait: 30s        # Wait 30s before sending first notification
  group_interval: 5m     # Wait 5m between notifications for the same group
  repeat_interval: 4h    # Re-send notification every 4h if still firing
  receiver: "default"

routes:
  - match:
      severity: critical
    receiver: "critical"
    group_wait: 10s      # Critical alerts: notify immediately (10s)
    group_interval: 1m   # Follow-up every 1m
    repeat_interval: 1h   # Re-remind every 1h
```

**Routing logic:**

- **`default` receiver** — Handles `warning`-severity alerts. Uses a 30-second `group_wait` to allow multiple related warnings to be batched together before sending. Notifications repeat every 4 hours.
- **`critical` receiver** — Handles `critical`-severity alerts (HighErrorRate, HFSpaceBuildFailing, ContainerRestartLoop). Uses a much shorter 10-second `group_wait` to ensure near-immediate notification. Follow-up alerts are sent every 1 minute, and repeat reminders fire every hour.

Both receivers are configured as placeholders (commented-out webhook configs). To activate notifications, uncomment the `webhook_configs` sections and add your Slack, Discord, PagerDuty, or email webhook URLs. For example:

```yaml
receivers:
  - name: "default"
    webhook_configs:
      - url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
        send_resolved: true

  - name: "critical"
    webhook_configs:
      - url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
        channel: "#omni-medical-critical"
        send_resolved: true
```

The `send_resolved: true` flag ensures that a notification is also sent when the alert clears, providing closure to the incident.

---

## 5. Sentry Error Tracking

Sentry provides **real-time error tracking and performance monitoring** with rich exception context, stack trace grouping, and release tracking. Integration is handled by `app/core/monitoring/error_tracking.py` and is completely optional — it has zero impact when not configured.

### Enabling Sentry

Sentry activates only when the `SENTRY_DSN` environment variable is set. Without it, all error-tracking functions are no-ops, making it safe to include in development environments and HF Spaces deployments.

```bash
# Production
export SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0"

# With optional tracing (20% of transactions sampled)
export SENTRY_TRACES_SAMPLE_RATE=0.2
```

### How It Works

The `init_sentry()` function performs the following steps:

1. **Reads the DSN** from the function argument or falls back to the `SENTRY_DSN` environment variable. If neither is present, it returns `False` immediately (no-op).
2. **Configures the LoggingIntegration** to only capture `ERROR`-level and above log records as Sentry events. This prevents Sentry from being flooded with INFO/WARNING logs while ensuring all application errors are captured automatically.
3. **Initializes the Sentry SDK** with the following settings:
   - `environment`: Set to `"production"` by default (configurable).
   - `traces_sample_rate`: Defaults to `0.2` (20% of transactions are traced for performance monitoring).
   - `send_default_pii`: Disabled by default (`False`) to protect patient data. **Never enable PII sending in medical applications** unless you have explicit consent and a data processing agreement.
   - `max_breadcrumbs`: 50 (number of events to keep for crash context).
   - `attach_stacktrace`: `True` (attaches stack traces to all events, even messages).

### Initialization in Application Code

```python
from app.core.monitoring.error_tracking import init_sentry

# Call early in the application lifecycle (e.g., in app/main.py or app.py)
sentry_initialized = init_sentry(
    dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
    environment="production",
    traces_sample_rate=0.2,
)

if sentry_initialized:
    print("Sentry error tracking active")
```

### Capturing Errors with Context

The `capture_error()` function sends an exception to Sentry with optional context tags. If Sentry is not initialized, it silently does nothing — it will never crash your application.

```python
from app.core.monitoring.error_tracking import capture_error

try:
    result = ocr_engine.process(image)
except Exception as e:
    capture_error(e, context={
        "engine": "paddleocr",
        "language": "ar",
        "image_size": image.size,
        "user_id": current_user.id,
    })
```

Context keys become tags in Sentry, allowing you to filter and group errors by engine, language, image dimensions, or any other dimension relevant to debugging. The function uses `sentry_sdk.push_scope()` to ensure that context tags are isolated and do not leak between requests.

### Best Practices for Medical OCR

- **Never set `send_default_pii=True`** in production. Medical documents may contain patient names, IDs, or other protected health information (PHI).
- **Use a low `traces_sample_rate`** (0.1–0.2) in production to control Sentry quota usage while still capturing representative performance data.
- **Set `environment`** to match your deployment tier (`development`, `staging`, `production`) so errors are properly segmented in the Sentry dashboard.
- **Tag errors with `engine` and `language`** to quickly identify patterns like "all Arabic PaddleOCR failures" or "Tesseract timeout on English documents."

---

## 6. Grafana Dashboards

Grafana serves as the visualization layer for all Prometheus metrics. It connects to Prometheus as its primary data source and renders real-time dashboards for operations teams.

### Data Source Configuration

The file `config/grafana-datasources.yml` provisions three data sources automatically when Grafana starts:

| Data Source | Type | URL | Purpose |
|---|---|---|---|
| **Prometheus** | `prometheus` | `http://prometheus:9090` | Primary metrics source. Set as the default datasource. Marked as non-editable to prevent accidental changes through the UI. |
| **Tempo** | `tempo` | `http://tempo:3200` | Distributed tracing backend (for Sentry-integrated trace visualization). Optional — only used if Tempo is deployed. |
| **PostgreSQL** | `postgres` | `postgres:5432` | Direct database queries from dashboards (e.g., document counts, user activity). Requires `GRAFANA_DB_PASSWORD` environment variable. |

### Recommended Dashboard Panels

When building Grafana dashboards for OmniMedical Suite, the following panels should be included:

#### Panel 1: Request Rate
- **Query:** `sum(rate(omni_http_requests_total[5m])) by (endpoint)`
- **Visualization:** Time series graph
- **Purpose:** Shows the throughput of each API endpoint over time. Sudden drops may indicate service degradation, while spikes may indicate load surges that require scaling.

#### Panel 2: Error Rate (5xx)
- **Query:** `sum(rate(omni_http_requests_total{http_status=~"5.."}[5m])) / sum(rate(omni_http_requests_total[5m])) * 100`
- **Visualization:** Stat panel with threshold coloring (green < 1%, yellow 1–5%, red > 5%)
- **Purpose:** Provides a single-glance view of error rates. This mirrors the HighErrorRate alert rule and serves as the visual counterpart.

#### Panel 3: P95 Latency
- **Query:** `histogram_quantile(0.95, sum(rate(omni_http_request_duration_seconds_bucket[5m])) by (le, endpoint))`
- **Visualization:** Time series graph with a 5-second horizontal line as warning threshold
- **Purpose:** Tracks the 95th percentile request latency per endpoint. Useful for identifying slow endpoints and correlating latency spikes with deployment events or load changes.

#### Panel 4: OCR Processing Time (P95)
- **Query:** `histogram_quantile(0.95, sum(rate(omni_ocr_processing_seconds_bucket[5m])) by (le, engine))`
- **Visualization:** Time series graph, one series per engine
- **Purpose:** Compares OCR processing speed across engines (PaddleOCR, Tesseract, EasyOCR, Surya). This panel directly corresponds to the OCRProcessingSlow alert.

#### Panel 5: OCR Confidence Distribution
- **Query:** `histogram_quantile(0.5, sum(rate(omni_ocr_confidence_score_bucket[10m])) by (le, engine))`
- **Visualization:** Gauge or stat panel per engine
- **Purpose:** Shows the median confidence score per OCR engine. A declining trend may indicate model degradation or a shift in input document types.

#### Panel 6: Model Accuracy Over Time
- **Query:** `omni_model_accuracy` (Gauge, shows latest value)
- **Visualization:** Stat panel with CER and WER for each engine
- **Purpose:** Displays the latest Character Error Rate (CER) and Word Error Rate (WER) for each model. Updated automatically by `BenchmarkTracker.record()`.

#### Panel 7: Resource Usage
- **Queries:**
  - Memory: `process_resident_memory_bytes / (1024*1024*1024)`
  - CPU: `rate(process_cpu_seconds_total[5m])`
- **Visualization:** Dual-axis time series
- **Purpose:** Monitors application resource consumption. The HighMemoryUsage alert fires at 4 GB RSS, so this panel provides the leading-edge visualization.

### Accessing Grafana

- **Standard deployment:** `http://localhost:3001` (mapped from Grafana's internal port 3000)
- **Default credentials:** `admin` / `admin` (change `GRAFANA_PASSWORD` in production)
- Import dashboards via JSON or use Grafana's provisioning feature by adding `.json` files to a `dashboards/` directory

---

## 7. Benchmark Tracking

The `BenchmarkTracker` class in `app/core/monitoring/benchmarks.py` provides a comprehensive system for recording, aggregating, and persisting OCR processing benchmarks. It bridges the gap between one-off accuracy evaluations and continuous production monitoring by automatically pushing benchmark data into Prometheus.

### BenchmarkTracker Class

```python
from app.core.monitoring.benchmarks import BenchmarkTracker

# Initialize with optional JSONL persistence
tracker = BenchmarkTracker(storage_path="data/benchmarks.jsonl")

# If storage_path is None, benchmarks are kept in memory only
tracker_memory_only = BenchmarkTracker()
```

When `storage_path` is provided, the tracker loads any existing benchmarks from the JSONL file on initialization, enabling historical analysis across restarts. The file is append-only (one JSON object per line), making it safe for concurrent reads and easy to process with standard Unix tools (`wc -l`, `jq`, `grep`).

### The `record()` Method

Every call to `record()` performs three actions simultaneously:

1. **In-memory storage** — Appends an `OCRBenchmark` dataclass to the internal list.
2. **Prometheus push** — Observes the duration on the `omni_ocr_processing_seconds` histogram and sets the `omni_model_accuracy` gauge for CER and/or WER if provided.
3. **Disk persistence** — Appends the benchmark as a single JSON line to the JSONL file.

```python
tracker.record(
    engine="paddleocr",
    language="ar",
    duration=2.3,       # seconds
    cer=0.042,          # Character Error Rate (optional)
    wer=0.089,          # Word Error Rate (optional)
    confidence=0.87,    # Average confidence score (optional)
    image_id="abc123",  # Optional image identifier for traceability
)
```

### The `get_stats()` Aggregation Method

The `get_stats()` method computes aggregated statistics for a specific engine or all engines combined. It returns a dictionary with count, duration statistics (average, min, max, P95), CER statistics, WER statistics, and average confidence:

```python
# Stats for a specific engine
stats = tracker.get_stats(engine="paddleocr")
# {
#     "count": 1523,
#     "duration": {"avg": 2.1, "min": 0.4, "max": 28.7, "p95": 8.3},
#     "cer": {"avg": 0.038, "min": 0.001, "max": 0.34},
#     "wer": {"avg": 0.081, "min": 0.005, "max": 0.52},
#     "confidence": {"avg": 0.89}
# }

# Stats across all engines
all_stats = tracker.get_stats()
```

The P95 duration is computed by sorting the durations and taking the value at the 95th percentile index. If there are fewer than 20 data points, it falls back to the maximum value to avoid misleading statistics from small samples.

### JSONL Persistence Format

Each line in the JSONL file is a self-contained JSON object representing a single benchmark:

```json
{"engine":"paddleocr","language":"ar","duration":2.3,"cer":0.042,"wer":0.089,"confidence":0.87,"timestamp":"2025-01-15T10:23:45.678901+00:00","image_id":"abc123"}
```

### Automatic Prometheus Integration

Every `record()` call automatically pushes data to Prometheus without any additional configuration:

- **`omni_ocr_processing_seconds`** histogram is observed with the `engine` and `language` labels.
- **`omni_model_accuracy`** gauge is set with the `model_type` (engine name) and `metric_type` (`cer` or `wer`) labels.

This means that every benchmark recorded through the `BenchmarkTracker` immediately becomes visible in Grafana dashboards and is subject to Prometheus alerting rules (e.g., LowOCRConfidence). There is no separate export step or batch process required.

### Retrieving Recent Benchmarks

For display in UI components or API responses, the `get_recent()` method returns the last N benchmarks as a list of dictionaries:

```python
recent = tracker.get_recent(n=20)
# [{"engine": "paddleocr", "language": "ar", "duration": 2.3, ...}, ...]
```

---

## 8. Docker Compose Monitoring

The OmniMedical Suite provides multiple Docker Compose configurations for different deployment tiers. Monitoring infrastructure (Prometheus, Grafana, Alertmanager) is included in the standard and production tiers.

### Starting the Full Stack with Monitoring

```bash
# Start application services + infrastructure (postgres, redis, qdrant)
docker-compose --profile infra up -d
```

This command starts:

| Service | Port | Description |
|---|---|---|
| `gradio` | 7860 | Gradio HITL application with health check |
| `api` | 8000 | FastAPI backend with `/metrics` endpoint |
| `postgres` | 5432 | PostgreSQL 16 database (profile: `infra`) |
| `redis` | 6379 | Redis 7 cache with AOF persistence (profile: `infra`) |
| `qdrant` | 6333 | Qdrant vector store (profile: `infra`) |

### Standard Deployment (with Prometheus + Grafana)

The `docker-compose.standard.yml` file includes Prometheus and Grafana as first-class services alongside the full application stack (web, api, worker, postgres, redis, qdrant):

```bash
DEPLOYMENT_MODE=standard docker-compose -f docker-compose.standard.yml up -d
```

| Service | Port | Description |
|---|---|---|
| `prometheus` | 9090 | Prometheus v2.50.0 with custom config mounted from `./config/prometheus/` |
| `grafana` | 3001 | Grafana 10.3.0 with persistent volume for dashboards and settings |
| `api` | 8000 | API service (scrape target for Prometheus at `/metrics`) |
| `web` | 3000 | Next.js frontend |
| `worker` | — | Celery background worker |
| `postgres` | 5432 | PostgreSQL with `postgres-exporter` on port 9187 |
| `redis` | 6379 | Redis with `redis-exporter` on port 9121 |
| `qdrant` | 6333 | Qdrant with built-in metrics at `/metrics` |

### Production Deployment

The `docker-compose.prod.yml` file provides a production-oriented configuration with web, PostgreSQL, and Redis. It does not include Prometheus/Grafana by default — in production, you would typically run the monitoring stack on separate infrastructure or use a managed observability service. You can compose multiple files:

```bash
docker-compose -f docker-compose.prod.yml -f docker-compose.standard.yml up -d prometheus grafana alertmanager
```

### Prometheus Configuration

The main Prometheus configuration at `config/prometheus.yml` defines the following scrape targets:

- **`prometheus`** (self-monitoring): `localhost:9090` every 15s
- **`omnimedical-api`**: `api:8000/metrics` every 10s (higher frequency for API metrics)
- **`redis`**: `redis-exporter:9121` every 15s
- **`postgres`**: `postgres-exporter:9187` every 15s
- **`qdrant`**: `qdrant:6333` every 15s

Alert rules are loaded from `/etc/prometheus/prometheus-rules.yml` (mapped from `config/prometheus-rules.yml`), and alerts are forwarded to the Alertmanager at `alertmanager:9093`.

### Environment Variables for Monitoring

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Application log level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FILE` | *(none)* | Optional file path for rotating log handler |
| `SENTRY_DSN` | *(none)* | Sentry DSN for error tracking (enables Sentry if set) |
| `GRAFANA_DB_PASSWORD` | *(required for PostgreSQL datasource)* | Password for Grafana's PostgreSQL datasource |
| `POSTGRES_PASSWORD` | `omni_dev_pass` | PostgreSQL password |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |

---

## 9. HF Spaces Monitoring

HuggingFace Spaces provides its own **container-level health monitoring**. When deployed to HF Spaces, the platform automatically checks container health and will restart the container if it becomes unresponsive. The `Dockerfile.gradio` includes a built-in health check that satisfies this requirement.

### Built-in Health Check

The `Dockerfile.gradio` defines a Docker `HEALTHCHECK` instruction:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=120s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860')" || exit 1
```

- **`--interval=30s`**: Health check runs every 30 seconds.
- **`--timeout=10s`**: Each check must complete within 10 seconds.
- **`--retries=3`**: The container is marked unhealthy after 3 consecutive failures.
- **`--start-period=120s`**: Failures during the first 2 minutes (model loading, initialization) do not count.

The health check attempts to connect to `http://localhost:7860` (the Gradio server). If the connection fails, the container is marked unhealthy. HuggingFace Spaces will automatically restart unhealthy containers, and the `HFSpaceBuildFailing` alert in `config/prometheus-rules.yml` will fire if the Space remains down for 15 minutes.

### HuggingFace API for Space Status

For programmatic monitoring of your HF Space's status, use the HuggingFace REST API:

```bash
# Check Space runtime status
curl -s https://huggingface.co/api/spaces/DrAbdulmalek/omni-medical-ocr | \
  python -m json.tool
```

The response includes:

```json
{
  "id": "DrAbdulmalek/omni-medical-ocr",
  "runtime": {
    "stage": "RUNNING_BUILDING",
    "hardware": {"current": "cpu-basic", "requested": "cpu-basic"},
    "errorMessage": null
  },
  "lastUpdated": "2025-01-15T10:00:00.000Z",
  "sdk": "docker"
}
```

Key fields to monitor:
- **`runtime.stage`**: Can be `RUNNING_BUILDING`, `RUNNING`, `NO_APP_FILE`, `ERROR`, or `DELETED`. A persistent `ERROR` or `NO_APP_FILE` state requires immediate attention.
- **`runtime.errorMessage`**: Non-null when the build or runtime has encountered an error. This field contains the Docker build logs or runtime crash information.
- **`runtime.hardware.current`**: The actual hardware allocated. Useful for detecting if your Space was downgraded due to quota limits.

### Monitoring Limitations on HF Spaces

HF Spaces does **not** expose Prometheus metrics endpoints to the outside world. This means that the full monitoring stack (Prometheus scraping, Grafana dashboards, Alertmanager) is not directly available for HF Spaces deployments. Instead, monitoring relies on:

1. **Docker HEALTHCHECK** — Container-level liveness probe handled by the HF platform.
2. **Structured JSON logs** — Emitted to container stdout/stderr and visible in the HF Spaces logs tab.
3. **Sentry** — If `SENTRY_DSN` is set as a Space secret, all unhandled exceptions and `capture_error()` calls are forwarded to Sentry, providing full error tracking without requiring Prometheus.
4. **HF API polling** — External scripts can poll the HF API to detect Space status changes.

To enable Sentry on HF Spaces, add `SENTRY_DSN` as a secret in the Space settings (not in the Dockerfile or public repository). The `init_sentry()` function in `app/core/monitoring/error_tracking.py` will automatically pick it up from the environment.

```python
# In your Gradio app.py
from app.core.monitoring.error_tracking import init_sentry
init_sentry()  # Automatically reads SENTRY_DSN from environment
```

### Combining HF Spaces with External Monitoring

For teams that need full Prometheus/Grafana monitoring of their HF Space, consider running a lightweight external scraper:

```bash
# Poll HF Space status every 60 seconds
watch -n 60 'curl -s https://huggingface.co/api/spaces/DrAbdulmalek/omni-medical-ocr | jq ".runtime.stage"'
```

Or integrate with a cron-based health check service (e.g., UptimeRobot, BetterUptime) that pings the public Gradio URL and alerts on downtime.