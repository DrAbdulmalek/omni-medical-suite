"""Integration tests for the HF staging service's content-bound export gate."""
from __future__ import annotations

import pytest

from app.services import hf_dataset_service as service
from packages.ocr_contracts.integrity_ledger import connect_ledger


@pytest.fixture(autouse=True)
def mock_hf_cas_boundary(monkeypatch):
    """Keep service integration tests offline while preserving their push fakes.

    The dedicated test_hf_dataset_cas.py suite exercises the real CAS helper.
    These tests focus on staging, consent, ledger, archive, and retry behavior.
    """
    class FakeHfApi:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def fake_baseline(api, *, repo_id, token):
        return ("a" * 40, "data/train-00000-of-00001.parquet")

    def fake_cas_push(api, dataset, *, repo_id, token, parent_commit, data_path):
        # Existing test doubles model delivery with push_to_hub; retain that
        # behavior here without invoking any real Hugging Face network method.
        return dataset.push_to_hub(
            repo_id=repo_id,
            private=service.OMNI_HF_DATASET_PRIVATE,
            token=token,
        )

    monkeypatch.setattr(service, "HfApi", FakeHfApi, raising=False)
    monkeypatch.setattr(service, "get_verified_dataset_baseline", fake_baseline)
    monkeypatch.setattr(service, "push_parquet_snapshot_with_cas", fake_cas_push)


