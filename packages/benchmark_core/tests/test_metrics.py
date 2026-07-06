"""Tests for benchmark metrics calculation."""
import pytest
from benchmarks.metrics import (
    character_error_rate,
    word_error_rate,
    medical_term_accuracy,
    calculate_all_metrics,
    normalize_text,
    normalize_arabic,
    extract_words,
    MetricsResult,
)


class TestNormalizeText:
    def test_basic_normalization(self):
        assert normalize_text("Hello  World") == "hello world"

    def test_whitespace_removal(self):
        assert normalize_text("  a  b  c  ") == "a b c"

    def test_punctuation_removal(self):
        result = normalize_text("Dr. Smith, MD!")
        assert "." not in result
        assert "," not in result
        assert "!" not in result

    def test_arabic_preservation(self):
        text = "مرحبا بالعالم"
        result = normalize_text(text)
        # Arabic chars should be preserved
        assert any("\u0600" <= c <= "\u06FF" for c in result)

    def test_empty_string(self):
        assert normalize_text("") == ""


class TestNormalizeArabic:
    def test_alef_normalization(self):
        assert "ا" in normalize_arabic("إأآا")

    def test_yaa_normalization(self):
        result = normalize_arabic("ىي")
        assert "ى" not in result

    def test_tatweel_removal(self):
        result = normalize_arabic("الـعـربـي")
        assert "\u0640" not in result

    def test_diacritics_removal(self):
        text = "قُرْآن"
        result = normalize_arabic(text)
        # Should strip diacritics
        assert len(result) < len(text)


class TestExtractWords:
    def test_english_words(self):
        words = extract_words("Hello World Test")
        assert "hello" in words
        assert "world" in words
        assert "test" in words

    def test_arabic_words(self):
        words = extract_words("مرحبا بالعالم")
        assert len(words) >= 2

    def test_mixed_words(self):
        words = extract_words("Hello مرحبا World العالم")
        assert "hello" in words
        assert "world" in words

    def test_empty(self):
        assert extract_words("") == []

    def test_numbers_preserved(self):
        words = extract_words("Patient 42 had 3 tests")
        assert "42" in words
        assert "3" in words


class TestCharacterErrorRate:
    def test_perfect_match(self):
        cer, errors, total = character_error_rate("hello world", "hello world")
        assert cer == 0.0
        assert errors == 0

    def test_all_wrong(self):
        cer, errors, total = character_error_rate("abc", "xyz")
        assert cer == 1.0
        assert errors == 3
        assert total == 3

    def test_empty_reference(self):
        cer, errors, total = character_error_rate("", "test")
        assert cer == 1.0
        assert total == 0

    def test_empty_both(self):
        cer, errors, total = character_error_rate("", "")
        assert cer == 0.0

    def test_punctuation_ignored(self):
        cer1, _, _ = character_error_rate("Dr. Smith", "Dr Smith")
        cer2, _, _ = character_error_rate("Dr. Smith", "Dr Smith")
        assert cer1 == cer2

    def test_case_insensitive(self):
        cer, _, _ = character_error_rate("Hello World", "hello world")
        assert cer == 0.0

    def test_medical_text(self):
        ref = "Patient has chest pain grade 3/10"
        hyp = "Patient has chest pain grade 3 10"
        cer, errors, total = character_error_rate(ref, hyp)
        assert cer <= 0.15


class TestWordErrorRate:
    def test_perfect_match(self):
        wer, _, _ = word_error_rate("the quick brown fox", "the quick brown fox")
        assert wer == 0.0

    def test_all_wrong(self):
        wer, _, _ = word_error_rate("hello world", "foo bar")
        assert wer == 1.0

    def test_one_substitution(self):
        wer, _, _ = word_error_rate("hello world", "hello earth")
        assert wer == pytest.approx(0.5, rel=0.01)

    def test_empty_reference(self):
        wer, _, total = word_error_rate("", "hello")
        assert wer == 1.0

    def test_medical_text(self):
        ref = "Patient presents with chest pain and dyspnea"
        hyp = "Patient presents with chest pain and shortness of breath"
        wer, _, _ = word_error_rate(ref, hyp)
        assert 0.0 <= wer <= 0.5


class TestMedicalTermAccuracy:
    def test_all_terms_found(self):
        ref = "Patient has hypertension and diabetes mellitus"
        hyp = "Patient has hypertension and diabetes mellitus"
        acc, correct, expected, found = medical_term_accuracy(ref, hyp)
        assert acc == 1.0
        assert correct == expected

    def test_some_terms_missing(self):
        ref = "Patient has hypertension and angina pectoris"
        hyp = "Patient has high blood pressure"
        acc, _, _, _ = medical_term_accuracy(ref, hyp)
        assert 0.0 <= acc < 1.0

    def test_no_medical_terms(self):
        ref = "The sky is blue today"
        hyp = "The sky is blue today"
        acc, _, expected, found = medical_term_accuracy(ref, hyp)
        assert acc == 0.0
        assert found == 0

    def test_empty_text(self):
        acc, _, _, _ = medical_term_accuracy("", "")
        assert acc == 0.0

    def test_arabic_medical_terms(self):
        ref = "المريض يعاني من ارتفاع ضغط الدم والسكري"
        hyp = "المريض يعاني من ارتفاع ضغط الدم والسكري"
        acc, correct, expected, found = medical_term_accuracy(ref, hyp)
        assert found > 0
        assert acc > 0

    def test_custom_terms(self):
        ref = "Xyzal 5mg tablet"
        hyp = "Xyzal 5mg tablet"
        custom = {"xyzal"}
        acc, correct, expected, found = medical_term_accuracy(ref, hyp, custom_terms=custom)
        assert found > 0
        assert correct > 0

    def test_fuzzy_matching(self):
        ref = "Patient has cardiomyopathy"
        hyp = "Patient has cardiomyopothy"  # slight OCR error
        acc, _, _, found = medical_term_accuracy(ref, hyp)
        assert found > 0


class TestCalculateAllMetrics:
    def test_returns_metrics_result(self):
        result = calculate_all_metrics("hello world", "hello world")
        assert isinstance(result, MetricsResult)

    def test_perfect_match_all_metrics(self):
        result = calculate_all_metrics("hypertension angina", "hypertension angina")
        assert result.cer == 0.0
        assert result.wer == 0.0
        assert result.medical_accuracy == 1.0

    def test_medical_document(self):
        ref = """
        Patient Name: John Smith
        Diagnosis: Hypertension, Type 2 Diabetes Mellitus
        Medications: Metformin 500mg, Lisinopril 10mg
        """
        hyp = """
        Patient Name: John Smith
        Diagnosis: Hypertension, Type 2 Diabetes Mellitus
        Medications: Metformin 500mg, Lisinopril 10mg
        """
        result = calculate_all_metrics(ref, hyp)
        assert result.cer == 0.0
        assert result.medical_accuracy > 0.5
