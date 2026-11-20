"""app/core/decision_log.py — structured decision logger.

Provides ``log_decision()`` — a single entry point for recording
non-deterministic runtime decisions in a structured, machine-readable
format. Designed to be lightweight (no dependencies on observability
package, no JSON schema enforcement) so it can be used from any layer
of the codebase without coupling.

Output format: one JSON line per decision, written to the standard
Python logger ``app.decision_log``. Configure a JSON-lines handler in
production to ship decisions to your log aggregator; in dev the lines
appear in the normal stderr stream.

Decision schema (informal):
    {
        "ts": "2026-07-19T00:30:00Z",          # ISO 8601 UTC
        "decision": "engine_selection",         # short snake_case key
        "outcome": ["EasyOCR"],                 # the chosen value(s)
        "reasons": ["Arabic/mixed language"],   # why this outcome
        "inputs": {                             # what fed the decision
            "profile": "balanced",
            "language": "ar",
            "image_quality": 0.8
        },
        "skipped": ["PaddleOCR"],               # alternatives considered & rejected
        "session_id": "abc123",                 # optional correlation id
        "duration_ms": 0.4                      # optional timing
    }

Usage:
    from app.core.decision_log import log_decision

    log_decision(
        decision="engine_selection",
        outcome=["EasyOCR"],
        reasons=["Arabic/mixed language (ar)"],
        inputs={"profile": "balanced", "language": "ar", "image_quality": 0.8},
        skipped=["PaddleOCR"],
    )

Design notes
------------
- Pure stdlib: only ``json``, ``logging``, ``datetime``, ``uuid``, ``os``.
- No module-level state except the logger and an optional process-wide
  ``session_id`` (set via ``set_session_id()`` or ``$OMNI_SESSION_ID``).
- The function never raises: a logging failure must not break the call
  site. Errors are swallowed and reported via the standard logger.
- ``inputs`` and ``skipped`` are optional; ``decision`` and ``outcome``
  are required.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

# Dedicated logger so operators can route decisions to a separate file
# without touching the root logger config.
_logger = logging.getLogger("app.decision_log")
if not _logger.handlers:
    # Default handler so decisions are visible even without explicit config.
    # In production, attach a JSON-lines file handler to this logger.
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False  # avoid double-emission via root

# Process-wide correlation id. Set once per process; override per-request
# via set_session_id() in middleware.
_session_id: str | None = os.environ.get("OMNI_SESSION_ID")


def set_session_id(session_id: str | None) -> None:
    """Set the process-wide session_id included in every decision log."""
    global _session_id
    _session_id = session_id


def get_session_id() -> str | None:
    """Return the current process-wide session_id (or None)."""
    return _session_id


def new_session_id() -> str:
    """Generate and set a fresh session_id; return it."""
    sid = uuid.uuid4().hex[:12]
    set_session_id(sid)
    return sid


def log_decision(
    *,
    decision: str,
    outcome: Any,
    reasons: Iterable[str] | None = None,
    inputs: dict[str, Any] | None = None,
    skipped: Iterable[Any] | None = None,
    duration_ms: float | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Emit one structured decision log line.

    Returns the dict that was logged (useful for tests and for chaining
    into a result schema). Never raises.
    """
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": decision,
        "outcome": _coerce_outcome(outcome),
        "reasons": list(reasons) if reasons else [],
    }
    if inputs:
        payload["inputs"] = _safe_jsonable(inputs)
    if skipped:
        payload["skipped"] = list(skipped)
    if duration_ms is not None:
        payload["duration_ms"] = round(float(duration_ms), 3)
    sid = session_id or _session_id
    if sid:
        payload["session_id"] = sid

    try:
        line = json.dumps(payload, ensure_ascii=False, default=_json_default)
        _logger.info(line)
    except Exception:  # pragma: no cover — logging must never break caller
        try:
            _logger.warning("decision_log serialization failed: decision=%s", decision)
        except Exception:
            pass
    return payload


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_outcome(value: Any) -> Any:
    """Normalize outcome to a JSON-friendly shape.

    Lists/tuples/sets become lists; dicts become JSON-safe dicts;
    scalars pass through; dataclasses are converted via ``__dict__``;
    other objects become their ``str()``.
    """
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_default(v) if not _is_jsonable(v) else v for v in value]
    if isinstance(value, dict):
        # P1-3: dicts should pass through as dicts (not be stringified)
        # so downstream JSON consumers can query outcome fields directly.
        return _safe_jsonable(value)
    if _is_jsonable(value):
        return value
    return _json_default(value)


def _is_jsonable(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool, type(None)))


def _safe_jsonable(obj: dict[str, Any], _seen: set[int] | None = None) -> dict[str, Any]:
    """Coerce a dict's values to JSON-friendly types, preserving scalars.

    P1-3: handles nested lists and dicts recursively (previously
    stringified any non-scalar value, which broke dict outcomes
    containing lists of strings). Uses a `_seen` set to break
    circular references (falls back to str() for already-seen objects).
    """
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return "<circular>"
    _seen.add(obj_id)

    out: dict[str, Any] = {}
    for k, v in obj.items():
        if _is_jsonable(v):
            out[k] = v
        elif isinstance(v, (list, tuple, set, frozenset)):
            out[k] = [
                item if _is_jsonable(item)
                else (_safe_jsonable(item, _seen) if isinstance(item, dict) else _json_default(item))
                for item in v
            ]
        elif isinstance(v, dict):
            out[k] = _safe_jsonable(v, _seen)
        else:
            out[k] = _json_default(v)
    return out


def _json_default(value: Any) -> Any:
    """Last-resort serializer for non-JSON values."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "__dict__"):
        d = getattr(value, "__dict__", None)
        if isinstance(d, dict) and d:
            return {k: _json_default(v) for k, v in d.items()}
    # Final fallback: stringify. This guarantees a non-empty result
    # for objects whose __dict__ is empty (e.g. classes with __slots__
    # or objects without any instance attributes).
    return str(value)
