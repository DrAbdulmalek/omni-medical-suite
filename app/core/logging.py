"""
Structured logging configuration for omni-medical-suite.

Provides JSON-formatted structured logging with request ID tracking,
console/file handlers, and audit/error log separation.
"""
import logging
import sys
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict
from pathlib import Path

# Request ID context for request tracing across async boundaries
import contextvars
_request_id_ctx = contextvars.ContextVar('request_id', default='unknown')


def get_request_id() -> str:
    """Get the current request ID from context."""
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in the current context."""
    _request_id_ctx.set(request_id)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured log output.

    Each log line is a JSON object containing timestamp, level, logger name,
    request_id, message, and optional exception info.
    """

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['request_id'] = get_request_id()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)


class JsonFormatter(StructuredFormatter):
    """Fallback JSON formatter that works without pythonjsonlogger.

    Outputs one JSON object per log line with consistent fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'request_id': get_request_id(),
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure structured logging for the application.

    Sets up three handlers:
    - Console (stdout) — all logs at the configured level
    - File: logs/audit.log — INFO and above
    - File: logs/errors.log — ERROR only

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files. Created automatically if missing.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Ensure log directory exists
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Try to use pythonjsonlogger if available, fall back to our own
    try:
        from pythonjsonlogger import jsonlogger

        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(logger)s %(message)s'
        )
    except ImportError:
        formatter = JsonFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates on re-init
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler for audit logs
    audit_handler = logging.FileHandler(os.path.join(log_dir, 'audit.log'))
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(formatter)
    root_logger.addHandler(audit_handler)

    # Error handler
    error_handler = logging.FileHandler(os.path.join(log_dir, 'errors.log'))
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A logger configured with the root handler stack.
    """
    return logging.getLogger(name)