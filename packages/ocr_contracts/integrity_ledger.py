"""Versioned content identity and append-only training export audit ledger.

This module records approvals and export attempts in SQLite. It performs no
network I/O and never publishes a dataset. Callers must supply explicit consent
and destination authorization for each export attempt.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

CANONICALIZATION_VERSION = 1


def canonical_payload(payload: dict[str, Any], *, schema_version: int = CANONICALIZATION_VERSION) -> bytes:
    """Return deterministic UTF-8 bytes for a versioned payload.

    The payload must contain only JSON-compatible values. Timestamps, paths,
    and other volatile provenance should be kept outside the content payload.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")
    if schema_version < 1:
        raise ValueError("schema_version must be positive")
    envelope = {"schema_version": schema_version, "payload": payload}
    try:
        text = json.dumps(
            envelope, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must contain finite, JSON-compatible values") from exc
    return text.encode("utf-8")


def compute_content_hash(payload: dict[str, Any], *, schema_version: int = CANONICALIZATION_VERSION) -> str:
    """SHA-256 identity for the exact canonical payload and schema version."""
    return hashlib.sha256(canonical_payload(payload, schema_version=schema_version)).hexdigest()


def connect_ledger(database: str | sqlite3.Connection) -> sqlite3.Connection:
    """Open/initialize a ledger. Pass ':memory:' or a temporary DB in tests."""
    conn = database if isinstance(database, sqlite3.Connection) else sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS approvals (
            approval_id TEXT PRIMARY KEY,
            sample_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version INTEGER NOT NULL CHECK(schema_version > 0),
            reviewer TEXT NOT NULL,
            consent INTEGER NOT NULL CHECK(consent IN (0, 1)),
            destination TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_approvals_sample
            ON approvals(sample_id, created_at);
        CREATE TABLE IF NOT EXISTS export_events (
            event_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            sample_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version INTEGER NOT NULL CHECK(schema_version > 0),
            dataset_version TEXT NOT NULL,
            destination TEXT NOT NULL,
            actor TEXT NOT NULL,
            authorization_ref TEXT NOT NULL,
            consent INTEGER NOT NULL DEFAULT 0 CHECK(consent IN (0, 1)),
            authorized_destinations TEXT NOT NULL DEFAULT '[]',
            outcome TEXT NOT NULL CHECK(outcome IN ('blocked', 'prepared', 'failed')),
            reason_code TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_exports_sample
            ON export_events(sample_id, created_at);
        CREATE TABLE IF NOT EXISTS delivery_events (
            event_id TEXT PRIMARY KEY,
            event_key TEXT NOT NULL UNIQUE,
            correlation_id TEXT NOT NULL,
            destination TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK(outcome IN (
                'push_started', 'push_succeeded', 'push_failed',
                'push_ambiguous', 'remote_present', 'archive_failed', 'queue_cleanup_failed'
            )),
            error_code TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_delivery_correlation
            ON delivery_events(correlation_id, created_at);
        CREATE TRIGGER IF NOT EXISTS approvals_no_update
        BEFORE UPDATE ON approvals BEGIN
            SELECT RAISE(ABORT, 'approvals are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS approvals_no_delete
        BEFORE DELETE ON approvals BEGIN
            SELECT RAISE(ABORT, 'approvals are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS export_events_no_update
        BEFORE UPDATE ON export_events BEGIN
            SELECT RAISE(ABORT, 'export_events are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS export_events_no_delete
        BEFORE DELETE ON export_events BEGIN
            SELECT RAISE(ABORT, 'export_events are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS delivery_events_no_update
        BEFORE UPDATE ON delivery_events BEGIN
            SELECT RAISE(ABORT, 'delivery_events are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS delivery_events_no_delete
        BEFORE DELETE ON delivery_events BEGIN
            SELECT RAISE(ABORT, 'delivery_events are append-only');
        END;
    """)
    # Additive migration for ledgers created by earlier releases. Defaults preserve
    # old rows conservatively; old events cannot masquerade as fully specified requests.
    export_columns = {row["name"] for row in conn.execute("PRAGMA table_info(export_events)")}
    if "consent" not in export_columns:
        conn.execute("ALTER TABLE export_events ADD COLUMN consent INTEGER NOT NULL DEFAULT 0")
    if "authorized_destinations" not in export_columns:
        conn.execute("ALTER TABLE export_events ADD COLUMN authorized_destinations TEXT NOT NULL DEFAULT '[]'")

    # SQLite cannot alter a CHECK constraint in place. Rebuild older delivery
    # ledgers transactionally so the reconciliation outcome is accepted while
    # preserving all existing immutable event rows.
    delivery_schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='delivery_events'"
    ).fetchone()
    if delivery_schema and "remote_present" not in str(delivery_schema["sql"]):
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("DROP TABLE IF EXISTS delivery_events_migrating")
            conn.execute("""
                CREATE TABLE delivery_events_migrating (
                    event_id TEXT PRIMARY KEY,
                    event_key TEXT NOT NULL UNIQUE,
                    correlation_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK(outcome IN (
                        'push_started', 'push_succeeded', 'push_failed',
                        'push_ambiguous', 'remote_present', 'archive_failed',
                        'queue_cleanup_failed'
                    )),
                    error_code TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                INSERT INTO delivery_events_migrating
                    (event_id, event_key, correlation_id, destination, outcome, error_code, created_at)
                SELECT event_id, event_key, correlation_id, destination, outcome, error_code, created_at
                FROM delivery_events
            """)
            conn.execute("DROP TABLE delivery_events")
            conn.execute("ALTER TABLE delivery_events_migrating RENAME TO delivery_events")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_delivery_correlation
                ON delivery_events(correlation_id, created_at)
            """)
            conn.execute("""
                CREATE TRIGGER delivery_events_no_update
                BEFORE UPDATE ON delivery_events BEGIN
                    SELECT RAISE(ABORT, 'delivery_events are append-only');
                END
            """)
            conn.execute("""
                CREATE TRIGGER delivery_events_no_delete
                BEFORE DELETE ON delivery_events BEGIN
                    SELECT RAISE(ABORT, 'delivery_events are append-only');
                END
            """)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    conn.commit()
    return conn


def approve_sample(
    conn: sqlite3.Connection,
    *,
    sample_id: str,
    payload: dict[str, Any],
    reviewer: str,
    consent: bool,
    destination: str,
    schema_version: int = CANONICALIZATION_VERSION,
) -> str:
    """Append an approval bound to the current exact payload hash."""
    if not sample_id.strip() or not reviewer.strip() or not destination.strip():
        raise ValueError("sample_id, reviewer, and destination are required")
    digest = compute_content_hash(payload, schema_version=schema_version)
    approval_id = str(uuid.uuid4())
    with conn:
        conn.execute(
            """INSERT INTO approvals
               (approval_id, sample_id, content_hash, schema_version, reviewer,
                consent, destination, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (approval_id, sample_id, digest, schema_version, reviewer, int(consent),
             destination, _now()),
        )
    return digest


def record_export_attempt(
    conn: sqlite3.Connection,
    *,
    sample_id: str,
    payload: dict[str, Any],
    dataset_version: str,
    destination: str,
    actor: str,
    authorization_ref: str | None,
    authorized_destinations: Iterable[str],
    consent: bool,
    idempotency_key: str,
    schema_version: int = CANONICALIZATION_VERSION,
) -> dict[str, str]:
    """Atomically record an export decision; never exports data.

    BEGIN IMMEDIATE serializes decision+insert across SQLite connections, so
    concurrent requests cannot race between the idempotency lookup and insert.
    Callers must provide a connection with no active transaction. A repeated
    key returns its existing event only when the request identity matches.
    """
    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    if conn.in_transaction:
        raise ValueError("ledger connection must not have an active transaction")
    digest = compute_content_hash(payload, schema_version=schema_version)
    allowed = set(authorized_destinations)
    allowed_json = json.dumps(sorted(allowed), ensure_ascii=False, separators=(",", ":"))

    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = conn.execute(
            """SELECT event_id, outcome, reason_code, sample_id, content_hash,
                      schema_version, dataset_version, destination, actor, authorization_ref,
                      consent, authorized_destinations
               FROM export_events WHERE idempotency_key = ?""",
            (idempotency_key,),
        ).fetchone()
        if existing:
            identity = (
                existing["sample_id"], existing["content_hash"], existing["schema_version"],
                existing["dataset_version"], existing["destination"], existing["actor"],
                existing["authorization_ref"], existing["consent"],
                existing["authorized_destinations"],
            )
            requested = (
                sample_id, digest, schema_version, dataset_version, destination,
                actor or "unknown", authorization_ref or "", int(consent), allowed_json,
            )
            if identity != requested:
                raise ValueError("idempotency_key_reused_for_different_request")
            result = {
                "event_id": existing["event_id"],
                "outcome": existing["outcome"],
                "reason_code": existing["reason_code"],
            }
            conn.commit()
            return result

        latest = conn.execute(
            """SELECT content_hash, schema_version, reviewer, consent, destination
               FROM approvals WHERE sample_id = ?
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (sample_id,),
        ).fetchone()
        reason = "eligible"
        outcome = "prepared"
        if latest is None:
            outcome, reason = "blocked", "approval_missing"
        elif latest["content_hash"] != digest or latest["schema_version"] != schema_version:
            outcome, reason = "blocked", "stale_approval"
        elif not latest["consent"] or not consent:
            outcome, reason = "blocked", "consent_missing"
        elif latest["destination"] != destination or destination not in allowed:
            outcome, reason = "blocked", "destination_not_authorized"
        elif not actor.strip() or not authorization_ref:
            outcome, reason = "blocked", "authorization_provenance_missing"

        event_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO export_events
               (event_id, idempotency_key, sample_id, content_hash, schema_version,
                dataset_version, destination, actor, authorization_ref, consent,
                authorized_destinations, outcome, reason_code, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, idempotency_key, sample_id, digest, schema_version,
             dataset_version, destination, actor or "unknown",
             authorization_ref or "", int(consent), allowed_json, outcome, reason, _now()),
        )
        conn.commit()
        return {"event_id": event_id, "outcome": outcome, "reason_code": reason}
    except Exception:
        conn.rollback()
        raise

def record_delivery_event(
    conn: sqlite3.Connection,
    *,
    event_key: str,
    correlation_id: str,
    destination: str,
    outcome: str,
    error_code: str = "",
) -> dict[str, str]:
    """Append a delivery outcome; this records observations, not exactly-once delivery.

    Reusing an event key with identical content is idempotent. Reusing it with
    different content is rejected. No medical payload or credential is stored.
    """
    allowed_outcomes = {
        "push_started", "push_succeeded", "push_failed",
        "push_ambiguous", "remote_present", "archive_failed", "queue_cleanup_failed",
    }
    if not event_key.strip() or not correlation_id.strip() or not destination.strip():
        raise ValueError("event_key, correlation_id, and destination are required")
    if outcome not in allowed_outcomes:
        raise ValueError("unsupported delivery outcome")
    if conn.in_transaction:
        raise ValueError("ledger connection must not have an active transaction")
    safe_error_code = "".join(
        char for char in str(error_code).lower()
        if char.isalnum() or char in "_-"
    )[:80]
    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = conn.execute(
            """SELECT event_id, correlation_id, destination, outcome, error_code
               FROM delivery_events WHERE event_key = ?""",
            (event_key,),
        ).fetchone()
        requested = (correlation_id, destination, outcome, safe_error_code)
        if existing:
            identity = (
                existing["correlation_id"], existing["destination"],
                existing["outcome"], existing["error_code"],
            )
            if identity != requested:
                raise ValueError("delivery_event_key_reused_for_different_event")
            result = {"event_id": existing["event_id"], "outcome": existing["outcome"]}
            conn.commit()
            return result
        event_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO delivery_events
               (event_id, event_key, correlation_id, destination, outcome, error_code, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, event_key, correlation_id, destination, outcome, safe_error_code, _now()),
        )
        conn.commit()
        return {"event_id": event_id, "outcome": outcome}
    except Exception:
        conn.rollback()
        raise


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
