# tests/test_ocr_tuner.py
"""Unit tests for src.ml.ocr_tuner.OCRTuner."""
import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from pathlib import Path  # noqa: E402

from src.ml.ocr_tuner import OCRTuner  # noqa: E402


def _write_synthetic_image(path: Path) -> None:
    """Write a small grayscale image to disk so OCRTuner can imread it."""
    image = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    cv2.imwrite(str(path), image)


def test_tuner_rejects_missing_image(tmp_path):
    missing = tmp_path / "missing.png"
    with pytest.raises(ValueError):
        OCRTuner(missing)


def test_tuner_constructs_with_valid_image(tmp_path):
    path = tmp_path / "synthetic.png"
    _write_synthetic_image(path)
    tuner = OCRTuner(path)
    assert tuner.original.shape == (100, 100)


def test_apply_params_returns_binary_image(tmp_path):
    path = tmp_path / "synthetic.png"
    _write_synthetic_image(path)
    tuner = OCRTuner(path)
    img = tuner._apply_params(
        {
            "clip_limit": 2.5,
            "block_size": 21,
            "constant": 5,
            "denoise_h": 10,
        }
    )
    assert img.shape == (100, 100)
    assert set(np.unique(img).tolist()).issubset({0, 255})


def test_score_text_with_ground_truth():
    path = None  # not used; we test _score_text directly
    # Bypass __init__ to avoid needing an image.
    tuner = OCRTuner.__new__(OCRTuner)
    tuner.ground_truth = "patient 12345 diabetes"
    score = tuner._score_text("patient diabetes")
    # 2 of 3 ground words matched
    assert 0.0 < score <= 1.0


def test_score_text_without_ground_truth():
    tuner = OCRTuner.__new__(OCRTuner)
    tuner.ground_truth = None
    # 25 words → 25/50 = 0.5
    text = " ".join(["word"] * 25)
    score = tuner._score_text(text)
    assert score == 0.5


def test_get_optimized_image_raises_before_tune(tmp_path):
    path = tmp_path / "synthetic.png"
    _write_synthetic_image(path)
    tuner = OCRTuner(path)
    with pytest.raises(RuntimeError):
        tuner.get_optimized_image()


def test_tune_returns_dict_of_params(tmp_path, monkeypatch):
    """tune() should call _evaluate for each combination and return a dict."""
    path = tmp_path / "synthetic.png"
    _write_synthetic_image(path)
    tuner = OCRTuner(path)

    # Stub _evaluate to return a deterministic score that depends on
    # denoise_h, so we can verify the best one is selected.
    def fake_evaluate(params):
        return float(params["denoise_h"])  # higher denoise_h → higher score

    monkeypatch.setattr(tuner, "_evaluate", fake_evaluate)
    best = tuner.tune(max_trials=12)
    assert isinstance(best, dict)
    assert set(best.keys()) == {"clip_limit", "block_size", "constant", "denoise_h"}
    # The grid's highest denoise_h is 20, so best must have denoise_h == 20.
    assert best["denoise_h"] == 20
