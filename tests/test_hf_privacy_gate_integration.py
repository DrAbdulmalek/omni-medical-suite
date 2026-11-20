"""End-to-end fail-closed tests for the HF privacy gate.

These tests use only temporary local files and mocked Hub APIs. They never
contact Hugging Face or perform a real upload.
"""
from __future__ import annotations

import json

import pytest

from app.services import hf_dataset_service as service


@pytest.mark.parametrize(
    ("visibility", "expected_error"),
    [
        (False, "private dataset required but remote dataset is public"),
        (None, "remote dataset privacy is unknown"),
        ("api-error", "remote dataset privacy could not be verified"),
    ],
)
def test_privacy_gate_blocks_before_remote_dataset_read_and_retains_rows(
    tmp_path, monkeypatch, visibility, expected_error
):
    stage = tmp_path / "stage"
    stage.mkdir()
    monkeypatch.setattr(service, "_STAGE_DIR", stage)
    monkeypatch.setattr(service, "_LEDGER_FILE", stage / "ledger.sqlite3")
    monkeypatch.setattr(service, "_PENDING_FILE", stage / "pending.jsonl")
    monkeypatch.setattr(service, "_UPLOADED_DIR", stage / "uploaded")

    row = {
        "incorrect_ocr_output": "original",
        "correct_text": "corrected",
        "category": "medical",
        "entities": "{}",
        "timestamp": "test-only",
        "content_hash": "legacy-test-hash",
        "consent": True,
    }
    row["integrity_hash"] = service._record_row_approval(row)
    service._PENDING_FILE.write_text(
        json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    class Info:
        private = visibility if isinstance(visibility, bool) else None

    class FakeHfApi:
        def __init__(self, *args, **kwargs):
            pass

        def dataset_info(self, *args, **kwargs):
            if visibility == "api-error":
                raise ConnectionError("injected metadata outage")
            return Info()

    monkeypatch.setattr(service, "HfApi", FakeHfApi)
    monkeypatch.setattr(service, "OMNI_HF_DATASET_PRIVATE", True)
    monkeypatch.setattr(service, "_dataset_private_env", None)
    monkeypatch.setattr(service, "HAS_HF", True)
    monkeypatch.setattr(service, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(service, "HF_TOKEN", "mock-token-only")

    remote_calls = []

    def unexpected_remote_read(*args, **kwargs):
        remote_calls.append(("read", args, kwargs))
        pytest.fail("privacy gate must run before load_dataset")

    class NeverPushDataset:
        @staticmethod
        def from_pandas(frame):
            return NeverPushDataset()

        def push_to_hub(self, **kwargs):
            remote_calls.append(("push", (), kwargs))
            pytest.fail("privacy gate must run before push_to_hub")

    monkeypatch.setattr(service, "load_dataset", unexpected_remote_read, raising=False)
    monkeypatch.setattr(service, "Dataset", NeverPushDataset, raising=False)

    with pytest.raises(RuntimeError, match=expected_error):
        service.flush_queue()

    assert remote_calls == []
    assert service._PENDING_FILE.exists()
    assert service._read_pending() == [row]
    assert not list(service._UPLOADED_DIR.glob("uploaded-*.jsonl"))
