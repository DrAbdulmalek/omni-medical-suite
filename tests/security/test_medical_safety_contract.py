from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "hf-space" / "app.py").read_text(encoding="utf-8")
APP_CORE = (ROOT / "hf-space" / "app_core.py").read_text(encoding="utf-8")
LAUNCHER = (ROOT / "deploy" / "gradio_launcher.py").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "deploy" / "Dockerfile.gradio").read_text(encoding="utf-8")


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
    assert 'if environment == "production" and (not username or not password):' in LAUNCHER
    assert 'GRADIO_USERNAME and GRADIO_PASSWORD are required' in LAUNCHER
    assert "auth=auth" in LAUNCHER


def test_paddle_confidence_is_normalized_to_percent_at_production_boundary():
    assert 'APP_PATH = Path(__file__).resolve().parents[1] / "hf-space" / "app_core.py"' in LAUNCHER
    assert "_original_run_paddle_ocr = module._run_paddle_ocr" in LAUNCHER
    assert "def _run_paddle_ocr_percent(image):" in LAUNCHER
    assert "value *= 100.0" in LAUNCHER
    assert '"confidence": round(value, 2)' in LAUNCHER


def test_direct_gradio_app_execution_is_blocked():
    assert 'if __name__ == "__main__":' in APP
    assert "Direct execution of hf-space/app.py is disabled." in APP
    assert "deploy/gradio_launcher.py" in APP
    assert "demo.launch(" not in APP


def test_production_image_uses_authenticated_launcher_not_app_directly():
    assert 'CMD ["python", "deploy/gradio_launcher.py"]' in DOCKERFILE
    assert 'CMD ["python", "hf-space/app.py"]' not in DOCKERFILE
