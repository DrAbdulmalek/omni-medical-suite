"""Offline regression tests for training content integrity and export ledger."""
import sqlite3

import pytest

from packages.ocr_contracts.integrity_ledger import (
    approve_sample,
    compute_content_hash,
    connect_ledger,
    record_export_attempt,
)


def _payload(correct_text="الجرعة ٥ ملغ", **extra):
    return {"verbatim_text": correct_text, "normalized_view": correct_text, **extra}


def _export(conn, payload, *, key="export-1", destination="local-jsonl",
            authorized=("local-jsonl",), consent=True, auth_ref="local-approval-7"):
    return record_export_attempt(
        conn, sample_id="sample-1", payload=payload, dataset_version="ds-v1",
        destination=destination, actor="reviewer-1", authorization_ref=auth_ref,
        authorized_destinations=authorized, consent=consent, idempotency_key=key,
    )


def test_hash_is_deterministic_and_key_order_independent():
    left = {"verbatim_text": "abc", "metadata": {"b": 2, "a": 1}}
    right = {"metadata": {"a": 1, "b": 2}, "verbatim_text": "abc"}
    assert compute_content_hash(left) == compute_content_hash(right)


def test_hash_changes_for_meaningful_content_or_schema_change():
    assert compute_content_hash(_payload()) != compute_content_hash(_payload("الجرعة ١٠ ملغ"))
    assert compute_content_hash(_payload(), schema_version=1) != compute_content_hash(_payload(), schema_version=2)


def test_edit_after_approval_blocks_export_as_stale():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    result = _export(conn, _payload("modified"), key="stale")
    assert result["outcome"] == "blocked"
    assert result["reason_code"] == "stale_approval"


@pytest.mark.parametrize(
    ("approval_consent", "export_consent", "destination", "authorized", "expected"),
    [
        (False, True, "local-jsonl", ("local-jsonl",), "consent_missing"),
        (True, False, "local-jsonl", ("local-jsonl",), "consent_missing"),
        (True, True, "remote-hub", ("local-jsonl",), "destination_not_authorized"),
    ],
)
def test_consent_and_destination_are_fail_closed(approval_consent, export_consent,
                                                  destination, authorized, expected):
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=approval_consent, destination="local-jsonl")
    result = _export(conn, _payload(), key=f"blocked-{expected}", destination=destination,
                     authorized=authorized, consent=export_consent)
    assert result["outcome"] == "blocked"
    assert result["reason_code"] == expected


def test_missing_approval_blocks_export_and_records_event():
    conn = connect_ledger(":memory:")
    result = _export(conn, _payload(), key="no-approval")
    assert result["outcome"] == "blocked"
    assert result["reason_code"] == "approval_missing"
    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1


def test_duplicate_idempotency_key_returns_same_event_without_duplicate_row():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    first = _export(conn, _payload(), key="same-key")
    second = _export(conn, _payload(), key="same-key")
    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1


def test_ledger_rows_reject_update_and_delete():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    _export(conn, _payload(), key="append-only")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE export_events SET outcome='failed'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM export_events")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE approvals SET reviewer='other'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM approvals")


def test_remote_destination_requires_explicit_destination_scoped_authorization():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="remote-hub")
    result = _export(conn, _payload(), key="remote-no-auth",
                     destination="remote-hub", authorized=("local-jsonl",), auth_ref="remote-auth")
    assert result["outcome"] == "blocked"
    assert result["reason_code"] == "destination_not_authorized"


def test_approved_destination_and_authorization_can_be_prepared_but_not_published():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    result = _export(conn, _payload(), key="local-ok")
    assert result["outcome"] == "prepared"
    assert result["reason_code"] == "eligible"
    # This module records eligibility only; it has no upload/publish side effect.
    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1

def test_idempotency_key_reuse_with_changed_request_is_rejected():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    _export(conn, _payload(), key="bound-key")
    with pytest.raises(ValueError, match="idempotency_key_reused_for_different_request"):
        _export(conn, _payload("different payload"), key="bound-key")
    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1

