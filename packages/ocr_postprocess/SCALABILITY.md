# Scalability Guide — دليل التوسع

> How to scale medical-ocr-postprocessor from development to production.

---

# Scalability Profiles

## Profile 1: Single-Worker (Development)
- **Workers**: 1 (ThreadPoolExecutor)
- **Expected throughput**: ~50-100 pages/min (~7,500 words/sec)
- **Memory**: ~200 MB
- **Use case**: Local development, testing, small batches (<100 pages)

## Profile 2: Multi-Worker (Production)
- **Workers**: 4-8 (ThreadPoolExecutor)  
- **Expected throughput**: 200-500 pages/min per worker
- **Memory**: ~200 MB per worker
- **Use case**: Production batch processing, large archives
- **Command**: `medical-ocr-postprocess batch --workers 8 input/ output/`

## Profile 3: No-Review (High-Throughput)
- **Workers**: 8+ (ThreadPoolExecutor)
- **Mode**: --no-review flag (skip correction logging)
- **Expected throughput**: 3-5x faster than Profile 2
- **Memory**: ~150 MB per worker (no log overhead)
- **Use case**: Bulk processing where final text is all that matters
- **Command**: `medical-ocr-postprocess batch --workers 8 --no-review input/ output/`

## Profile 4: Process-Based (CPU-Bound Heavy)
- **Workers**: CPU count (ProcessPoolExecutor)
- **Mode**: --use-processes flag
- **Expected throughput**: Scales with CPU cores, ~2-3x per core
- **Memory**: ~200 MB × worker count (isolated processes)
- **Use case**: CPU-bound correction with large dictionaries
- **Command**: `medical-ocr-postprocess batch --workers 4 --use-processes input/ output/`
- **Note**: Each worker creates its own PostProcessor instance

## Queue Draining
- **Mode**: Continuous polling with worker pool
- **Use case**: Watching an input directory for new files
- **Command**: `medical-ocr-postprocess batch --drain --workers 4 input/ output/`
- Processes files as they arrive, moves processed files to `input/processed/`

---

## Deployment Modes

### Mode 1: Single-Worker (Development & Small Batches)

**Best for:** < 100 pages, daily processing, development/testing

```python
from medical_ocr_postprocessor import PostProcessor

pp = PostProcessor(confidence_threshold=0.85)
results = pp.batch_correct(words, confidences)
```

**Performance:**
| Metric | Value |
|--------|-------|
| Throughput | ~5,000-10,000 words/sec |
| Memory | ~200 MB RAM |
| Latency | ~0.1-0.2 ms per word |

**CLI:**
```bash
medical-ocr-postprocess batch --input-dir pages/ --output-dir output/
```

---

### Mode 2: Multi-Worker (Production Batch Processing)

**Best for:** 100-10,000+ pages, bulk document processing

```bash
medical-ocr-postprocess batch \
    --input-dir backlog/ \
    --output-dir processed/ \
    --workers 4 \
    --confidence 0.85
```

**Performance (4 workers):**
| Metric | Value |
|--------|-------|
| Throughput | ~20,000-40,000 words/sec |
| Memory | ~800 MB RAM (200 MB x 4) |
| Parallelism | ThreadPoolExecutor |
| Scaling | Near-linear up to CPU cores |

**Scaling Guide:**

| Pages | Workers | Est. Time | RAM |
|-------|---------|-----------|-----|
| < 100 | 1 | < 2 min | 200 MB |
| 100-500 | 2-4 | 2-10 min | 400-800 MB |
| 500-2,000 | 4-6 | 10-30 min | 800 MB-1.2 GB |
| 2,000-10,000 | 6-8 | 30 min-2 hr | 1.2-1.6 GB |
| > 10,000 | 8+ | 2+ hr | 1.6+ GB |

---

### Mode 3: No-Review (High-Throughput Pipeline)

**Best for:** Large-scale processing where manual review is not feasible

```bash
medical-ocr-postprocess batch \
    --input-dir pipeline/ \
    --output-dir output/ \
    --workers 8 \
    --no-review \
    --confidence 0.80
```

**Key differences from standard batch:**
- No `flagged/` directory created
- All corrections auto-accepted (no human review)
- Lower confidence threshold (0.80 vs 0.85) accepts more corrections
- 3-5x faster due to skipped review file I/O and per-word logging

