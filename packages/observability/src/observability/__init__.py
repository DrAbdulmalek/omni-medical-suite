"""
observability
=============

Structured logging + LLM-powered log review for the OmniMedical suite.

Public API
----------
- ``get_logger(name)`` → configured ``logging.Logger``
- ``log_event(event, category, **fields)`` → structured one-line JSON event
- ``LogCategory`` → enum of standardized categories
- ``Severity`` → enum of standardized severities
- ``configure_logging(level=..., log_dir=...)`` → global setup

Log file layout
---------------
- ``<log_dir>/omni.log``           — human-readable, all severities
- ``<log_dir>/omni.jsonl``         — JSON lines, one event per line (for LLM)
- ``<log_dir>/errors.jsonl``       — JSON lines, errors and criticals only
- ``<log_dir>/timeline.jsonl``     — JSON lines, performance + lifecycle events

Categories (high-level)
-----------------------
- LIFECYCLE   — app start/stop, module load/unload
- OCR         — OCR engine invocations + results
- PREPROCESS  — scanner_fixer pipeline stages (crop, deskew, enhance, ...)
- DB          — database reads/writes
- API         — HTTP/web requests
- ML          — model load/inference
- USER        — user-initiated actions (save, edit, batch)
- PERFORMANCE — timing, memory, throughput
- ERROR       — exceptions + error conditions
- SECURITY    — auth, token usage, suspicious activity
"""

from .logger import (
    get_logger,
    log_event,
    configure_logging,
    reset_session_id,
    LogCategory,
    Severity,
    OBSERVABILITY_VERSION,
)

__all__ = [
    "get_logger",
    "log_event",
    "configure_logging",
    "reset_session_id",
    "LogCategory",
    "Severity",
    "OBSERVABILITY_VERSION",
]

__version__ = OBSERVABILITY_VERSION
