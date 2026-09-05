# tests/test_integration_ocr_calibre.py
"""Integration tests for the OCR + Calibre flow.

These tests do NOT require Calibre or Tesseract to be installed — they
stub the I/O surfaces and exercise only the orchestration logic.
"""
import numpy as np
import pytest

from src.processors.ocr_engine import MedicalOCREngine


def test_ocr_engine_returns_string(monkeypatch):
    engine = MedicalOCREngine(use_easyocr=False)
    monkeypatch.setattr(
        engine,
        "_extract_with_tesseract",
        lambda image: "patient: 12345",
    )
    image = np.zeros((100, 100), dtype=np.uint8)
    text = engine.extract_text(image)
    assert isinstance(text, str)
    assert "patient" in text
    assert "12345" in text


def test_ocr_engine_returns_empty_string_when_no_text(monkeypatch):
    engine = MedicalOCREngine(use_easyocr=False)
    monkeypatch.setattr(
        engine,
        "_extract_with_tesseract",
        lambda image: "",
    )
    image = np.zeros((100, 100), dtype=np.uint8)
    text = engine.extract_text(image)
    assert text == ""


def test_ocr_engine_easyocr_then_tesseract_fallback(monkeypatch):
    """If EasyOCR returns an empty string, Tesseract is consulted next."""
    call_log: list[str] = []

    engine = MedicalOCREngine(use_easyocr=True)

    def easy(image):
        call_log.append("easyocr")
        return ""

    def tess(image):
        call_log.append("tesseract")
        return "fallback"

    monkeypatch.setattr(engine, "_extract_with_easyocr", easy)
    monkeypatch.setattr(engine, "_extract_with_tesseract", tess)

    image = np.zeros((50, 50), dtype=np.uint8)
    text = engine.extract_text(image)
    assert text == "fallback"
    assert call_log == ["easyocr", "tesseract"]


def test_calibre_search_fails_closed_when_calibredb_missing(tmp_path):
    """A missing Calibre binary must raise rather than silently return []."""
    from src.integrations.calibre_manager import CalibreManager, CalibreError

    manager = CalibreManager(tmp_path, calibredb_executable="/nonexistent/calibredb")
    with pytest.raises(CalibreError):
        manager._search_ids("anything")
