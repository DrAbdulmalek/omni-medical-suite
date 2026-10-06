from src.ocr.ensemble import OCREnsemble


def test_confidence_weighted_text_refuses_uncalibrated_cross_engine_scores(monkeypatch):
    obj = OCREnsemble.__new__(OCREnsemble)
    monkeypatch.setattr(obj, "run_all", lambda image: {
        "results": {
            "tesseract": {"text": "A", "lines": [{"confidence": 0.99}]},
            "surya": {"text": "B", "lines": [{"confidence": 0.80}]},
        },
        "num_engines": 2,
        "engines_used": ["tesseract", "surya"],
    })
    assert obj.get_confidence_weighted_text(object()) == ""


def test_confidence_weighted_text_requires_same_calibration(monkeypatch):
    obj = OCREnsemble.__new__(OCREnsemble)
    monkeypatch.setattr(obj, "run_all", lambda image: {
        "results": {
            "tesseract": {"text": "A", "confidence_scale": "probability", "calibration_version": "v1", "lines": [{"confidence": 0.99}]},
            "surya": {"text": "B", "confidence_scale": "probability", "calibration_version": "v2", "lines": [{"confidence": 0.80}]},
        },
        "num_engines": 2,
        "engines_used": ["tesseract", "surya"],
    })
    assert obj.get_confidence_weighted_text(object()) == ""


def test_confidence_weighted_text_uses_calibrated_scores(monkeypatch):
    obj = OCREnsemble.__new__(OCREnsemble)
    monkeypatch.setattr(obj, "run_all", lambda image: {
        "results": {
            "tesseract": {"text": "A", "confidence_scale": "probability", "calibration_version": "v1", "lines": [{"confidence": 0.79}]},
            "surya": {"text": "B", "confidence_scale": "probability", "calibration_version": "v1", "lines": [{"confidence": 0.91}]},
        },
        "num_engines": 2,
        "engines_used": ["tesseract", "surya"],
    })
    assert obj.get_confidence_weighted_text(object()) == "B"
