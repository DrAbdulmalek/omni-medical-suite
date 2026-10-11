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
            outcome TEXT NOT NULL CHECK(outcome IN ('blocked', 'prepared', 'failed')),
            reason_code TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_exports_sample
            ON export_events(sample_id, created_at);
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
    """)
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
    """Record an export decision only; this function never exports data.

    A repeated idempotency key returns the existing event without duplicating
    it. Any blocked attempt is retained as an audit event.
    """
    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    digest = compute_content_hash(payload, schema_version=schema_version)
    existing = conn.execute(
        """SELECT event_id, outcome, reason_code, sample_id, content_hash,
                  schema_version, dataset_version, destination, actor, authorization_ref
           FROM export_events WHERE idempotency_key = ?""",
        (idempotency_key,),
    ).fetchone()
    if existing:
        # Idempotency keys are bound to request identity; reusing a key for a
        # different payload or destination must not silently reuse an old result.
        identity = (
            existing["sample_id"], existing["content_hash"], existing["schema_version"],
            existing["dataset_version"], existing["destination"], existing["actor"],
            existing["authorization_ref"],
        )
        requested = (
            sample_id, digest, schema_version, dataset_version, destination, actor or "unknown",
            authorization_ref or "",
        )
        if identity != requested:
            raise ValueError("idempotency_key_reused_for_different_request")
        return {
            "event_id": existing["event_id"],
            "outcome": existing["outcome"],
            "reason_code": existing["reason_code"],
        }

    latest = conn.execute(
        """SELECT content_hash, schema_version, reviewer, consent, destination
           FROM approvals WHERE sample_id = ?
           ORDER BY created_at DESC, rowid DESC LIMIT 1""",
        (sample_id,),
    ).fetchone()
    allowed = set(authorized_destinations)
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
    with conn:
        conn.execute(
            """INSERT INTO export_events
               (event_id, idempotency_key, sample_id, content_hash, schema_version,
                dataset_version, destination, actor, authorization_ref, outcome,
                reason_code, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, idempotency_key, sample_id, digest, schema_version,
             dataset_version, destination, actor or "unknown",
             authorization_ref or "", outcome, reason, _now()),
        )
    return {"event_id": event_id, "outcome": outcome, "reason_code": reason}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
