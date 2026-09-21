"""Wave 1.3b — HF privacy gate regression tests (RED-first by design).

Master prompt §1.3b requirements encoded here:
1. Upload to HuggingFace is DISABLED by default — flush_queue() must refuse
   (no network call) unless OMNI_HF_UPLOAD_ENABLED=1 is explicitly set.
2. De-identification happens BEFORE staging: Saudi mobile / national-ID /
   long digit runs / emails are replaced with structural tags in both the
   original and corrected texts (and entities), and the content_hash is
   computed AFTER scrubbing.
3. The auto-flush path (save_to_hf at threshold) must respect the same gate.
4. The public Space (hf-space/app_core.py) must carry the same gate marker
   and a visible privacy warning in its UI.

Values are never printed; assertions check structural tags only.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def svc_fresh(tmp_path, monkeypatch):
    """Fresh service module with isolated staging dir (fixture pattern of
    tests/test_hf_dataset_staging.py)."""
    monkeypatch.setenv("OMNI_HF_QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.delenv("OMNI_HF_UPLOAD_ENABLED", raising=False)
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    import app.services.hf_dataset_service as svc

    yield svc
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]


# ── 1. Upload disabled by default ───────────────────────────────────────────


def test_flush_disabled_by_default(svc_fresh, monkeypatch):
    svc = svc_fresh
    monkeypatch.setattr(svc, "HAS_HF", True)
    monkeypatch.setattr(
        svc, "load_dataset",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("network load_dataset must not be called while upload is disabled")),
        raising=False,  # attr may not exist when HF libs are absent
    )
    svc.save_to_hf("نص مصحح", "نص أصلي", {}, "prescription")
    assert svc.count_pending() == 1
    result = svc.flush_queue()
    assert "معطّل" in result or "DISABLED" in result.lower()
    # row must remain staged (no data loss, no upload)
    assert svc.count_pending() == 1


def test_auto_flush_blocked_when_disabled(svc_fresh, monkeypatch):
    svc = svc_fresh
    monkeypatch.setattr(svc, "HAS_HF", True)
    monkeypatch.setattr(svc, "_FLUSH_THRESHOLD", 1)
    result = svc.save_to_hf("نص", "نص", {}, "prescription")
    assert "تم رفع" not in result  # nothing was uploaded
    assert svc.count_pending() == 1


def test_flush_proceeds_when_explicitly_enabled(svc_fresh, monkeypatch):
    svc = svc_fresh
    monkeypatch.setenv("OMNI_HF_UPLOAD_ENABLED", "1")
    # re-import to pick up the env change (module-level constant)
    for mod in list(sys.modules):
        if "hf_dataset_service" in mod:
            del sys.modules[mod]
    import app.services.hf_dataset_service as svc2

    monkeypatch.setattr(svc2, "HAS_HF", True)
    # Probe the FIRST post-gate network-free step inside the lock:
    # _read_pending runs after the gate — if the gate failed we never see it.
    monkeypatch.setattr(
        svc2, "_read_pending",
        lambda: (_ for _ in ()).throw(RuntimeError("probe: past the gate")),
        raising=False,
    )
    svc2.save_to_hf("نص مصحح", "نص أصلي", {}, "prescription")
    with pytest.raises(RuntimeError, match="probe"):
        svc2.flush_queue()  # gate passed, failure comes from the probe


# ── 2. De-identification before staging ────────────────────────────────────


def test_save_scrubs_phone_nid_email(svc_fresh):
    svc = svc_fresh
    original = "المريض اتصل على 0551234567 أو +966551234567 البريد a.b@example.com هوية 1234567890 ملف 9876543"
    corrected = "تم التواصل على 0551234567 بخصوص النتيجة"
    svc.save_to_hf(corrected, original, {"phone": "0551234567"}, "prescription")
    raw = svc._PENDING_FILE.read_text(encoding="utf-8")
    for secret in ("0551234567", "966551234567", "a.b@example.com", "1234567890", "9876543"):
        assert secret not in raw, f"identifier leaked to staging: {secret}"
    assert "[PHONE]" in raw and "[EMAIL]" in raw


def test_content_hash_ignores_identifier_differences(svc_fresh):
    svc = svc_fresh
    r1 = svc.save_to_hf("نتيجة التحليل طبيعية", "نتيجة التحليل طبيعية اتصل 0551111111", {}, "lab")
    r2 = svc.save_to_hf("نتيجة التحليل طبيعية", "نتيجة التحليل طبيعية اتصل 0552222222", {}, "lab")
    h1 = r1.split("بصمة المحتوى:")[1].split()[0]
    h2 = r2.split("بصمة المحتوى:")[1].split()[0]
    assert h1 == h2, "content_hash must be computed AFTER de-identification"


# ── 3. Dataset visibility default ──────────────────────────────────────────


def test_dataset_private_by_default(svc_fresh):
    svc = svc_fresh
    assert svc._DATASET_PRIVATE is True, "medical-adjacent dataset must default to private"


# ── 4. Public Space carries the gate + warning ─────────────────────────────


def test_space_gate_markers_present():
    src = (REPO_ROOT / "hf-space" / "app_core.py").read_text(encoding="utf-8")
    assert "OMNI_HF_UPLOAD_ENABLED" in src, "Space save path lacks the explicit enable gate"
    assert "خصوصية البيانات" in src, "Space UI lacks the visible privacy warning"
