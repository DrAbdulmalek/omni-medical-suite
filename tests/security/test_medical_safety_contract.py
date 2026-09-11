from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "hf-space" / "app.py").read_text(encoding="utf-8")
APP_CORE = (ROOT / "hf-space" / "app_core.py").read_text(encoding="utf-8")
LAUNCHER = (ROOT / "deploy" / "gradio_launcher.py").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "deploy" / "Dockerfile.gradio").read_text(encoding="utf-8")

# P0 split-brain guards: the PRODUCTION modules (not just the HF Space twin)
HF_SERVICE = (ROOT / "app" / "services" / "hf_dataset_service.py").read_text(encoding="utf-8")
HITL = (ROOT / "app" / "gradio_full_hitl.py").read_text(encoding="utf-8")
MOBILE_SERVER = (ROOT / "packages" / "core" / "mobile" / "server.py").read_text(encoding="utf-8")
REVIEW_SERVICE = (ROOT / "app" / "services" / "review_service.py").read_text(encoding="utf-8")
API_SERVER = (ROOT / "packages" / "core" / "api_server.py").read_text(encoding="utf-8")
OCR_ADAPTER = (ROOT / "packages" / "omni_ocr" / "adapter.py").read_text(encoding="utf-8")


def test_medical_dataset_is_private_by_default():
    assert 'HF_DATASET_PRIVATE = os.getenv("HF_DATASET_PRIVATE", "true").lower() == "true"' in APP_CORE
    assert '"private": HF_DATASET_PRIVATE' in APP_CORE


def test_medical_persistence_requires_explicit_approval_and_confidence():
    assert "def save_to_hf(" in APP_CORE
    assert 'if not approved:' in APP_CORE
    assert "Human approval is required" in APP_CORE
    assert "if confidence < MEDICAL_MIN_CONFIDENCE:" in APP_CORE
    assert "OCR confidence" in APP_CORE


def test_ui_exposes_mandatory_review_control():
    assert 'approved = gr.Checkbox(' in APP_CORE
    assert "approve this medical correction" in APP_CORE
    assert 'inputs=[corrected, raw_ocr, ner_output, category, approved, confidence]' in APP_CORE


def test_production_gradio_requires_credentials():
    assert 'if environment == "production" and (not username or not password):' in APP
    assert 'GRADIO_USERNAME and GRADIO_PASSWORD are required' in APP
    assert "auth=auth" in APP
    assert 'module.launch_production()' in LAUNCHER


def test_paddle_confidence_is_normalized_to_percent_at_production_boundary():
    assert "def install_production_confidence_contract()" in APP
    assert "def _run_paddle_ocr_percent(image):" in APP
    assert "value *= 100.0" in APP
    assert '"confidence": round(value, 2)' in APP
    assert "install_production_confidence_contract()" in APP
    assert "launch_production()" in APP


def test_direct_gradio_app_execution_uses_the_authenticated_production_contract():
    assert 'if __name__ == "__main__":' in APP
    assert "launch_production()" in APP
    assert "Direct execution of hf-space/app.py is disabled." not in APP
    assert "demo.launch(" in APP


def test_production_image_uses_authenticated_launcher_not_app_directly():
    assert 'CMD ["python", "deploy/gradio_launcher.py"]' in DOCKERFILE
    assert 'CMD ["python", "hf-space/app.py"]' not in DOCKERFILE
    assert "module.launch_production()" in LAUNCHER


# ---------------------------------------------------------------------------
# P0-A: fail-closed PHI egress — production modules (split-brain guard).
# The 2B regression: safety contracts only covered hf-space while the
# production hf_dataset_service hardcodes public pushes. These tests make
# the split-brain impossible to reintroduce silently.
# ---------------------------------------------------------------------------


def test_production_hf_service_is_fail_closed():
    import re

    assert re.search(r"private\s*:\s*False", HF_SERVICE) is None, (
        "production hf_dataset_service must never hardcode a public dataset"
    )
    assert HF_SERVICE.count("push_to_hub") == 1, "single gated push_to_hub only"
    assert 'OMNI_HF_EXPORT_ENABLED = _env_flag("OMNI_HF_EXPORT_ENABLED", False)' in HF_SERVICE
    assert 'OMNI_HF_DATASET_PRIVATE' in HF_SERVICE
    assert 'OMNI_HF_EXPORT_RAW_TEXT = _env_flag("OMNI_HF_EXPORT_RAW_TEXT", False)' in HF_SERVICE
    assert "raw_retained_locally" in HF_SERVICE
    assert 'consent' in HF_SERVICE


def test_production_hf_service_refuses_flush_when_disabled():
    assert "if not OMNI_HF_EXPORT_ENABLED:" in HF_SERVICE
    assert "معطّل" in HF_SERVICE
    assert "if not HF_TOKEN:" in HF_SERVICE


def test_hitl_save_requires_explicit_consent():
    assert "consent_checkbox = gr.Checkbox(" in HITL
    assert "value=False" in HITL
    assert "fn=save_correction" in HITL
    assert "consent_checkbox]" in HITL
    assert "BLOCKED" in HITL


def test_hf_space_export_is_kill_switched():
    assert "OMNI_HF_EXPORT_ENABLED" in APP_CORE
    assert "if not OMNI_HF_EXPORT_ENABLED:" in APP_CORE
    assert "raw_retained_locally" in APP_CORE
    # approved + confidence gates preserved (existing behavior kept intact)
    assert 'if not approved:' in APP_CORE
    assert "if confidence < MEDICAL_MIN_CONFIDENCE:" in APP_CORE


def test_cloud_ocr_denied_by_default():
    assert 'OMNI_ALLOW_CLOUD_OCR' in API_SERVER
    assert "403" in API_SERVER
    # 3 gated endpoints (8-space indent = call sites; the def line has "-> None")
    assert API_SERVER.count("\n        _cloud_ocr_gate()") == 3, "all three /mistral/* endpoints gated"
    assert "_cloud_ocr_allowed" in OCR_ADAPTER
    assert "OMNI_ALLOW_CLOUD_OCR" in OCR_ADAPTER


# ---------------------------------------------------------------------------
# P0-B: fail-visible OCR + single canonical correction (split-brain guard)
# ---------------------------------------------------------------------------


def test_production_paths_have_no_second_correct_text():
    # The canonical correction lives in _auto_correct_ocr (one real call per
    # file that owns a copy of the canonical logic). The lowercase pattern
    # matches real calls only — never docstring mentions of the class method.
    assert MOBILE_SERVER.count(".correct_text(") == 0
    assert REVIEW_SERVICE.count(".correct_text(") == 0
    OCR_SERVICE = (ROOT / "app" / "services" / "ocr_service.py").read_text(encoding="utf-8")
    assert OCR_SERVICE.count("checker.correct_text(") == 1
    assert APP_CORE.count("checker.correct_text(") == 1


def test_production_engines_return_fail_visible_status():
    assert 'ENGINE_STATUS_ERROR' in (ROOT / "app" / "services" / "ocr_service.py").read_text(encoding="utf-8")
    assert '"selected_engine"' in HITL
    assert '"user_visible_error"' in HITL
    assert '"fallback_used"' in HITL
    assert '"ocr_status"' in MOBILE_SERVER
