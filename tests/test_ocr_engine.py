# tests/test_ocr_engine.py
"""Unit tests for src.processors.ocr_engine.MedicalOCREngine."""
import numpy as np

from src.processors.ocr_engine import MedicalOCREngine


def test_easyocr_priority(monkeypatch):
    """If EasyOCR returns text, Tesseract must NOT be called."""
    engine = MedicalOCREngine(use_easyocr=True)
    monkeypatch.setattr(
        engine,
        "_extract_with_easyocr",
        lambda image: "easyocr text",
    )
    monkeypatch.setattr(
        engine,
        "_extract_with_tesseract",
        lambda image: (_ for _ in ()).throw(Exception("should not be called")),
    )
    image = np.zeros((50, 50), dtype=np.uint8)
    assert engine.extract_text(image) == "easyocr text"


def test_fallback_to_tesseract(monkeypatch):
    """If EasyOCR raises, the engine must fall back to Tesseract."""
    engine = MedicalOCREngine(use_easyocr=True)
    monkeypatch.setattr(
        engine,
        "_extract_with_easyocr",
        lambda image: (_ for _ in ()).throw(Exception("easyocr failed")),
    )
    monkeypatch.setattr(
        engine,
        "_extract_with_tesseract",
        lambda image: "fallback text",
    )
    image = np.zeros((50, 50), dtype=np.uint8)
    assert engine.extract_text(image) == "fallback text"


def test_empty_easyocr_result_falls_back(monkeypatch):
    """If EasyOCR returns an empty string, the engine must fall back to Tesseract."""
    engine = MedicalOCREngine(use_easyocr=True)
    monkeypatch.setattr(
        engine,
        "_extract_with_easyocr",
        lambda image: "",
    )
    monkeypatch.setattr(
        engine,
        "_extract_with_tesseract",
        lambda image: "fallback text",
    )
    image = np.zeros((50, 50), dtype=np.uint8)
    assert engine.extract_text(image) == "fallback text"


def test_tesseract_only_when_easyocr_disabled(monkeypatch):
    """When use_easyocr=False, _extract_with_easyocr must never be called."""
    engine = MedicalOCREngine(use_easyocr=False)
    monkeypatch.setattr(
        engine,
        "_extract_with_easyocr",
        lambda image: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    monkeypatch.setattr(
        engine,
        "_extract_with_tesseract",
        lambda image: "tesseract text",
    )
    image = np.zeros((50, 50), dtype=np.uint8)
    assert engine.extract_text(image) == "tesseract text"


def test_easyocr_download_disabled_by_default():
    engine = MedicalOCREngine()
    assert engine.allow_easyocr_download is False

def test_easyocr_model_directory_configuration():
    engine = MedicalOCREngine(easyocr_model_storage_directory='/models', allow_easyocr_download=False)
    assert engine.easyocr_model_storage_directory == '/models'
    assert engine.allow_easyocr_download is False