@pytest.fixture
def ledger_paths(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    monkeypatch.setattr(service, "_STAGE_DIR", stage)
    monkeypatch.setattr(service, "_QUEUE_LOCK_FILE", stage / ".queue.lock", raising=False)
    monkeypatch.setattr(service, "_LEDGER_FILE", stage / "training_integrity_ledger.sqlite3")
    monkeypatch.setattr(service, "_UPLOADED_DIR", stage / "uploaded")
    monkeypatch.setattr(service, "_PENDING_FILE", stage / "pending.jsonl")
    stage.mkdir(parents=True, exist_ok=True)
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


def test_unapproved_row_is_blocked_before_any_remote_read(ledger_paths, monkeypatch):
    row = _row(consent=True)  # legacy staged row has no content-bound approval
    service._PENDING_FILE.write_text(__import__("json").dumps(row) + "\n", encoding="utf-8")
    monkeypatch.setattr(service, "HAS_HF", True)
    monkeypatch.setattr(service, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(service, "HF_TOKEN", "test-token-not-used")

    def unexpected_remote_read(*args, **kwargs):
        pytest.fail("remote dataset read must not happen when the ledger blocks a row")

    monkeypatch.setattr(service, "load_dataset", unexpected_remote_read, raising=False)

    result = service.flush_queue()

    assert "سجل النزاهة" in result
    assert service._PENDING_FILE.exists()
    assert len(service._read_pending()) == 1


def test_ambiguous_remote_commit_recovers_by_dedup_without_second_push(ledger_paths, monkeypatch):
    import json

    row = _row(consent=True)
    row["integrity_hash"] = service._record_row_approval(row)
    service._PENDING_FILE.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(service, "HAS_HF", True)
    monkeypatch.setattr(service, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(service, "HF_TOKEN", "test-token-not-used")
    remote_rows = []
    push_calls = []

    class ExistingDataset:
        column_names = ["content_hash", "integrity_hash"]

        def __len__(self):
            return len(remote_rows)

        def __getitem__(self, key):
            return [item.get(key) for item in remote_rows]

        def to_pandas(self):
            return [dict(item) for item in remote_rows]

    class FakePandas:
        @staticmethod
        def DataFrame(rows):
            return rows

        @staticmethod
        def concat(frames, ignore_index=True):
            return [item for frame in frames for item in frame]

    class CommitThenTimeoutDataset:
        def __init__(self, frame):
            self.frame = frame

        @staticmethod
        def from_pandas(frame):
            return CommitThenTimeoutDataset(frame)

        def push_to_hub(self, **kwargs):
            push_calls.append(kwargs["repo_id"])
            # Model the ambiguous window: remote commit happened, but the client
            # lost the response and raised before local archive/queue cleanup.
            remote_rows.extend(dict(item) for item in self.frame)
            raise TimeoutError("transport timeout after remote commit")

    monkeypatch.setattr(service, "load_dataset", lambda *args, **kwargs: ExistingDataset(), raising=False)
    monkeypatch.setattr(service, "pd", FakePandas(), raising=False)
    monkeypatch.setattr(service, "Dataset", CommitThenTimeoutDataset, raising=False)

    with pytest.raises(TimeoutError, match="after remote commit"):
        service.flush_queue()

    assert len(push_calls) == 1
    assert service._PENDING_FILE.exists()
    assert service._read_pending() == [row]
    assert not list(service._UPLOADED_DIR.glob("uploaded-*.jsonl"))
    conn = connect_ledger(str(ledger_paths))
    try:
        outcomes = [
            item["outcome"] for item in conn.execute(
                "SELECT outcome FROM delivery_events ORDER BY created_at, rowid"
            )
        ]
        assert outcomes == ["push_started", "push_ambiguous"]
    finally:
        conn.close()

    # A fresh baseline sees the committed row, deduplicates it, and safely
    # archives/cleans the queue without issuing a second remote write.
    result = service.flush_queue()
    assert "موجودة مسبقاً" in result
    assert len(push_calls) == 1
    assert not service._PENDING_FILE.exists()
    assert list(service._UPLOADED_DIR.glob("uploaded-*.jsonl"))
    conn = connect_ledger(str(ledger_paths))
    try:
        outcomes = [
            item["outcome"] for item in conn.execute(
                "SELECT outcome FROM delivery_events ORDER BY created_at, rowid"
            )
        ]
        assert outcomes == [
            "push_started", "push_ambiguous", "remote_present"
        ]
    finally:
        conn.close()

def test_remote_push_then_archive_failure_recovers_by_remote_dedup(ledger_paths, monkeypatch):
    import json

    row = _row(consent=True)
    row["integrity_hash"] = service._record_row_approval(row)
    service._PENDING_FILE.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(service, "HAS_HF", True)
    monkeypatch.setattr(service, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(service, "HF_TOKEN", "test-token-not-used")
    remote_hashes = set()
    remote_rows = []
    push_calls = []

    class ExistingDataset:
        column_names = ["content_hash", "integrity_hash"]

        def __len__(self):
            return len(remote_rows)

        def __getitem__(self, key):
            return [item.get(key) for item in remote_rows]

        def to_pandas(self):
            return [dict(item) for item in remote_rows]

    class FakePandas:
        @staticmethod
        def DataFrame(rows):
            return rows

        @staticmethod
        def concat(frames, ignore_index=True):
            return [item for frame in frames for item in frame]

    class SuccessfulDataset:
        def __init__(self, frame):
            self.frame = frame

        @staticmethod
        def from_pandas(frame):
            return SuccessfulDataset(frame)

        def push_to_hub(self, **kwargs):
            push_calls.append(kwargs["repo_id"])
            remote_rows.extend(dict(item) for item in self.frame)
            remote_hashes.update(item.get("content_hash", "") for item in self.frame)

    monkeypatch.setattr(service, "load_dataset", lambda *args, **kwargs: ExistingDataset(), raising=False)
    monkeypatch.setattr(service, "pd", FakePandas(), raising=False)
    monkeypatch.setattr(service, "Dataset", SuccessfulDataset, raising=False)

    with monkeypatch.context() as scoped:
        def fail_archive(rows):
            raise OSError("injected crash after remote push")
        scoped.setattr(service, "_archive_uploaded", fail_archive)
        with pytest.raises(OSError, match="injected crash after remote push"):
            service.flush_queue()

    # The remote write happened, but local cleanup did not; staged data remains.
    assert len(push_calls) == 1
    assert row["content_hash"] in remote_hashes
    assert service._PENDING_FILE.exists()
    assert service._read_pending() == [row]
    conn = connect_ledger(str(ledger_paths))
    try:
        outcomes = [
            item["outcome"] for item in conn.execute(
                "SELECT outcome FROM delivery_events ORDER BY created_at, rowid"
            )
        ]
        assert outcomes == ["push_started", "push_succeeded", "archive_failed"]
    finally:
        conn.close()

    # On restart/retry, the remote hash check deduplicates the already-pushed row
    # and allows archive/queue cleanup without a second remote push.
    result = service.flush_queue()
    assert "موجودة مسبقاً" in result
    assert len(push_calls) == 1
    assert not service._PENDING_FILE.exists()
    assert list(service._UPLOADED_DIR.glob("uploaded-*.jsonl"))
    conn = connect_ledger(str(ledger_paths))
    try:
        outcomes = [
            item["outcome"] for item in conn.execute(
                "SELECT outcome FROM delivery_events ORDER BY created_at, rowid"
            )
        ]
        assert outcomes == [
            "push_started", "push_succeeded", "archive_failed", "remote_present"
        ]
    finally:
        conn.close()


def test_remote_read_failure_aborts_before_any_push(ledger_paths, monkeypatch):
    import json

    row = _row(consent=True)
    row["integrity_hash"] = service._record_row_approval(row)
    service._PENDING_FILE.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(service, "HAS_HF", True)
    monkeypatch.setattr(service, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(service, "HF_TOKEN", "test-token-not-used")
    push_calls = []

    def failed_read(*args, **kwargs):
        raise ConnectionError("injected remote read outage")

    class NeverPushDataset:
        @staticmethod
        def from_pandas(frame):
            return NeverPushDataset()

        def push_to_hub(self, **kwargs):
            push_calls.append(kwargs)

    monkeypatch.setattr(service, "load_dataset", failed_read, raising=False)
    monkeypatch.setattr(service, "Dataset", NeverPushDataset, raising=False)

    with pytest.raises(RuntimeError, match="could not verify the existing remote dataset"):
        service.flush_queue()

    assert push_calls == []
    assert service._PENDING_FILE.exists()
    assert service._read_pending() == [row]


def test_pending_rewrite_uses_integrity_hash_not_legacy_content_hash(ledger_paths):
    import json

    first = _row(consent=True)
    first["integrity_hash"] = "sha256-category-a"
    second = dict(first)
    second["category"] = "different-category"
    second["integrity_hash"] = "sha256-category-b"
    # Legacy dedup hash is deliberately equal for these semantically distinct rows.
    service._PENDING_FILE.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in (first, second)),
        encoding="utf-8",
    )

    service._rewrite_pending_excluding([first])

    assert service._read_pending() == [second]



def test_remote_dedup_preserves_distinct_payloads_with_same_legacy_hash(ledger_paths, monkeypatch):
    import json

    first = _row(consent=True)
    first["integrity_hash"] = service._record_row_approval(first)
    second = dict(first)
    second["category"] = "different-category"
    second["entities"] = '{"medication": "different"}'
    second["integrity_hash"] = service._record_row_approval(second)
    assert first["content_hash"] == second["content_hash"]
    assert first["integrity_hash"] != second["integrity_hash"]
    service._PENDING_FILE.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in (first, second)),
        encoding="utf-8",
    )
    monkeypatch.setattr(service, "HAS_HF", True)
    monkeypatch.setattr(service, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(service, "HF_TOKEN", "test-token-not-used")
    pushed_frames = []

    class EmptyDataset:
        column_names = ["content_hash"]

        def __len__(self):
            return 0

        def __getitem__(self, key):
            return []

        def to_pandas(self):
            return []

    class FakePandas:
        @staticmethod
        def DataFrame(rows):
            return rows

        @staticmethod
        def concat(frames, ignore_index=True):
            return [item for frame in frames for item in frame]

    class CapturingDataset:
        def __init__(self, frame):
            self.frame = frame

        @staticmethod
        def from_pandas(frame):
            return CapturingDataset(frame)

        def push_to_hub(self, **kwargs):
            pushed_frames.append(self.frame)

    monkeypatch.setattr(service, "load_dataset", lambda *args, **kwargs: EmptyDataset(), raising=False)
    monkeypatch.setattr(service, "pd", FakePandas(), raising=False)
    monkeypatch.setattr(service, "Dataset", CapturingDataset, raising=False)

    service.flush_queue()

    assert len(pushed_frames) == 1
    uploaded_rows = [row for row in pushed_frames[0] if row.get("integrity_hash")]
    assert {row["integrity_hash"] for row in uploaded_rows} == {
        first["integrity_hash"], second["integrity_hash"]
    }
    assert not service._PENDING_FILE.exists()



def test_legacy_remote_hash_does_not_suppress_canonical_row(ledger_paths, monkeypatch):
    import json

    row = _row(consent=True)
    row["integrity_hash"] = service._record_row_approval(row)
    service._PENDING_FILE.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(service, "HAS_HF", True)
    monkeypatch.setattr(service, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(service, "HF_TOKEN", "test-token-not-used")
    pushed = []

    class LegacyDataset:
        column_names = ["content_hash", "category"]

        def __len__(self):
            return 1

        def __getitem__(self, key):
            return [row["content_hash"]] if key == "content_hash" else [row["category"]]

        def to_pandas(self):
            return [{"content_hash": row["content_hash"], "category": row["category"]}]

    class FakePandas:
        @staticmethod
        def DataFrame(rows):
            return rows

        @staticmethod
        def concat(frames, ignore_index=True):
            return [item for frame in frames for item in frame]

    class CapturingDataset:
        def __init__(self, frame):
            self.frame = frame

        @staticmethod
        def from_pandas(frame):
            return CapturingDataset(frame)

        def push_to_hub(self, **kwargs):
            pushed.extend(self.frame)

    monkeypatch.setattr(service, "load_dataset", lambda *args, **kwargs: LegacyDataset(), raising=False)
    monkeypatch.setattr(service, "pd", FakePandas(), raising=False)
    monkeypatch.setattr(service, "Dataset", CapturingDataset, raising=False)

    service.flush_queue()

    assert any(item.get("integrity_hash") == row["integrity_hash"] for item in pushed)



def test_queue_cleanup_preserves_unconsented_duplicate_payload(ledger_paths):
    import json

    approved = _row(consent=True)
    approved["integrity_hash"] = service._record_row_approval(approved)
    unconsented = dict(approved)
    unconsented["consent"] = False
    service._PENDING_FILE.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in (approved, unconsented)),
        encoding="utf-8",
    )

    service._rewrite_pending_excluding([approved])

    remaining = service._read_pending()
    assert remaining == [unconsented]
    assert remaining[0]["consent"] is False
