"""
Professional Logging Setup for Omni Medical OCR Pipeline
=========================================================

Features:
* Colored console output (ANSI, auto-disabled on non-TTY / Windows)
* Rotating file handler with UTF-8 encoding (Arabic-safe)
* Performance-timing decorator ``@timed``
* Lazy one-liner factory: ``get_logger(__name__)``
"""

from __future__ import annotations

import functools
import logging
import os
import sys
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, TypeVar

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

class _ColourCode:
    """ANSI escape sequences for coloured log output."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    # Foreground
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GREY    = "\033[90m"


# Detect whether the current stream supports ANSI colours.
def _supports_colour(stream: Any) -> bool:
    """Return True if *stream* likely supports ANSI colour codes."""
    if hasattr(stream, "isatty") and stream.isatty():
        # Windows 10+ supports ANSI via vt100
        if sys.platform == "win32":
            return os.environ.get("WT_SESSION") is not None or "ANSICON" in os.environ
        return True
    # CI/CD often force colour via env var
    return os.environ.get("FORCE_COLOR", "0") == "1"


# ---------------------------------------------------------------------------
# ColourFormatter
# ---------------------------------------------------------------------------

class ColourFormatter(logging.Formatter):
    """Log formatter that injects ANSI colours per log level."""

    # level -> (colour_code, level_name_width)
    _LEVEL_STYLES: dict[int, tuple[str, str]] = {
        logging.DEBUG:    (_ColourCode.CYAN,    "DEBUG"),
        logging.INFO:     (_ColourCode.GREEN,   "INFO "),
        logging.WARNING:  (_ColourCode.YELLOW,  "WARN "),
        logging.ERROR:    (_ColourCode.RED,     "ERROR"),
        logging.CRITICAL: (_ColourCode.RED + _ColourCode.BOLD, "FATAL"),
    }

    def __init__(self, fmt: str | None = None, datefmt: str | None = None,
                 use_colour: bool = True) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self._use_colour = use_colour

    def format(self, record: logging.LogRecord) -> str:
        if self._use_colour:
            style = self._LEVEL_STYLES.get(record.levelno, (_ColourCode.WHITE, "?????"))
            colour, label = style
            # Store original so we can restore
            record.levelname = f"{colour}{label}{_ColourCode.RESET}"
            # Add subtle colour to the logger name
            record.name = f"{_ColourCode.GREY}{record.name}{_ColourCode.RESET}"
        return super().format(record)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Package-level default log directory
_DEFAULT_LOG_DIR = Path.home() / ".omni-medical-ocr" / "logs"

_logger_cache: dict[str, logging.Logger] = {}


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_dir: str | Path | None = None,
    console: bool = True,
    file: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Return a named, configured :class:`logging.Logger`.

    Parameters
    ----------
    name:
        Logger name (typically ``__name__`` of the calling module).
    level:
        Minimum log level (default ``logging.INFO``).
    log_dir:
        Directory for rotating log files.  Defaults to
        ``~/.omni-medical-ocr/logs``.
    console:
        Attach a coloured :class:`StreamHandler` to *stderr*.
    file:
        Attach a :class:`RotatingFileHandler` (UTF-8 encoded).
    max_bytes:
        Max size per log file before rotation.
    backup_count:
        Number of rotated backups to keep.

    Returns
    -------
    logging.Logger
    """
    if name in _logger_cache:
        return _logger_cache[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # prevent double-printing via root

    # ---- Console handler ----
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        use_colour = _supports_colour(sys.stderr)
        fmt = "%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s"
        console_handler.setFormatter(ColourFormatter(fmt=fmt, datefmt="%H:%M:%S",
                                                     use_colour=use_colour))
        logger.addHandler(console_handler)

    # ---- File handler ----
    if file:
        log_path: Path = Path(log_dir) if log_dir else _DEFAULT_LOG_DIR
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / "pipeline.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",       # Arabic-safe
            errors="replace",
        )
        file_handler.setLevel(level)
        file_fmt = "%(asctime)s │ %(name)s │ %(levelname)-5s │ %(funcName)s:%(lineno)d │ %(message)s"
        file_handler.setFormatter(logging.Formatter(file_fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(file_handler)

    _logger_cache[name] = logger
    return logger


# ---------------------------------------------------------------------------
# Performance-timing decorator
# ---------------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])


def timed(logger: logging.Logger | None = None, level: int = logging.INFO) -> Callable[[F], F]:
    """
    Decorator that logs the wall-clock execution time of the wrapped function.

    Usage::

        @timed()
        def preprocess(img):
            ...

        @timed(logger=my_logger, level=logging.DEBUG)
        def heavy_computation():
            ...
    """
    def decorator(func: F) -> F:
        _log = logger or get_logger(func.__module__)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _log.log(level, "⏱  Entering %s", func.__qualname__)
            t0 = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - t0
                _log.log(level, "⏱  %s completed in %.3f s", func.__qualname__, elapsed)

        return wrapper  # type: ignore[return-value]
    return decorator


# ---------------------------------------------------------------------------
# Convenience: module-level logger for direct use in utils package
# ---------------------------------------------------------------------------

logger = get_logger("omni_medical_ocr")
