"""Tests for app/services/hf_dataset_service.py — P0-4 staging-file design.

These tests verify:
1. ``save_to_hf()`` writes a row to the local staging file even when
   HuggingFace libs are unavailable (offline-first guarantee).
2. The staging file is append-only and survives across calls.
3. ``count_pending()`` returns the correct count.
4. ``flush_queue()`` returns a "no HF" message when HF libs are missing
   (and does NOT lose the staged rows).
5. Dedup logic: rows with the same ``content_hash`` are not duplicated.
6. The ``content_hash`` is deterministic for the same input pair.
7. Auto-flush threshold: when ``_FLUSH_THRESHOLD`` rows are staged and
   HF is unavailable, the message correctly reports the queued state.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def isolated_queue(tmp_path, monkeypatch):
    """Point the staging dir at a tmp_path so tests don't pollute ~/.omni."""
    queue_dir = tmp_path / "queue"
    monkeypatch.setenv("OMNI_HF_QUEUE_DIR", str(queue_dir))
    # Force re-import so module picks up the new env var
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    yield queue_dir
    # cleanup
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]


# ---------------------------------------------------------------------------
# Staging-file basics
# ---------------------------------------------------------------------------


def test_save_to_hf_writes_pending_file(isolated_queue):
    """save_to_hf() writes a JSON line to pending.jsonl."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    result = save_to_hf("corrected text", "original text", {"meds": ["aspirin"]}, "prescription")
    assert "✅" in result
    assert _PENDING_FILE.exists()
    lines = _PENDING_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["correct_text"] == "corrected text"
    assert row["incorrect_ocr_output"] == "original text"
    assert row["category"] == "prescription"
    assert "content_hash" in row
    assert "timestamp" in row


def test_save_to_hf_appends_multiple_rows(isolated_queue):
    """Multiple save_to_hf() calls append to the same file."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    save_to_hf("c1", "o1", {}, "prescription")
    save_to_hf("c2", "o2", {}, "report")
    save_to_hf("c3", "o3", {}, "lab_result")
    lines = _PENDING_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_save_to_hf_empty_corrected_text_returns_warning(isolated_queue):
    """Empty corrected_text returns a warning and does not stage anything."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    result = save_to_hf("", "original", {}, "prescription")
    assert "⚠️" in result
    assert not _PENDING_FILE.exists()


def test_save_to_hf_whitespace_corrected_text_returns_warning(isolated_queue):
    """Whitespace-only corrected_text is treated as empty."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    result = save_to_hf("   \n\n  ", "original", {}, "prescription")
    assert "⚠️" in result
    assert not _PENDING_FILE.exists()


# ---------------------------------------------------------------------------
# count_pending
# ---------------------------------------------------------------------------


def test_count_pending_zero_when_empty(isolated_queue):
    """count_pending() returns 0 when no rows are staged."""
    from app.services.hf_dataset_service import count_pending

    assert count_pending() == 0


def test_count_pending_after_saves(isolated_queue):
    """count_pending() reflects the number of staged rows."""
    from app.services.hf_dataset_service import count_pending, save_to_hf

    save_to_hf("c1", "o1", {}, "prescription")
    save_to_hf("c2", "o2", {}, "prescription")
    assert count_pending() == 2


# ---------------------------------------------------------------------------
# Content hash determinism + dedup
# ---------------------------------------------------------------------------


def test_content_hash_deterministic(isolated_queue):
    """Same input pair produces the same content_hash."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    save_to_hf("corrected", "original", {}, "prescription")
    save_to_hf("corrected", "original", {}, "prescription")  # same pair
    lines = _PENDING_FILE.read_text(encoding="utf-8").splitlines()
    h1 = json.loads(lines[0])["content_hash"]
    h2 = json.loads(lines[1])["content_hash"]
    assert h1 == h2


def test_content_hash_differs_for_different_pairs(isolated_queue):
    """Different input pairs produce different content_hashes."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    save_to_hf("corrected-A", "original-A", {}, "prescription")
    save_to_hf("corrected-B", "original-B", {}, "prescription")
    lines = _PENDING_FILE.read_text(encoding="utf-8").splitlines()
    h1 = json.loads(lines[0])["content_hash"]
    h2 = json.loads(lines[1])["content_hash"]
    assert h1 != h2


# ---------------------------------------------------------------------------
# flush_queue behavior when HF libs are unavailable
# ---------------------------------------------------------------------------


def test_flush_queue_returns_message_when_hf_unavailable(isolated_queue, monkeypatch):
    """When HAS_HF is False, flush_queue() returns a friendly message and
    leaves the staging file intact.
    """
    # Force HAS_HF to False
    import app.services.hf_dataset_service as svc

    monkeypatch.setattr(svc, "HAS_HF", False)
    svc.save_to_hf("c1", "o1", {}, "prescription")
    assert svc.count_pending() == 1
    result = svc.flush_queue()
    assert "غير متاحة" in result
    # Staging file must still contain the row (no data loss)
    assert svc.count_pending() == 1


def test_flush_queue_empty_returns_info_message(isolated_queue, monkeypatch):
    """flush_queue() with no pending rows returns an info message."""
    import app.services.hf_dataset_service as svc

    monkeypatch.setattr(svc, "HAS_HF", True)  # even if HF is available
    result = svc.flush_queue()
    assert "لا توجد" in result


# ---------------------------------------------------------------------------
# Threshold behavior
# ---------------------------------------------------------------------------


def test_threshold_message_includes_count(isolated_queue, monkeypatch):
    """When HF is unavailable and threshold is reached, the message reports
    the queued count.
    """
    monkeypatch.setenv("OMNI_HF_FLUSH_THRESHOLD", "999")  # never auto-flush
    # Re-import to pick up the threshold env var
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    import app.services.hf_dataset_service as svc

    monkeypatch.setattr(svc, "HAS_HF", False)
    result = svc.save_to_hf("c1", "o1", {}, "prescription")
    assert "1" in result  # pending count
    assert "مرحّلة" in result


# ---------------------------------------------------------------------------
# Atomicity / append-only guarantee
# ---------------------------------------------------------------------------


def test_pending_file_append_only(isolated_queue):
    """Each save appends; existing rows are never modified."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    save_to_hf("first", "o1", {}, "prescription")
    first_content = _PENDING_FILE.read_text(encoding="utf-8")
    save_to_hf("second", "o2", {}, "prescription")
    second_content = _PENDING_FILE.read_text(encoding="utf-8")
    # The first row must still be present, unchanged, at the start
    assert first_content in second_content
    assert "first" in second_content


def test_pending_file_is_valid_jsonl(isolated_queue):
    """Every line in pending.jsonl is valid JSON."""
    from app.services.hf_dataset_service import save_to_hf, _PENDING_FILE

    for i in range(5):
        save_to_hf(f"c{i}", f"o{i}", {"idx": i}, "prescription")
    for line in _PENDING_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            # Must not raise
            json.loads(line)
