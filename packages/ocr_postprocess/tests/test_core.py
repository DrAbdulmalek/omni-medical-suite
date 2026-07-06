"""Tests for medical_ocr_postprocessor.core module."""

import pytest

from medical_ocr_postprocessor.core import (
    CorrectionResult,
    CorrectionSource,
    PostProcessor,
)


class TestPostProcessorInit:
    """Test PostProcessor initialization."""

    def test_default_init(self):
        pp = PostProcessor()
        assert pp.confidence_threshold == 0.85
        assert pp.language == "ar"
        assert len(pp._medical_terms) > 0

    def test_custom_threshold(self):
        pp = PostProcessor(confidence_threshold=0.5)
        assert pp.confidence_threshold == 0.5

    def test_invalid_threshold(self):
        with pytest.raises(ValueError, match="confidence_threshold must be 0-1"):
            PostProcessor(confidence_threshold=1.5)

    def test_custom_medical_terms(self):
        terms = ["aspirin", "diabetes", "ibuprofen"]
        pp = PostProcessor(medical_terms=terms)
        assert "aspirin" in pp._medical_terms
        assert "diabetes" in pp._medical_terms

    def test_empty_medical_terms_still_has_defaults(self):
        pp = PostProcessor(medical_terms=["custom_term"])
        # Custom terms only — no defaults
        assert "custom_term" in pp._medical_terms
        assert len(pp._medical_terms) == 1


class TestArabicNormalization:
    """Test Arabic text normalization."""

    def test_normalize_alef_forms(self):
        pp = PostProcessor()
        # أ إ آ → ا
        assert pp.normalize_arabic("أحمد") == "احمد"
        assert pp.normalize_arabic("إبراهيم") == "ابراهيم"
        assert pp.normalize_arabic("آدم") == "ادم"

    def test_normalize_yaa(self):
        pp = PostProcessor()
        # ى → ي
        assert pp.normalize_arabic("مستشفى") == "مستشفي"

    def test_remove_tatweel(self):
        pp = PostProcessor()
        assert pp.normalize_arabic("عـالم") == "عالم"

    def test_remove_diacritics(self):
        pp = PostProcessor()
        text = "مَرِيضٌ"
        normalized = pp.normalize_arabic(text)
        # All diacritics removed
        assert normalized == "مريض"

    def test_normalize_whitespace(self):
        pp = PostProcessor()
        assert pp.normalize_arabic("  hello   world  ") == "hello world"

    def test_empty_string(self):
        pp = PostProcessor()
        assert pp.normalize_arabic("") == ""

    def test_mixed_arabic_english(self):
        pp = PostProcessor()
        result = pp.normalize_arabic("مريض diabetes")
        assert "diabetes" in result
        assert "مريض" in result


class TestCorrectWord:
    """Test single word correction."""

    def test_exact_medical_match(self):
        pp = PostProcessor()
        result = pp.correct_word("سكري")
        assert result.corrected == "سكري"
        assert result.medical_term_matched == "سكري"
        assert result.source == CorrectionSource.MEDICAL_DICT

    def test_arabic_normalization_applied(self):
        pp = PostProcessor()
        result = pp.correct_word("إسكري")
        # Should normalize alef
        assert "أ" not in result.corrected

    def test_empty_word(self):
        pp = PostProcessor()
        result = pp.correct_word("")
        assert result.is_modified is False

    def test_whitespace_only(self):
        pp = PostProcessor()
        result = pp.correct_word("   ")
        assert result.is_modified is False

    def test_low_confidence(self):
        pp = PostProcessor(confidence_threshold=0.95)
        result = pp.correct_word("unknownword", ocr_confidence=0.3)
        assert result.confidence < 0.95

    def test_correction_log_updated(self):
        pp = PostProcessor()
        assert len(pp.correction_log) == 0
        pp.correct_word("سكري")
        assert len(pp.correction_log) == 1

    def test_result_to_dict(self):
        pp = PostProcessor()
        result = pp.correct_word("سكري")
        d = result.to_dict()
        assert "original" in d
        assert "corrected" in d
        assert "confidence" in d
        assert "source" in d
        assert "is_modified" in d


