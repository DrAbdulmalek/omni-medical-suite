"""Integration tests for the HF staging service's content-bound export gate."""
from __future__ import annotations

import pytest

from packages.ocr_contracts.integrity_ledger import connect_ledger
from app.services import hf_dataset_service as service


@pytest.fixture
def ledger_paths(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    monkeypatch.setattr(service, "_STAGE_DIR", stage)
    monkeypatch.setattr(service, "_LEDGER_FILE", stage / "training_integrity_ledger.sqlite3")
    monkeypatch.setattr(service, "_UPLOADED_DIR", stage / "uploaded")
    monkeypatch.setattr(service, "_PENDING_FILE", stage / "pending.jsonl")
    return stage / "training_integrity_ledger.sqlite3"


def _row(*, consent=True):
    return {
        "incorrect_ocr_output": "الجرعة ٥ ملغ",
        "correct_text": "الجرعة 10 ملغ",
        "category": "prescription",
        "entities": '{"medication": "example"}',
        "timestamp": "volatile timestamp intentionally excluded",
        "content_hash": "legacy-dedup-hash",
        "consent": consent,
    }


def test_explicit_consent_is_bound_to_exact_payload_and_prepared(ledger_paths):
    row = _row(consent=True)
    row["integrity_hash"] = service._record_row_approval(row)

    prepared, blocked = service._prepare_rows_with_ledger([row])

    assert prepared == [row]
    assert blocked == 0
    conn = connect_ledger(str(ledger_paths))
    try:
        approval = conn.execute(
            "SELECT sample_id, content_hash, consent, destination FROM approvals"
        ).fetchone()
        assert approval["sample_id"] == row["integrity_hash"]
        assert approval["content_hash"] == row["integrity_hash"]
        assert approval["consent"] == 1
        assert approval["destination"] == service.HF_DATASET
        event = conn.execute(
            "SELECT outcome, destination FROM export_events"
        ).fetchone()
        assert event["outcome"] == "prepared"
        assert event["destination"] == service.HF_DATASET
    finally:
        conn.close()


def test_unapproved_legacy_or_nonconsented_rows_fail_closed(ledger_paths):
    nonconsented = _row(consent=False)
    nonconsented["integrity_hash"] = service._record_row_approval(nonconsented)
    legacy = _row(consent=True)  # no ledger approval/hash from the old staging format

    prepared, blocked = service._prepare_rows_with_ledger([nonconsented, legacy])

    assert prepared == []
    assert blocked == 2


def test_changed_payload_after_approval_is_blocked(ledger_paths):
    row = _row(consent=True)
    row["integrity_hash"] = service._record_row_approval(row)
    row["correct_text"] = "نص تغير بعد الموافقة"

    prepared, blocked = service._prepare_rows_with_ledger([row])

    assert prepared == []
    assert blocked == 1


def test_same_staged_row_is_idempotent_after_ledger_reopen(ledger_paths):
    row = _row(consent=True)
    row["integrity_hash"] = service._record_row_approval(row)
    first, blocked_first = service._prepare_rows_with_ledger([row])
    assert first == [row] and blocked_first == 0

    # Force a fresh connection on the second pass; the durable ledger returns
    # the same prepared event rather than appending a duplicate event.
    second, blocked_second = service._prepare_rows_with_ledger([row])
    assert second == [row] and blocked_second == 0

    conn = connect_ledger(str(ledger_paths))
    try:
        assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1
    finally:
        conn.close()
