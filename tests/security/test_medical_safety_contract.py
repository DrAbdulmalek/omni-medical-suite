from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "hf-space" / "app.py").read_text(encoding="utf-8")
LAUNCHER = (ROOT / "deploy" / "gradio_launcher.py").read_text(encoding="utf-8")


def test_medical_dataset_is_private_by_default():
    assert 'HF_DATASET_PRIVATE = os.getenv("HF_DATASET_PRIVATE", "true").lower() == "true"' in APP
    assert '"private": HF_DATASET_PRIVATE' in APP


def test_medical_persistence_requires_explicit_approval_and_confidence():
    assert "def save_to_hf(" in APP
    assert 'if not approved:' in APP
    assert "Human approval is required" in APP
    assert "if confidence < MEDICAL_MIN_CONFIDENCE:" in APP
    assert "OCR confidence" in APP


def test_ui_exposes_mandatory_review_control():
    assert 'approved = gr.Checkbox(' in APP
    assert "approve this medical correction" in APP
    assert 'inputs=[corrected, raw_ocr, ner_output, category, approved, confidence]' in APP


def test_production_gradio_requires_credentials():
    assert 'if environment == "production" and (not username or not password):' in LAUNCHER
    assert 'GRADIO_USERNAME and GRADIO_PASSWORD are required' in LAUNCHER
    assert "auth=auth" in LAUNCHER
