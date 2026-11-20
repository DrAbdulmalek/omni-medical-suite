# OmniMedical Observability

Structured logging + LLM-powered log review for the OmniMedical suite.

## Quick start

```python
from observability import (
    configure_logging, log_event, LogCategory, Severity, get_logger
)

# Call once at app start
configure_logging()  # → ~/.omni/logs/{omni.log, omni.jsonl, errors.jsonl}

# Emit structured events
log_event("user.uploaded_image",
          category=LogCategory.USER,
          level=Severity.INFO,
          file_path="report.png", file_size_kb=850)

# In a function you want to profile:
import time
t0 = time.perf_counter()
# ... do work ...
log_event("ocr.success",
          category=LogCategory.OCR,
          level=Severity.INFO,
          duration_ms=round((time.perf_counter() - t0) * 1000, 2),
          engine="paddleocr",
          chars_extracted=1240,
          status="ok")
```

## Log file layout

| File | Format | Purpose |
|------|--------|---------|
| `~/.omni/logs/omni.log` | human-readable | all severities, rotated 10MB × 5 |
| `~/.omni/logs/omni.jsonl` | JSON lines | all severities, for analyzer |
| `~/.omni/logs/errors.jsonl` | JSON lines | WARNING+ only, for fast error review |
| `~/.omni/logs/omni.log.1`, `.2`, … | rotated backups | when current file hits 10MB |

Each JSON line contains:

```json
{
  "ts": "2026-07-18T23:13:08.123456+00:00",
  "level": "info",
  "logger": "observability.scanner_fixer",
  "message": "fix_scan.success",
  "session_id": "a3f4b2c1d4e5",
  "host": "manjaro",
  "pid": 12345,
  "platform": "Linux-6.6-x86_64",
  "file": "packages/scanner_fixer/src/scanner_fixer/pipeline.py:42",
  "func": "fix_scan",
  "category": "preprocess",
  "event": "fix_scan.success",
  "duration_ms": 223.6,
  "input_shape": [400, 600, 3],
  "output_shape": [380, 580, 3],
  "status": "ok"
}
```

## Categories

- `LIFECYCLE` — app start/stop, module load/unload
- `OCR` — OCR engine invocations + results
- `PREPROCESS` — scanner_fixer pipeline stages (crop, deskew, enhance, …)
- `DB` — database reads/writes
- `API` — HTTP/web requests
- `ML` — model load/inference
- `USER` — user-initiated actions (save, edit, batch)
- `PERFORMANCE` — timing, memory, throughput
- `ERROR` — exceptions + error conditions
- `SECURITY` — auth, token usage, suspicious activity

## Auto-instrument scanner_fixer

```python
from observability.integration import instrument_scanner_fixer

instrument_scanner_fixer()  # call once at app start
```

After this, every call to `fix_scan`, `fix_scan_batch`, `auto_crop`, `deskew`,
`auto_rotate`, `enhance_for_ocr`, and `DocumentPreprocessor.process()` will
emit `start` / `success` / `error` events with timing and shape info —
automatically, without changing those modules.

## LLM log analyzer

```bash
# Stats only (no LLM call, works offline)
python scripts/llm_log_analyzer.py

# Stats + LLM review (uses z-ai SDK CLI)
python scripts/llm_log_analyzer.py --llm

# Filter to last 24h
python scripts/llm_log_analyzer.py --since 24h --llm

# Custom log dir + output dir
python scripts/llm_log_analyzer.py \
    --log-dir ~/.omni/logs \
    --out-dir ./reports \
    --csv \
    --llm
```

Produces:

| File | Contents |
|------|----------|
| `stats.json` | Raw aggregated statistics |
| `summary.md` | Human-readable Markdown report (rule-based priorities) |
| `llm_review.md` | LLM-generated priorities (only if `--llm`) |
| `timeline.csv` | Per-event timeline (only if `--csv`) |

### Example LLM output (real)

After running 6 `fix_scan` calls + 1 deliberate error:

```
## 1. Fix Image File Handling Errors
**Why it matters**: 2/23 events (8.7%) are errors due to ValueError when
trying to read nonexistent images (`/nonexistent.png`).
**Suggested first step**: Examine `scanner_fixer` module for image file
validation before processing, specifically checking for file existence
and proper paths.

## 2. Optimize fix_scan Performance
**Why it matters**: `fix_scan.success` events show high variability
(43.82ms stdev) compared to `auto_crop` (0.34ms stdev), suggesting
inconsistent performance.
**Suggested first step**: Profile the `fix_scan` function to identify
bottlenecks, likely in `/packages/scanner_fixer/src/scanner_fixer/fix_scan.py`.

[...]
```

## Integration with existing app

Add to `app/main.py` or wherever the app starts:

```python
from observability import configure_logging
from observability.integration import instrument_scanner_fixer

configure_logging()  # uses ~/.omni/logs by default
instrument_scanner_fixer()
```

Then run the app normally. After a session, run the analyzer to see what
happened:

```bash
python scripts/llm_log_analyzer.py --since 1h --llm
```

## Tests

```bash
cd packages/observability
python3 -m pytest tests/ -v
# → 7 passed
```
