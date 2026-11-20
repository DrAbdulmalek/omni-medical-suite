"""Tests for app/core/decision_log.py — structured decision logger.

These tests verify:
1. log_decision() emits a JSON line to the dedicated logger
2. The schema (decision, outcome, reasons, inputs, skipped, duration_ms,
   session_id, ts) is correct
3. Failures inside log_decision never raise (it must be safe to call
   from any context)
4. Session id handling: env var, explicit set, new_session_id()
"""

from __future__ import annotations

import json
import logging
import os
from io import StringIO
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import decision_log
from app.core.decision_log import (
    get_session_id,
    log_decision,
    new_session_id,
    set_session_id,
)


@pytest.fixture(autouse=True)
def _reset_session_id():
    """Reset session_id before and after each test."""
    set_session_id(None)
    yield
    set_session_id(None)


@pytest.fixture
def captured_logs():
    """Capture log lines emitted by the app.decision_log logger."""
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("app.decision_log")
    prev_level = logger.level
    prev_handlers = logger.handlers[:]
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    try:
        yield buf
    finally:
        logger.handlers[:] = prev_handlers
        logger.setLevel(prev_level)


def _parse_log_lines(buf: StringIO) -> list[dict]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_log_decision_minimal(captured_logs):
    """log_decision with only required fields emits a valid JSON line."""
    payload = log_decision(decision="test_decision", outcome="yes")
    assert payload["decision"] == "test_decision"
    assert payload["outcome"] == "yes"
    assert payload["reasons"] == []
    lines = _parse_log_lines(captured_logs)
    assert len(lines) == 1
    assert lines[0]["decision"] == "test_decision"


def test_log_decision_full_schema(captured_logs):
    """All optional fields are present in the emitted JSON when provided."""
    set_session_id("sess-abc")
    log_decision(
        decision="engine_selection",
        outcome=["EasyOCR", "Tesseract"],
        reasons=["Arabic/mixed language (ar)", "low image quality"],
        inputs={"profile": "balanced", "language": "ar", "image_quality": 0.5},
        skipped=["PaddleOCR", "Nougat"],
        duration_ms=0.42,
    )
    lines = _parse_log_lines(captured_logs)
    assert len(lines) == 1
    line = lines[0]
    assert line["decision"] == "engine_selection"
    assert line["outcome"] == ["EasyOCR", "Tesseract"]
    assert line["reasons"] == ["Arabic/mixed language (ar)", "low image quality"]
    assert line["inputs"]["profile"] == "balanced"
    assert line["skipped"] == ["PaddleOCR", "Nougat"]
    assert line["duration_ms"] == 0.42
    assert line["session_id"] == "sess-abc"
    assert "ts" in line  # ISO 8601 timestamp present


def test_log_decision_outcome_scalar(captured_logs):
    """Scalar outcomes are passed through as-is."""
    log_decision(decision="rtl_reversal", outcome="reversed")
    lines = _parse_log_lines(captured_logs)
    assert lines[0]["outcome"] == "reversed"


def test_log_decision_outcome_set(captured_logs):
    """Set outcomes are normalized to lists."""
    log_decision(decision="dedup_decision", outcome={"a", "b"})
    lines = _parse_log_lines(captured_logs)
    assert sorted(lines[0]["outcome"]) == ["a", "b"]


def test_log_decision_inputs_non_jsonable(captured_logs):
    """Non-JSON values in inputs are coerced to strings, not crashed on."""
    class Foo:
        def __repr__(self):
            return "Foo()"

    log_decision(
        decision="test",
        outcome="ok",
        inputs={"obj": Foo(), "normal": 42},
    )
    lines = _parse_log_lines(captured_logs)
    assert lines[0]["inputs"]["normal"] == 42
    assert "Foo" in lines[0]["inputs"]["obj"]


# ---------------------------------------------------------------------------
# Robustness tests
# ---------------------------------------------------------------------------


def test_log_decision_never_raises():
    """log_decision must not raise even on pathological inputs."""
    # Recursive dict — would crash naive json.dumps
    d: dict = {}
    d["self"] = d
    payload = log_decision(decision="test", outcome="ok", inputs=d)
    assert payload["decision"] == "test"


# ---------------------------------------------------------------------------
# Session id tests
# ---------------------------------------------------------------------------


def test_session_id_env_var(monkeypatch):
    """OMNI_SESSION_ID env var seeds the session_id."""
    # Reimport to pick up env var (module-level read at import time)
    monkeypatch.setenv("OMNI_SESSION_ID", "env-sess-123")
    import importlib

    importlib.reload(decision_log)
    try:
        assert decision_log.get_session_id() == "env-sess-123"
    finally:
        monkeypatch.delenv("OMNI_SESSION_ID", raising=False)
        importlib.reload(decision_log)


def test_set_get_session_id():
    """set_session_id / get_session_id round-trip."""
    set_session_id("manual-xyz")
    assert get_session_id() == "manual-xyz"


def test_new_session_id_unique():
    """new_session_id() returns different values across calls."""
    a = new_session_id()
    b = new_session_id()
    assert a != b
    assert get_session_id() == b  # last one set wins


def test_session_id_in_emitted_log(captured_logs):
    """session_id appears in the emitted JSON when set."""
    set_session_id("sess-emit")
    log_decision(decision="x", outcome="y")
    lines = _parse_log_lines(captured_logs)
    assert lines[0]["session_id"] == "sess-emit"


def test_no_session_id_when_unset(captured_logs):
    """No session_id key in the emitted JSON when not set."""
    set_session_id(None)
    log_decision(decision="x", outcome="y")
    lines = _parse_log_lines(captured_logs)
    assert "session_id" not in lines[0]


def test_explicit_session_id_overrides_global(captured_logs):
    """Per-call session_id kwarg overrides the global session_id."""
    set_session_id("global")
    log_decision(decision="x", outcome="y", session_id="per-call")
    lines = _parse_log_lines(captured_logs)
    assert lines[0]["session_id"] == "per-call"
