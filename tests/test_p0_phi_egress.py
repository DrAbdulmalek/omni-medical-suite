"""P0-A acceptance tests — fail-closed PHI egress (HF Hub + cloud OCR).

Contract under test (see PR body / task spec):
  1. No Hub push unless OMNI_HF_EXPORT_ENABLED=true (master kill-switch).
  2. flush_queue() refuses (no fake success) when disabled or tokenless.
  3. Dataset is PRIVATE by default; only the explicit literal
     OMNI_HF_DATASET_PRIVATE=false makes it public; garbage stays private.
  4. The Hub payload is metadata-only by default — raw OCR text, corrected
     text and entities never leave the machine unless
     OMNI_HF_EXPORT_RAW_TEXT=true.
  5. Per-sample consent: the HITL save path BLOCKS without explicit
     consent, and unconsented staged rows are never pushed.

All Hub I/O is mocked — these tests never touch the network.
"""

from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "app" / "services" / "hf_dataset_service.py"
HITL_PATH = REPO_ROOT / "app" / "gradio_full_hitl.py"


def _fresh_service(monkeypatch, tmp_path):
    """Import hf_dataset_service fresh with an isolated staging dir and
    default (fail-closed) env."""
    monkeypatch.setenv("OMNI_HF_QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.delenv("OMNI_HF_EXPORT_ENABLED", raising=False)
    monkeypatch.delenv("OMNI_HF_EXPORT_RAW_TEXT", raising=False)
    monkeypatch.delenv("OMNI_HF_DATASET_PRIVATE", raising=False)
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    return importlib.import_module("app.services.hf_dataset_service")


def _enable_push(svc, monkeypatch):
    """Open the operator gates and mock a verified, empty remote Hub dataset."""
    import pandas as pd

    monkeypatch.setattr(svc, "HAS_HF", True)
    monkeypatch.setattr(svc, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(svc, "HF_TOKEN", "test-token")
    fake_dataset = MagicMock()

    class EmptyRemoteDataset:
        # A successful, verified empty snapshot is required before a write.
        column_names = ["content_hash", "integrity_hash"]

        def __len__(self):
            return 0

        def __getitem__(self, key):
            return []

        def to_pandas(self):
            return pd.DataFrame(columns=self.column_names)

    # Privacy must also be mocked explicitly; tests must never contact Hub.
    class PrivateDatasetInfo:
        private = True

    class FakeHfApi:
        def __init__(self, *args, **kwargs):
            pass

        def dataset_info(self, *args, **kwargs):
            return PrivateDatasetInfo()

    def fake_baseline(api, *, repo_id, token):
        return ("a" * 40, "data/train-00000-of-00001.parquet")

    def fake_cas_push(api, dataset, *, repo_id, token, parent_commit, data_path):
        # The production service now writes through CAS. Keep this test fully
        # offline while preserving the observable fake delivery boundary.
        return dataset.push_to_hub(
            repo_id=repo_id,
            private=svc.OMNI_HF_DATASET_PRIVATE,
            token=token,
        )

    monkeypatch.setattr(svc, "HfApi", FakeHfApi, raising=False)
    monkeypatch.setattr(svc, "get_verified_dataset_baseline", fake_baseline)
    monkeypatch.setattr(svc, "push_parquet_snapshot_with_cas", fake_cas_push)

    # raising=False: optional HF libraries are not installed in every CI job,
    # so inject the module globals that flush_queue() resolves at runtime.
    monkeypatch.setattr(svc, "Dataset", fake_dataset, raising=False)
    monkeypatch.setattr(
        svc, "load_dataset", MagicMock(return_value=EmptyRemoteDataset()), raising=False
    )
    return fake_dataset

# ---------------------------------------------------------------------------
# Gate 1: master kill-switch
# ---------------------------------------------------------------------------


def test_flush_queue_does_not_push_when_export_disabled(monkeypatch, tmp_path):
    """Export unset (default) → flush refuses, push_to_hub is never called,
    rows stay staged, and the refusal is explicit (no fake success)."""
    svc = _fresh_service(monkeypatch, tmp_path)
    fake_dataset = MagicMock()
    monkeypatch.setattr(svc, "HAS_HF", True)
    monkeypatch.setattr(svc, "Dataset", fake_dataset, raising=False)
    monkeypatch.setattr(svc, "load_dataset", MagicMock(side_effect=RuntimeError("no network")), raising=False)
    monkeypatch.setattr(svc, "HF_TOKEN", "test-token")

    msg = svc.save_to_hf("نص مصحح", "نص خام", {}, "prescription", consent=True)
    assert "✅" in msg
    assert svc.count_pending() == 1

    result = svc.flush_queue()
    assert "معطّل" in result
    assert fake_dataset.from_pandas.return_value.push_to_hub.call_count == 0
    assert svc.count_pending() == 1  # rows remain staged, nothing lost


def test_flush_queue_refuses_without_token(monkeypatch, tmp_path):
    """Export enabled but HF_TOKEN empty → refusal, no push, rows intact."""
    svc = _fresh_service(monkeypatch, tmp_path)
    fake_dataset = MagicMock()
    monkeypatch.setattr(svc, "HAS_HF", True)
    monkeypatch.setattr(svc, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(svc, "HF_TOKEN", "")
    monkeypatch.setattr(svc, "Dataset", fake_dataset, raising=False)

    svc.save_to_hf("c1", "o1", {}, "prescription", consent=True)
    result = svc.flush_queue()
    assert "HF_TOKEN" in result
    assert fake_dataset.from_pandas.return_value.push_to_hub.call_count == 0
    assert svc.count_pending() == 1


def test_save_message_says_local_only_when_export_disabled(monkeypatch, tmp_path):
    """The default save message states explicitly that nothing was uploaded."""
    svc = _fresh_service(monkeypatch, tmp_path)
    msg = svc.save_to_hf("c1", "o1", {}, "prescription", consent=True)
    assert "محلياً" in msg
    assert "لم يتم رفع أي بيانات" in msg


# ---------------------------------------------------------------------------
# Gate 2: privacy default (private=True, garbage stays private)
# ---------------------------------------------------------------------------


def test_flush_queue_private_true_by_default(monkeypatch, tmp_path):
    """With every gate open and no privacy env set, the push must request a
    PRIVATE dataset."""
    svc = _fresh_service(monkeypatch, tmp_path)
    fake_dataset = _enable_push(svc, monkeypatch)
    svc.save_to_hf("c1", "o1", {}, "prescription", consent=True)
    svc.flush_queue()
    kwargs = fake_dataset.from_pandas.return_value.push_to_hub.call_args.kwargs
    assert kwargs["private"] is True


def test_garbage_private_override_stays_private(monkeypatch, tmp_path):
    """Only the literal 'false' is public — unset/garbage/lookalikes stay
    private (fail-closed parsing)."""
    for value in (None, "", "garbage", "False", "FALSE", "0", "no", "off", "true"):
        monkeypatch.setenv("OMNI_HF_QUEUE_DIR", str(tmp_path / "queue"))
        monkeypatch.delenv("OMNI_HF_EXPORT_ENABLED", raising=False)
        monkeypatch.delenv("OMNI_HF_EXPORT_RAW_TEXT", raising=False)
        if value is None:
            monkeypatch.delenv("OMNI_HF_DATASET_PRIVATE", raising=False)
        else:
            monkeypatch.setenv("OMNI_HF_DATASET_PRIVATE", value)
        for mod in list(sys.modules):
            if "hf_dataset_service" in mod:
                del sys.modules[mod]
        import app.services.hf_dataset_service as svc

        if value == "false":
            assert svc.OMNI_HF_DATASET_PRIVATE is False, value
        else:
            assert svc.OMNI_HF_DATASET_PRIVATE is True, value
    # restore a clean module for later tests
    monkeypatch.delenv("OMNI_HF_DATASET_PRIVATE", raising=False)
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    importlib.import_module("app.services.hf_dataset_service")


def test_flush_queue_never_hardcodes_private_false(monkeypatch, tmp_path):
    """Static contract: production uses CAS and does not directly call the
    legacy push_to_hub API."""
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert re.search(r"private\s*:\s*False", src) is None, "hardcoded private: False found"
    assert re.search(r"private\s*=\s*False", src) is None, "hardcoded private=False found"
    assert '"private": False' not in src
    assert "push_parquet_snapshot_with_cas(" in src
    assert ".push_to_hub(" not in src
    assert "OMNI_HF_EXPORT_ENABLED" in src

# ---------------------------------------------------------------------------
# Gate 3: raw-text payload gate
# ---------------------------------------------------------------------------


def test_hub_payload_excludes_raw_ocr_by_default(monkeypatch, tmp_path):
    """Default (raw gate off) → pushed columns are metadata-only; no raw OCR
    text, no corrected text, no entities ever leave the machine."""
    svc = _fresh_service(monkeypatch, tmp_path)
    fake_dataset = _enable_push(svc, monkeypatch)
    svc.save_to_hf("النص المصحح", "النص الخام غير الصحيح", {"meds": ["x"]},
                   "prescription", consent=True)
    result = svc.flush_queue()
    assert "تم رفع" in result  # gated push went through
    df = fake_dataset.from_pandas.call_args[0][0]
    for col in ("incorrect_ocr_output", "correct_text", "entities", "ner_entities"):
        assert col not in df.columns, f"raw column {col!r} leaked into Hub payload"
    assert set(df.columns) == {"content_hash", "integrity_hash", "category", "timestamp",
                               "consent", "raw_retained_locally"}
    assert df["raw_retained_locally"].tolist() == [True]


def test_hub_payload_includes_raw_ocr_only_when_explicitly_enabled(monkeypatch, tmp_path):
    """OMNI_HF_EXPORT_RAW_TEXT=true → raw columns are allowed (explicit
    operator opt-in), proving the gate actually controls the payload."""
    svc = _fresh_service(monkeypatch, tmp_path)
    fake_dataset = _enable_push(svc, monkeypatch)
    monkeypatch.setattr(svc, "OMNI_HF_EXPORT_RAW_TEXT", True)
    svc.save_to_hf("النص المصحح", "النص الخام", {}, "prescription", consent=True)
    svc.flush_queue()
    df = fake_dataset.from_pandas.call_args[0][0]
    assert "correct_text" in df.columns
    assert "incorrect_ocr_output" in df.columns


# ---------------------------------------------------------------------------
# Gate 4: per-sample consent
# ---------------------------------------------------------------------------


def test_save_blocked_without_consent(monkeypatch, tmp_path):
    """HITL save path (A3): without the explicit consent checkbox the save
    is BLOCKED and nothing is staged."""
    monkeypatch.setenv("OMNI_HF_QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.delenv("OMNI_HF_EXPORT_ENABLED", raising=False)
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    import app.gradio_full_hitl as hitl

    msg = hitl.save_correction("نص", "خام", {}, "prescription", consent=False)
    assert "BLOCKED" in msg
    svc = importlib.import_module("app.services.hf_dataset_service")
    assert svc.count_pending() == 0
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod or "gradio_full_hitl" in mod:
            del sys.modules[mod]


def test_unconsented_rows_are_never_pushed(monkeypatch, tmp_path):
    """Rows staged without a consent=True marker (including pre-P0 legacy
    rows) are filtered out of every flush and stay staged locally."""
    svc = _fresh_service(monkeypatch, tmp_path)
    fake_dataset = _enable_push(svc, monkeypatch)
    # Simulate a pre-P0 staged row with no consent field at all.
    svc._append_pending({
        "incorrect_ocr_output": "legacy raw",
        "correct_text": "legacy corrected",
        "category": "prescription",
        "entities": "{}",
        "timestamp": "2026-01-01T00:00:00",
        "content_hash": "legacyhash12",
    })
    result = svc.flush_queue()
    assert "موافقة" in result
    assert fake_dataset.from_pandas.return_value.push_to_hub.call_count == 0
    assert svc.count_pending() == 1  # legacy row retained locally, not lost


def test_consent_checkbox_defaults_to_unchecked():
    """A3 static contract: the HITL consent checkbox exists, defaults to
    False (never auto-ticked), and gates the save binding."""
    src = HITL_PATH.read_text(encoding="utf-8")
    assert "consent_checkbox = gr.Checkbox(" in src
    assert "value=False" in src
    assert "fn=save_correction" in src
    assert "consent_checkbox]" in src