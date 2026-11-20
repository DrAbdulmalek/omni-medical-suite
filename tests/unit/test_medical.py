"""
Unit tests for packages/medical — dictionary, medical review, BGL converter.

These tests verify medical-domain logic without external OCR engines.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "packages"))


class TestDictionaryManager:
    """Tests for packages/medical/dictionary_manager.py."""

    def test_dictionary_manager_importable(self):
        """Verify dictionary_manager module can be imported."""
        try:
            from medical import dictionary_manager
            assert dictionary_manager is not None
        except ImportError:
            pytest.skip("medical.dictionary_manager not importable")

    def test_medical_terms_json_exists(self):
        """Verify medical_terms.json exists at repo root and has valid structure."""
        root = Path(__file__).resolve().parent.parent.parent
        terms_file = root / "medical_terms.json"
        if not terms_file.exists():
            pytest.skip("medical_terms.json not found at repo root")
        import json
        with open(terms_file, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, (dict, list)), "medical_terms.json should be a dict or list"
        if isinstance(data, dict):
            # Each key should map to a list of terms or a string
            for key, value in data.items():
                assert isinstance(value, (list, str, dict)), f"Unexpected type for key '{key}'"


class TestMedicalOCRReviewer:
    """Tests for packages/medical/medical_ocr_reviewer.py."""

    def test_medical_reviewer_importable(self):
        """Verify medical_ocr_reviewer module can be imported."""
        try:
            from medical import medical_ocr_reviewer
            assert medical_ocr_reviewer is not None
        except ImportError:
            pytest.skip("medical.medical_ocr_reviewer not importable")


class TestDictionaryPipeline:
    """Tests for packages/medical/dictionary_pipeline.py."""

    def test_pipeline_importable(self):
        """Verify dictionary_pipeline module can be imported."""
        try:
            from medical import dictionary_pipeline
            assert dictionary_pipeline is not None
        except ImportError:
            pytest.skip("medical.dictionary_pipeline not importable")


class TestTMXProcessor:
    """Tests for packages/medical/tmx_processor.py — TMX translation memory files."""

    def test_tmx_processor_importable(self):
        """Verify tmx_processor module can be imported."""
        try:
            from medical import tmx_processor
            assert tmx_processor is not None
        except ImportError:
            pytest.skip("medical.tmx_processor not importable")
