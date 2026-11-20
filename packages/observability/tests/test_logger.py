"""Tests for observability package — logger + integration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make package importable
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "packages" / "observability" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from observability import (  # noqa: E402
    LogCategory,
    Severity,
    configure_logging,
    get_logger,
    log_event,
    reset_session_id,
)


@pytest.fixture
def tmp_log_dir(tmp_path):
    """Fresh log dir per test."""
    log_dir = tmp_path / "logs"
    configure_logging(log_dir=log_dir, reset=True, console=False)
    yield log_dir
    # Reset for next test
    configure_logging(log_dir=log_dir, reset=True, console=False)


def test_log_event_writes_jsonl(tmp_log_dir):
    reset_session_id()
    log_event("test.event", category=LogCategory.LIFECYCLE,
              level=Severity.INFO, custom_field="abc")
    jsonl = tmp_log_dir / "omni.jsonl"
    assert jsonl.exists()
    lines = [l for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "No JSON lines written"
    last = json.loads(lines[-1])
    assert last["event"] == "test.event"
    assert last["category"] == "lifecycle"
    assert last["level"] == "info"
    assert last["custom_field"] == "abc"
    assert "session_id" in last and len(last["session_id"]) == 12


def test_errors_jsonl_only_warnings_and_above(tmp_log_dir):
    log_event("info.1", level=Severity.INFO, category=LogCategory.OTHER)
    log_event("warn.1", level=Severity.WARNING, category=LogCategory.PERFORMANCE)
    log_event("err.1", level=Severity.ERROR, category=LogCategory.ERROR,
              error_type="ValueError")
    err_jsonl = tmp_log_dir / "errors.jsonl"
    assert err_jsonl.exists()
    err_lines = [l for l in err_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(err_lines) == 2  # warning + error, no info
    events = [json.loads(l)["event"] for l in err_lines]
    assert "warn.1" in events and "err.1" in events


def test_session_id_consistent_within_session(tmp_log_dir):
    sid = reset_session_id()
    log_event("a")
    log_event("b")
    jsonl = tmp_log_dir / "omni.jsonl"
    lines = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert all(l["session_id"] == sid for l in lines[-2:])


def test_get_logger_returns_child(tmp_log_dir):
    log = get_logger("test_module")
    assert log.name == "observability.test_module"


def test_category_enum_values():
    assert LogCategory.OCR.value == "ocr"
    assert LogCategory.PREPROCESS.value == "preprocess"