**When to use no-review mode:**
- Pre-processing large corpora for training data
- Initial filtering before a second-pass review
- Non-PHI documents where accuracy threshold is acceptable
- Automated pipelines with downstream validation

---

### Mode 4: Process-Based (CPU-Bound Heavy)

**Best for:** CPU-intensive correction with large dictionaries, bypassing GIL

```bash
medical-ocr-postprocess batch \
    --input-dir backlog/ \
    --output-dir processed/ \
    --workers 4 \
    --use-processes \
    --confidence 0.85
```

**Key details:**
- Each worker process creates its own PostProcessor instance (pickle-safe)
- Uses `collections.deque(maxlen=10000)` to cap correction logs per process
- No shared state between workers — fully isolated
- Memory scales linearly with worker count (~200 MB per worker)

---

### Mode 5: Celery + Redis (Distributed Production)

**Best for:** Continuous processing, multiple machines, queue-based workflows

```bash
pip install medical-ocr-postprocessor[production]
```

```python
# tasks.py
from celery import Celery
from medical_ocr_postprocessor import PostProcessor

app = Celery('ocr_postprocess', broker='redis://localhost:6379/0')

@app.task
def process_document(file_path: str) -> dict:
    """Process a single document as a Celery task."""
    import json
    pp = PostProcessor(confidence_threshold=0.85)
    
    with open(file_path) as f:
        data = json.load(f)
    
    words = data.get("words", [])
    confidences = data.get("confidences", [0.5] * len(words))
    results = pp.batch_correct(words, confidences)
    
    return {
        "file": file_path,
        "total": len(words),
        "corrected": sum(1 for r in results if r.is_modified),
        "results": [r.to_dict() for r in results],
    }
```

```bash
# Start workers
celery -A tasks worker --loglevel=info --concurrency=4

# Submit work
python -c "
from tasks import process_document
process_document.delay('pages/page_001.json')
"
```

**Performance (4 Celery workers):**
| Metric | Value |
|--------|-------|
| Throughput | ~20,000-40,000 words/sec per worker |
| Memory | ~200 MB per worker process |
| Scaling | Add more machines, horizontal scaling |
| Persistence | Redis queue survives restarts |
| Monitoring | Use `--prometheus` flag + Grafana |

---

## Throughput Comparison

| Mode | Words/sec | Pages/min | Review | Setup Complexity |
|------|-----------|-----------|--------|-----------------|
| Single-Worker | ~7,500 | ~50 | Yes (inline) | Zero |
| Multi-Worker (4) | ~30,000 | ~200 | Yes (flagged/) | Low |
| No-Review (8) | ~60,000 | ~400 | No | Low |
| Process-Based (4) | ~20,000-60,000 | ~200-400 | Yes (flagged/) | Low |
| Celery (4 nodes) | ~120,000 | ~800 | Optional | Medium |

---

## Resource Requirements

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| CPU | 1 core | 4 cores | 8+ cores |
| RAM | 512 MB | 2 GB | 4+ GB |
| Disk | 100 MB | 1 GB | 10+ GB (for queue) |
| Python | 3.10+ | 3.11 | 3.11+ |
| Redis | Not needed | Not needed | 6.0+ (for Celery) |

---

## Monitoring

```bash
pip install medical-ocr-postprocessor[monitoring]
```

Prometheus metrics are exposed at `/metrics` when running as a Celery worker:
- `postprocessor_words_total` — Total words processed
- `postprocessor_corrections_total` — Total corrections applied
- `postprocessor_errors_total` — Total errors encountered
- `postprocessor_processing_duration_seconds` — Processing latency histogram

---

## Tips for High Throughput

1. **Use `--no-review`** when you don't need human review — 3-5x faster
2. **Increase `--workers`** up to your CPU core count
3. **Batch files** instead of processing one-by-one
4. **Use `--use-processes`** for CPU-bound workloads (bypasses GIL)
5. **Pre-load dictionaries** at worker startup, not per-request
6. **Set confidence threshold** to 0.80 for high-recall pipelines

---

> Part of the [Medical OCR Ecosystem](https://github.com/DrAbdulmalek/omni-medical-suite/blob/main/PORTFOLIO.md)
