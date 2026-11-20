"""
observability.integration
=========================

Drop-in hooks for instrumenting scanner_fixer and other modules.

Usage
-----
    from observability.integration import instrument_scanner_fixer
    instrument_scanner_fixer()  # call once at app start

Then every ``fix_scan()``, ``auto_crop()``, ``deskew()``, ``auto_rotate()``,
``enhance_for_ocr()`` and ``DocumentPreprocessor.process()`` call will emit
structured events to the JSONL log.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable

from .logger import LogCategory, Severity, get_logger, log_event


def _instrument(
    func: Callable[..., Any],
    *,
    event_prefix: str,
    category: LogCategory = LogCategory.PREPROCESS,
    logger_name: str = "observability.scanner_fixer",
) -> Callable[..., Any]:
    """Wrap a function so it emits start/finish/error events."""

    log = get_logger(logger_name)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        # Try to extract an "input_shape" without crashing on weird inputs
        input_shape: Any = None
        try:
            first = args[0] if args else kwargs.get("image")
            if hasattr(first, "shape"):
                input_shape = list(first.shape)
            elif hasattr(first, "size"):
                input_shape = list(first.size)
        except Exception:
            pass

        log_event(
            f"{event_prefix}.start",
            category=category,
            level=Severity.DEBUG,
            logger=log,
            input_shape=input_shape,
        )
        try:
            result = func(*args, **kwargs)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            output_shape: Any = None
            try:
                if hasattr(result, "shape"):
                    output_shape = list(result.shape)
                elif isinstance(result, tuple) and result and hasattr(result[0], "shape"):
                    output_shape = list(result[0].shape)
            except Exception:
                pass

            log_event(
                f"{event_prefix}.success",
                category=category,
                level=Severity.INFO,
                logger=log,
                duration_ms=duration_ms,
                input_shape=input_shape,
                output_shape=output_shape,
                status="ok",
            )
            return result
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log_event(
                f"{event_prefix}.error",
                category=LogCategory.ERROR,
                level=Severity.ERROR,
                logger=log,
                duration_ms=duration_ms,
                input_shape=input_shape,
                status="error",
                error_type=type(exc).__name__,
                exception=str(exc),
            )
            raise

    return wrapper


def instrument_scanner_fixer() -> None:
    """
    Patch the scanner_fixer public API to emit observability events.

    Safe to call multiple times — re-patching is a no-op.
    """
    try:
        import scanner_fixer  # type: ignore
    except ImportError:
        try:
            import sys
            from pathlib import Path

            repo_root = Path(__file__).resolve().parents[4]
            src = repo_root / "packages" / "scanner_fixer" / "src"
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            import scanner_fixer  # type: ignore  # noqa: F811
        except ImportError as exc:
            raise RuntimeError(
                f"scanner_fixer not importable; cannot instrument: {exc}"
            )

    # Avoid double-instrumentation
    if getattr(scanner_fixer, "_omni_instrumented", False):
        return

    # Patch module-level functions
    patches = [
        ("fix_scan", "fix_scan"),
        ("fix_scan_batch", "fix_scan_batch"),
        ("auto_crop", "auto_crop"),
        ("deskew", "deskew"),
        ("auto_rotate", "auto_rotate"),
        ("enhance_for_ocr", "enhance_for_ocr"),
    ]
    for attr_name, event_name in patches:
        original = getattr(scanner_fixer, attr_name, None)
        if original is None or not callable(original):
            continue
        instrumented = _instrument(original, event_prefix=event_name)
        setattr(scanner_fixer, attr_name, instrumented)

    # Patch DocumentPreprocessor methods (instance-bound — wrap on the class)
    try:
        from scanner_fixer.enhanced_preprocessor import DocumentPreprocessor  # type: ignore

        for method_name, event_name in [
            ("process", "preprocessor.process"),
            ("_advanced_deskew", "preprocessor.advanced_deskew"),
            ("_remove_noise", "preprocessor.remove_noise"),
            ("_remove_shadows", "preprocessor.remove_shadows"),
        ]:
            original = getattr(DocumentPreprocessor, method_name, None)
            if original is None:
                continue
            instrumented = _instrument(
                original,
                event_prefix=event_name,
                logger_name="observability.scanner_fixer.preprocessor",
            )
            setattr(DocumentPreprocessor, method_name, instrumented)
    except ImportError:
        pass

    scanner_fixer._omni_instrumented = True  # type: ignore[attr-defined]
