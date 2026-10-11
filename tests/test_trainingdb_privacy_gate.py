"""Unit tests for the fail-closed per-sample training-data privacy gate."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "trainingdb_sync.py"
SPEC = importlib.util.spec_from_file_location("trainingdb_sync", SCRIPT)
trainingdb_sync = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(trainingdb_sync)


def _write_manifest(tmp_path, records):
    manifest = tmp_path / "slices.jsonl"
    manifest.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return manifest


def _approved_record():
    return {
        "id": "slice-001",
        "source": {"human_reviewed": True},
        "privacy_review": {
            "approved": True,
            "deidentified": True,
            "consent_confirmed": True,
            "reviewer": "reviewer-id",
            "reviewed_at": 1791720000,
        },
    }


def test_privacy_gate_rejects_legacy_batch_review_without_per_sample_approval(tmp_path):
    _write_manifest(tmp_path, [{"id": "legacy", "source": {"human_reviewed": True}}])

    errors = trainingdb_sync.validate_privacy_approvals(str(tmp_path))

    assert any("missing per-sample privacy_review" in error for error in errors)


def test_privacy_gate_accepts_explicit_complete_per_sample_review(tmp_path):
    _write_manifest(tmp_path, [_approved_record()])

    assert trainingdb_sync.validate_privacy_approvals(str(tmp_path)) == []


def test_privacy_gate_rejects_unconfirmed_consent_and_missing_reviewer(tmp_path):
    record = _approved_record()
    record["privacy_review"]["consent_confirmed"] = False
    record["privacy_review"]["reviewer"] = ""
    _write_manifest(tmp_path, [record])

    errors = trainingdb_sync.validate_privacy_approvals(str(tmp_path))

    assert any("consent not confirmed" in error for error in errors)
    assert any("reviewer identity missing" in error for error in errors)


def test_privacy_gate_rejects_malformed_manifest_line(tmp_path):
    (tmp_path / "slices.jsonl").write_text("{broken json}\n", encoding="utf-8")

    errors = trainingdb_sync.validate_privacy_approvals(str(tmp_path))

    assert any("malformed JSON" in error for error in errors)


def test_privacy_gate_rejects_missing_manifest(tmp_path):
    assert trainingdb_sync.validate_privacy_approvals(str(tmp_path)) == [
        "missing slices.jsonl manifest"
    ]

def test_privacy_gate_accepts_review_ledger_entry_for_exact_sample_id(tmp_path):
    _write_manifest(tmp_path, [{"id": "slice-001", "source": {"human_reviewed": True}}])
    review = _approved_record()["privacy_review"] | {"sample_id": "slice-001"}
    (tmp_path / "privacy_reviews.jsonl").write_text(
        json.dumps(review) + "\n", encoding="utf-8"
    )

    assert trainingdb_sync.validate_privacy_approvals(str(tmp_path)) == []


def test_latest_review_ledger_entry_can_revoke_prior_approval(tmp_path):
    _write_manifest(tmp_path, [{"id": "slice-001"}])
    approved = _approved_record()["privacy_review"] | {"sample_id": "slice-001"}
    revoked = dict(approved, approved=False, reviewed_at=1791720001)
    (tmp_path / "privacy_reviews.jsonl").write_text(
        json.dumps(approved) + "\n" + json.dumps(revoked) + "\n",
        encoding="utf-8",
    )

    errors = trainingdb_sync.validate_privacy_approvals(str(tmp_path))

    assert any("sample not explicitly approved" in error for error in errors)
