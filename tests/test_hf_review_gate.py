"""Regression tests for the P3 human-review training-data gate."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

@pytest.fixture
def isolated_queue(tmp_path, monkeypatch):
    queue_dir = tmp_path / "queue"
    monkeypatch.setenv("OMNI_HF_QUEUE_DIR", str(queue_dir))
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    yield queue_dir
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]


def test_new_sample_is_pending_and_not_export_eligible(isolated_queue):
    from app.services.hf_dataset_service import list_review_queue, save_to_hf
    save_to_hf("correct", "ocr", {}, "medical", consent=True)
    assert list_review_queue()[0]["review_status"] == "pending"


def test_approval_requires_reviewer(isolated_queue):
    from app.services.hf_dataset_service import list_review_queue, save_to_hf, set_review_status
    save_to_hf("correct", "ocr", {}, "medical", consent=True)
    h = list_review_queue()[0]["content_hash"]
    with pytest.raises(ValueError):
        set_review_status(h, "approved")


def test_approval_records_provenance(isolated_queue):
    from app.services.hf_dataset_service import list_review_queue, save_to_hf, set_review_status
    save_to_hf("correct", "ocr", {}, "medical", consent=True)
    h = list_review_queue()[0]["content_hash"]
    assert set_review_status(h, "approved", reviewer="operator-1", dataset_version="ds-v1")
    row = list_review_queue()[0]
    assert row["review_status"] == "approved"
    assert row["reviewer"] == "operator-1"
    assert row["dataset_version"] == "ds-v1"


def test_rejection_is_never_export_eligible(isolated_queue, monkeypatch):
    import app.services.hf_dataset_service as svc
    monkeypatch.setattr(svc, "HAS_HF", True)
    monkeypatch.setattr(svc, "OMNI_HF_EXPORT_ENABLED", True)
    monkeypatch.setattr(svc, "HF_TOKEN", "test-token")
    svc.save_to_hf("correct", "ocr", {}, "medical", consent=True)
    h = svc.list_review_queue()[0]["content_hash"]
    svc.set_review_status(h, "rejected", reviewer="operator-1", reason="wrong correction", dataset_version="ds-v1")
    result = svc.flush_queue()
    assert "مؤهلة" in result or "eligible" in result.lower()
    assert svc.count_pending() == 1


def test_final_review_status_cannot_be_injected_at_save_time(isolated_queue):
    from app.services.hf_dataset_service import list_review_queue, save_to_hf
    result = save_to_hf(\"correct\", \"ocr\", {}, \"medical\", consent=True,
                        review_status=\"approved\", reviewer=\"operator-1\", dataset_version=\"ds-v1\")
    assert \"pending\" in result.lower() or \"نهائية\" in result
    assert list_review_queue() == []
