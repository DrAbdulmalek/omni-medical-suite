"""
observability.logger
====================

Structured logger that emits both human-readable and JSON-lines logs.

Design:
- A single ``configure_logging()`` call sets up 4 handlers:
    1. console (stderr)              — human readable
    2. omni.log                       — human readable, all severities
    3. omni.jsonl                     — JSON lines, all severities
    4. errors.jsonl                   — JSON lines, WARNING+
- ``log_event()`` is the primary entry point. It builds a structured
  dict, emits a JSON line to the .jsonl handlers, and a readable line
  to the .log handler.
- Thread-safe, idempotent (safe to call configure_logging multiple times).
- Log rotation: 10 MB per file, 5 backups.
"""

from __future__ import annotations

import enum
import json
import logging
import os
import platform
import socket
import sys
import threading
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

OBSERVABILITY_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_LOG_DIR = Path.home() / ".omni" / "logs"
_DEFAULT_LEVEL = logging.INFO

# Thread-local session ID — one ID per "session" (process invocation, or
# explicit reset via ``reset_session_id()``).
_session_local = threading.local()


def _get_or_create_session_id() -> str:
    sid = getattr(_session_local, "session_id", None)
    if sid is None:
        sid = uuid.uuid4().hex[:12]
        _session_local.session_id = sid
    return sid


def reset_session_id() -> str:
    """Force a new session ID. Returns the new ID."""
    _session_local.session_id = uuid.uuid4().hex[:12]
    return _session_local.session_id  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LogCategory(str, enum.Enum):
    LIFECYCLE = "lifecycle"
    OCR = "ocr"
    PREPROCESS = "preprocess"
    DB = "db"
    API = "api"
    ML = "ml"
    USER = "user"
    PERFORMANCE = "performance"
    ERROR = "error"
    SECURITY = "security"
    OTHER = "other"


class Severity(int, enum.Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class _JsonLineFormatter(logging.Formatter):
    """Format a LogRecord as a single JSON line."""

    def __init__(self, *, include_extras: bool = True) -> None:
        super().__init__()
        self._include_extras = include_extras
        self._hostname = socket.gethostname()
        self._pid = os.getpid()
        self._platform = platform.platform()

    def format(self, record: logging.LogRecord) -> str:
        # Standard fields
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": _get_or_create_session_id(),
            "host": self._hostname,
            "pid": self._pid,
            "platform": self._platform,
            "file": f"{record.pathname}:{record.lineno}",
            "func": record.funcName,
        }

        # Structured extras (passed via log_event)
        for key in ("category", "event", "duration_ms", "engine",
                    "input_shape", "output_shape", "status",
                    "user_action", "error_type"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val

        # Arbitrary extras (passed as `extra={...}` from log_event)
        if self._include_extras and hasattr(record, "_omni_extras"):
            payload.update(record._omni_extras)  # type: ignore[attr-defined]

        # Exceptions
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class _ReadableFormatter(logging.Formatter):
    """Human-readable single-line format."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"[:-3]
        )
        cat = getattr(record, "category", "")
        cat_str = f" [{cat}]" if cat else ""
        msg = record.getMessage()
        extras = getattr(record, "_omni_extras", {})
        extras_str = ""
        if extras:
            extras_str = " " + " ".join(
                f"{k}={v!r}" for k, v in extras.items()
                if k not in ("category", "event")
            )
        return f"{ts} | {record.levelname:<8} | {record.name}{cat_str} | {msg}{extras_str}"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

_configured = False
_config_lock = threading.Lock()


def configure_logging(
    level: int = _DEFAULT_LEVEL,
    log_dir: str | Path | None = None,
    *,
    console: bool = True,
    reset: bool = False,
) -> Path:
    """
    Configure root + observability loggers.

    Idempotent: subsequent calls are no-ops unless ``reset=True``.

    Returns the log directory path.
    """
    global _configured

    log_dir_path = Path(log_dir).expanduser() if log_dir else _DEFAULT_LOG_DIR
    log_dir_path.mkdir(parents=True, exist_ok=True)

    with _config_lock:
        if _configured and not reset:
            return log_dir_path

        root = logging.getLogger()
        # Avoid duplicate handlers on reset
        if reset:
            for h in list(root.handlers):
                root.removeHandler(h)
            obs = logging.getLogger("observability")
            for h in list(obs.handlers):
                obs.removeHandler(h)

        root.setLevel(level)

        # 1. Console (stderr) — human readable
        if console:
            ch = logging.StreamHandler(stream=sys.stderr)
            ch.setLevel(level)
            ch.setFormatter(_ReadableFormatter())
            root.addHandler(ch)

        # 2. omni.log — human readable, rotating
        full_log = log_dir_path / "omni.log"
        fh_full = RotatingFileHandler(
            full_log, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh_full.setLevel(level)
        fh_full.setFormatter(_ReadableFormatter())
        root.addHandler(fh_full)

        # 3. omni.jsonl — JSON lines, all severities
        jsonl_log = log_dir_path / "omni.jsonl"
        fh_jsonl = RotatingFileHandler(
            jsonl_log, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh_jsonl.setLevel(level)
        fh_jsonl.setFormatter(_JsonLineFormatter(include_extras=True))
        # Attach to a dedicated logger so we can keep JSON separate if needed
        obs_logger = logging.getLogger("observability")
        obs_logger.setLevel(level)
        obs_logger.propagate = True  # also flows to root handlers
        obs_logger.addHandler(fh_jsonl)

        # 4. errors.jsonl — JSON lines, WARNING+ only
        err_log = log_dir_path / "errors.jsonl"
        fh_err = RotatingFileHandler(
            err_log, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh_err.setLevel(logging.WARNING)
        fh_err.setFormatter(_JsonLineFormatter(include_extras=True))
        obs_logger.addHandler(fh_err)

        _configured = True
        return log_dir_path


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the observability namespace."""
    if not _configured:
        configure_logging()
    if name.startswith("observability"):
        return logging.getLogger(name)
    return logging.getLogger(f"observability.{name}")


# ---------------------------------------------------------------------------
# log_event — primary structured entry point
# ---------------------------------------------------------------------------


def log_event(
    event: str,
    *,
    category: LogCategory | str = LogCategory.OTHER,
    level: Severity | int = Severity.INFO,
    logger: str | logging.Logger = "observability.app",
    **fields: Any,
) -> None:
    """
    Emit a structured event.

    Parameters
    ----------
    event : short stable identifier (e.g. "deskew.start", "ocr.success")
    category : high-level category from LogCategory
    level : logging level
    logger : name or Logger instance
    **fields : arbitrary structured fields (duration_ms, engine, file, ...)
    """
    if not _configured:
        configure_logging()

    if isinstance(category, LogCategory):
        cat_value = category.value
    else:
        cat_value = str(category)

    if isinstance(level, Severity):
        level_int = int(level)
    else:
        level_int = int(level)

    log_obj = logger if isinstance(logger, logging.Logger) else get_logger(logger)

    # Build a synthetic record via extra= so the formatters can pick fields up
    extras = dict(fields)
    extras["category"] = cat_value
    extras["event"] = event

    # Pull a few well-known fields up to the record level so the JsonLineFormatter
    # surfaces them at the top of the payload (rather than nested in extras).
    record_kwargs: dict[str, Any] = {"_omni_extras": extras}
    for key in ("duration_ms", "engine", "input_shape", "output_shape",
                "status", "user_action", "error_type"):
        if key in fields:
            record_kwargs[key] = fields[key]

    log_obj.log(level_int, event, extra=record_kwargs, exc_info=fields.get("exc_info"))
