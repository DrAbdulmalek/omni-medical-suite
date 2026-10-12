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


def test_concurrent_same_key_is_serialized_across_connections(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    db_path = str(tmp_path / "ledger.sqlite3")
    setup = connect_ledger(db_path)
    approve_sample(setup, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    setup.close()

    def attempt():
        conn = connect_ledger(db_path)
        try:
            return _export(conn, _payload(), key="concurrent-same-key")
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: attempt(), range(8)))

    assert len({result["event_id"] for result in results}) == 1
    check = connect_ledger(db_path)
    try:
        assert check.execute(
            "SELECT COUNT(*) FROM export_events WHERE idempotency_key = ?",
            ("concurrent-same-key",),
        ).fetchone()[0] == 1
    finally:
        check.close()


def test_export_rejects_connection_with_open_transaction():
    conn = connect_ledger(":memory:")
    conn.execute("BEGIN")
    with pytest.raises(ValueError, match="must not have an active transaction"):
        _export(conn, _payload(), key="active-transaction")
    conn.rollback()


def test_committed_event_survives_connection_close_and_reopen(tmp_path):
    db_path = str(tmp_path / "durable-ledger.sqlite3")
    conn = connect_ledger(db_path)
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    first = _export(conn, _payload(), key="durable-event")
    conn.close()

    reopened = connect_ledger(db_path)
    try:
        row = reopened.execute(
            "SELECT event_id, outcome, reason_code FROM export_events WHERE idempotency_key = ?",
            ("durable-event",),
        ).fetchone()
        assert dict(row) == first
        assert _export(reopened, _payload(), key="durable-event") == first
        assert reopened.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1
    finally:
        reopened.close()


def test_failed_idempotency_mismatch_rolls_back_and_connection_can_retry():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    original = _export(conn, _payload(), key="retry-boundary")

    with pytest.raises(ValueError, match="idempotency_key_reused_for_different_request"):
        _export(conn, _payload("tampered"), key="retry-boundary")

    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1
    retry = _export(conn, _payload(), key="retry-boundary")
    assert retry == original
    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1



def test_idempotency_key_reuse_with_changed_consent_is_rejected():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    _export(conn, _payload(), key="consent-bound")
    with pytest.raises(ValueError, match="idempotency_key_reused_for_different_request"):
        _export(conn, _payload(), key="consent-bound", consent=False)
    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1


def test_idempotency_key_reuse_with_changed_authorized_destinations_is_rejected():
    conn = connect_ledger(":memory:")
    approve_sample(conn, sample_id="sample-1", payload=_payload(), reviewer="reviewer-1",
                   consent=True, destination="local-jsonl")
    _export(conn, _payload(), key="destinations-bound")
    with pytest.raises(ValueError, match="idempotency_key_reused_for_different_request"):
        _export(conn, _payload(), key="destinations-bound",
                authorized=("local-jsonl", "remote-hub"))
    assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1


def test_legacy_export_event_schema_migrates_additively_and_fails_closed(tmp_path):
    db_path = str(tmp_path / "legacy-ledger.sqlite3")
    legacy = sqlite3.connect(db_path)
    legacy.execute("""
        CREATE TABLE export_events (
            event_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            sample_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version INTEGER NOT NULL CHECK(schema_version > 0),
            dataset_version TEXT NOT NULL,
            destination TEXT NOT NULL,
            actor TEXT NOT NULL,
            authorization_ref TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK(outcome IN ('blocked', 'prepared', 'failed')),
            reason_code TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    legacy.execute(
        """INSERT INTO export_events (
            event_id, idempotency_key, sample_id, content_hash, schema_version,
            dataset_version, destination, actor, authorization_ref, outcome,
            reason_code, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("legacy-event-1", "legacy-key-1", "legacy-sample", "legacy-hash", 1,
         "legacy-dataset", "remote-hub", "legacy-actor", "legacy-auth",
         "prepared", "eligible", "2026-01-01T00:00:00Z"),
    )
    legacy.commit()
    legacy.close()

    conn = connect_ledger(db_path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(export_events)")}
        assert {"consent", "authorized_destinations"} <= columns
        old = conn.execute(
            "SELECT * FROM export_events WHERE event_id = 'legacy-event-1'"
        ).fetchone()
        assert old["consent"] == 0
        assert old["authorized_destinations"] == "[]"
        assert old["sample_id"] == "legacy-sample"
    finally:
        conn.close()

    # Migration is repeatable and must not duplicate or rewrite historical rows.
    conn = connect_ledger(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 1
        result = record_export_attempt(
            conn, sample_id="legacy-sample", payload=_payload(),
            dataset_version="ds-v1", destination="remote-hub", actor="reviewer-1",
            authorization_ref="legacy-auth", authorized_destinations=("remote-hub",),
            consent=True, idempotency_key="post-migration-attempt",
        )
        # An old event is audit history, not proof of a current content-bound approval.
        assert result["outcome"] == "blocked"
        assert result["reason_code"] == "approval_missing"
        assert conn.execute("SELECT COUNT(*) FROM export_events").fetchone()[0] == 2
    finally:
        conn.close()
