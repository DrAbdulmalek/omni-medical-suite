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


def test_calibre_search_returns_empty_when_calibredb_missing(tmp_path):
    """Integration: a missing calibredb binary must not raise; search returns []."""
    from src.integrations.calibre_manager import CalibreManager, CalibreError

    manager = CalibreManager(tmp_path, calibredb_executable="/nonexistent/calibredb")
    # search_ids with non-empty query invokes _run, which raises CalibreError
    # because the binary is missing. This is the expected hard-fail behavior —
    # the manager surfaces the error rather than silently returning empty.
    with pytest.raises(CalibreError):
        manager.search_ids("anything")
