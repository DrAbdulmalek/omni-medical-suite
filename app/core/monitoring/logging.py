"""
OmniMedical Suite — Structured JSON Logging.

Provides a unified JSON logging format for all services (API, Gradio, workers).
Outputs structured logs to stdout (for containerized environments) and optionally
to a rotating file handler for local development.

Usage:
    from app.core.monitoring.logging import get_logger
    logger = get_logger("ocr")
    logger.info("Processing complete", extra={"duration_ms": 450, "engine": "paddleocr"})
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach request_id if present (set by middleware or context var)
        request_id = getattr(record, "request_id", None)
        if request_id is None:
            request_id = getattr(record, "request_id", str(uuid.uuid4())[:8])
        log_data["request_id"] = request_id

        # Attach any extra fields
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "engine"):
            log_data["engine"] = record.engine
        if hasattr(record, "lang"):
            log_data["lang"] = record.lang

        # Exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        # File/line for debugging
        log_data["file"] = record.pathname
        log_data["line"] = record.lineno

        return json.dumps(log_data, default=str, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configure the root 'omni_medical' logger with JSON formatting.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional file path for rotating file handler.
        max_bytes: Max file size before rotation (default 10 MB).
        backup_count: Number of backup files to keep.

    Returns:
        Configured logger instance.
    """
    root_logger = logging.getLogger("omni_medical")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent duplicate handlers on repeated calls
    if root_logger.handlers:
        return root_logger

    formatter = JSONFormatter()

    # Console handler (stdout for Docker/cloud)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # Optional rotating file handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the omni_medical namespace."""
    return logging.getLogger(f"omni_medical.{name}")


# Auto-initialize on import
default_logger = setup_logging()