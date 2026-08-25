"""Behavioral regression tests for medical OCR token safety."""

from pathlib import Path


def test_production_ocr_source_has_no_trailing_space_keys():
    source = Path("hf-space/app_core.py").read_text(encoding="utf-8")
    assert '"ترامادول ": "ترامادول"' not in source
    assert '"ديكلوفيناك ": "ديكلوفيناك"' not in source


def test_production_ocr_source_uses_boundary_safe_replacement():
    source = Path("hf-space/app_core.py").read_text(encoding="utf-8")
    assert "re.finditer(pattern, corrected)" in source
    assert "re.sub(pattern, right, corrected)" in source
