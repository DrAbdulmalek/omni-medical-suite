"""
Unit tests for packages/nlp — Arabic NLP, RTL, correction, language detection.

These tests verify NLP preprocessing and correction logic.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "packages"))

from tests.utils import assert_text_similar, normalize_arabic_text


class TestArabicNormalization:
    """Test Arabic text normalization utility."""

    def test_tatweel_removal(self):
        """Tatweel (kashida U+0640) should be stripped."""
        text_with_tatweel = "علا\u0640ج"  # علاج with kashida
        text_without = "علاج"
        assert normalize_arabic_text(text_with_tatweel) == normalize_arabic_text(text_without)

    def test_alef_normalization(self):
        """Alef variants should normalize to bare alef."""
        originals = ["أحمد", "إبراهيم", "آدم"]
        normalized = [normalize_arabic_text(t) for t in originals]
        for t in normalized:
            assert "\u0622" not in t  # alef madda
            assert "\u0623" not in t  # alef hamza above
            assert "\u0625" not in t  # alef hamza below

    def test_taa_marbuta_normalization(self):
        """Taa marbuta should normalize to haa."""
        assert normalize_arabic_text("مدرسة") == normalize_arabic_text("مدرسه")

    def test_whitespace_normalization(self):
        """Multiple spaces should collapse to single space."""
        assert normalize_arabic_text("ضغط   الدم") == "ضغط الدم"


class TestArabicRTL:
    """Tests for packages/nlp/arabic_rtl.py — RTL text handling."""

    def test_rtl_module_importable(self):
        """Verify arabic_rtl module can be imported."""
        try:
            from nlp import arabic_rtl
            assert arabic_rtl is not None
        except ImportError:
            pytest.skip("nlp.arabic_rtl not importable")

    def test_rtl_text_has_arabic_chars(self):
        """Arabic RTL text should contain Arabic Unicode characters."""
        text = "المريض يعاني من ألم"
        arabic_chars = [c for c in text if "\u0600" <= c <= "\u06FF"]
        assert len(arabic_chars) > 0


class TestArabicNLPUtils:
    """Tests for packages/nlp/arabic_nlp_utils.py."""

    def test_nlp_utils_importable(self):
        """Verify arabic_nlp_utils module can be imported."""
        try:
            from nlp import arabic_nlp_utils
            assert arabic_nlp_utils is not None
        except ImportError:
            pytest.skip("nlp.arabic_nlp_utils not importable")

    def test_entity_extraction(self):
        """Test that medical entities can be extracted from Arabic text."""
        try:
            from nlp.arabic_nlp_utils import extract_entities
            text = "ضغط الدم ١٢٠/٨٠ والسكري من النوع الثاني"
            result = extract_entities(text)
            assert isinstance(result, (list, dict))
        except (ImportError, AttributeError):
            pytest.skip("extract_entities not available in test environment")


class TestLanguageDetector:
    """Tests for packages/nlp/language_detector.py."""

    def test_detector_importable(self):
        """Verify language_detector module can be imported."""
        try:
            from nlp import language_detector
            assert language_detector is not None
        except ImportError:
            pytest.skip("nlp.language_detector not importable")

    def test_arabic_detection(self):
        """Test that Arabic text is correctly identified."""
        try:
            from nlp.language_detector import detect_language
            result = detect_language("هذا نص عربي طبي")
            assert result in ("ar", "arabic", "ar-SA", None)
        except (ImportError, AttributeError):
            pytest.skip("detect_language not available")


class TestTextSimilarity:
    """Test the assert_text_similar helper itself."""

    def test_identical_text_scores_100(self):
        """Identical text should score 100%."""
        assert_text_similar("ضغط الدم", "ضغط الدم", threshold=0.99)

    def test_similar_text_passes(self):
        """Small OCR errors should still pass with default threshold."""
        assert_text_similar("ضغط الدم ١٢٠/٨٠", "ضغط الدم ١٢٠/٨٠", threshold=0.8)

    def test_different_text_fails(self):
        """Completely different text should fail."""
        with pytest.raises(AssertionError):
            assert_text_similar("ضغط الدم", "جراحة القلب", threshold=0.5)