class TestBatchCorrect:
    """Test batch word correction."""

    def test_batch_correct_basic(self):
        pp = PostProcessor()
        results = pp.batch_correct(["سكري", "ضغط", "قلب"])
        assert len(results) == 3
        assert all(isinstance(r, CorrectionResult) for r in results)

    def test_batch_with_confidences(self):
        pp = PostProcessor()
        results = pp.batch_correct(
            ["سكري", "unknown"],
            confidences=[0.9, 0.3],
        )
        assert len(results) == 2

    def test_batch_confidence_length_mismatch(self):
        pp = PostProcessor()
        with pytest.raises(ValueError, match="confidences length"):
            pp.batch_correct(["a", "b"], confidences=[0.5])


class TestValidateArabic:
    """Test Arabic text validation."""

    def test_valid_arabic(self):
        pp = PostProcessor()
        result = pp.validate_arabic("مريض يعاني من السكري")
        assert result["is_valid"] is True
        assert result["metrics"]["arabic_ratio"] > 0.5

    def test_non_arabic_text(self):
        pp = PostProcessor()
        result = pp.validate_arabic("hello world")
        # Non-Arabic text is still "valid" — just low arabic_ratio
        assert result["metrics"]["arabic_ratio"] == 0.0

    def test_empty_text(self):
        pp = PostProcessor()
        result = pp.validate_arabic("")
        assert result["metrics"]["word_count"] == 0

    def test_repeated_chars_detected(self):
        pp = PostProcessor()
        result = pp.validate_arabic("مممممريض")
        issues = result["issues"]
        repeated = [i for i in issues if i["type"] == "repeated_chars"]
        assert len(repeated) > 0

    def test_short_segments_detected(self):
        pp = PostProcessor()
        # Many single-char segments
        text = "ا ب ت ث ج ح خ"
        result = pp.validate_arabic(text)
        issues = [i for i in result["issues"] if i["type"] == "excessive_short_segments"]
        assert len(issues) > 0


class TestValidateMedicalTerms:
    """Test medical term validation."""

    def test_known_medical_terms(self):
        pp = PostProcessor()
        result = pp.validate_medical_terms("مريض سكري ضغط الدم ميتفورمين")
        assert len(result["found_terms"]) > 0
        assert "سكري" in result["found_terms"]

    def test_coverage(self):
        pp = PostProcessor()
        result = pp.validate_medical_terms("سكري ضغط قلب")
        assert result["coverage"] > 0.5

    def test_suggestions_for_misspelled(self):
        pp = PostProcessor()
        result = pp.validate_medical_terms("سكري متفورمن")
        # "متفورمن" should get a suggestion for "ميتفورمين"
        suggestions = result["suggestions"]
        matched = [s for s in suggestions if s["original"] == "متفورمن"]
        assert len(matched) > 0
        assert matched[0]["score"] >= 60

    def test_empty_text(self):
        pp = PostProcessor()
        result = pp.validate_medical_terms("")
        assert result["coverage"] == 0.0
        assert result["total_words"] == 0


class TestAddMedicalTerms:
    """Test adding custom medical terms."""

    def test_add_terms(self):
        pp = PostProcessor()
        added = pp.add_medical_terms(["term1", "term2"])
        assert added == 2
        assert "term1" in pp._medical_terms

    def test_skip_duplicates(self):
        pp = PostProcessor()
        pp.add_medical_terms(["term1"])
        added = pp.add_medical_terms(["term1", "term2"])
        assert added == 1

    def test_skip_empty_terms(self):
        pp = PostProcessor()
        added = pp.add_medical_terms(["", "  ", "term1"])
        assert added == 1


class TestStats:
    """Test session statistics."""

    def test_empty_stats(self):
        pp = PostProcessor()
        stats = pp.get_stats()
        assert stats["total_processed"] == 0
        assert stats["modification_rate"] == 0.0

    def test_stats_after_processing(self):
        pp = PostProcessor()
        pp.batch_correct(["سكري", "ضغط", "قلب"])
        stats = pp.get_stats()
        assert stats["total_processed"] == 3
        assert stats["medical_term_matches"] >= 2  # all are medical terms

    def test_clear_log(self):
        pp = PostProcessor()
        pp.correct_word("سكري")
        pp.clear_correction_log()
        assert len(pp.correction_log) == 0
