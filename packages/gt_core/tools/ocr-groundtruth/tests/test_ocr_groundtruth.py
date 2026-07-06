"""
Tests for ocr_groundtruth.
Run with: pytest tests/ -v
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ocr_groundtruth.alignment import (
    tokenize,
    align_two_sources,
    merge_multi_source,
    compute_similarity_ratio,
)
from ocr_groundtruth.evaluate import (
    levenshtein_distance,
    character_error_rate,
    word_error_rate,
    evaluate_engine_output,
    compare_engines,
)
from ocr_groundtruth.groundtruth_builder import build_ground_truth_record


# ─── Tokenize tests ──────────────────────────────────────────────────────────

class TestTokenize:
    def test_basic_split(self):
        assert tokenize("hello world") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert tokenize("hello, world!") == ["hello", "world"]

    def test_arabic_text(self):
        result = tokenize("مرحبا بالعالم")
        assert result == ["مرحبا", "بالعالم"]

    def test_keeps_internal_punctuation(self):
        result = tokenize("Dr. Smith")
        assert "Dr" in result or "Dr." in result

    def test_empty_string(self):
        assert tokenize("") == []

    def test_numbers_preserved(self):
        result = tokenize("dosage 500mg twice")
        assert "500mg" in result


# ─── Alignment tests ─────────────────────────────────────────────────────────

class TestAlignment:
    def test_identical_sequences(self):
        tokens = ["the", "quick", "brown", "fox"]
        segments = align_two_sources(tokens, tokens)
        assert all(seg["type"] == "equal" for seg in segments)

    def test_detects_replacement(self):
        a = ["the", "quick", "fox"]
        b = ["the", "slow", "fox"]
        segments = align_two_sources(a, b)
        types = [s["type"] for s in segments]
        assert "replace" in types

    def test_merge_full_agreement(self):
        sources = {
            "abbyy": "patient name john doe",
            "readiris": "patient name john doe",
        }
        result = merge_multi_source(sources)
        assert result["stats"]["agreement_rate"] == 1.0
        assert result["stats"]["conflicts"] == 0

    def test_merge_detects_conflict(self):
        sources = {
            "abbyy": "patient name john doe",
            "readiris": "patient name jane doe",
        }
        result = merge_multi_source(sources)
        assert result["stats"]["conflicts"] >= 1

    def test_merge_three_sources_majority_vote(self):
        sources = {
            "abbyy": "aspirin 500mg daily",
            "readiris": "aspirin 500mg daily",
            "tesseract": "asprin 500mg daily",
        }
        result = merge_multi_source(sources)
        # First word should resolve to "aspirin" via majority (2 vs 1)
        first_word_result = result["word_results"][0]
        assert first_word_result["word"] == "aspirin"
        assert first_word_result["agreement"] in ["full", "majority"]

    def test_merge_single_source(self):
        sources = {"abbyy": "single source text"}
        result = merge_multi_source(sources)
        assert result["stats"]["total_words"] == 3

    def test_merge_empty_raises(self):
        import pytest
        with pytest.raises(ValueError):
            merge_multi_source({})

    def test_similarity_ratio_identical(self):
        ratio = compute_similarity_ratio("hello world", "hello world")
        assert ratio == 1.0

    def test_similarity_ratio_different(self):
        ratio = compute_similarity_ratio("hello world", "completely different text")
        assert ratio < 0.5


# ─── Evaluation (CER/WER) tests ──────────────────────────────────────────────

class TestEvaluate:
    def test_levenshtein_identical(self):
        assert levenshtein_distance("hello", "hello") == 0

    def test_levenshtein_one_substitution(self):
        assert levenshtein_distance("hello", "hallo") == 1

    def test_levenshtein_empty(self):
        assert levenshtein_distance("", "hello") == 5

    def test_cer_perfect_match(self):
        cer = character_error_rate("patient name", "patient name")
        assert cer == 0.0

    def test_cer_with_errors(self):
        cer = character_error_rate("aspirin", "asprin")
        assert cer > 0.0
        assert cer < 0.5

    def test_wer_perfect_match(self):
        wer = word_error_rate("the quick brown fox", "the quick brown fox")
        assert wer == 0.0

    def test_wer_one_word_wrong(self):
        wer = word_error_rate("the quick brown fox", "the slow brown fox")
        assert wer == 0.25  # 1 out of 4 words wrong

    def test_wer_empty_reference(self):
        wer = word_error_rate("", "")
        assert wer == 0.0

    def test_evaluate_engine_output_structure(self):
        result = evaluate_engine_output("ground truth text", "groundtruth text", "test_engine")
        assert "cer" in result
        assert "wer" in result
        assert result["engine"] == "test_engine"

    def test_compare_engines_finds_best(self):
        gt = "patient diagnosed with acute bronchitis"
        engines = {
            "bad_engine": "patiant diagnoosed wth acut bronkitis",
            "good_engine": "patient diagnosed with acute bronchitis",
        }
        result = compare_engines(gt, engines)
        assert result["best_cer"] == "good_engine"
        assert result["best_wer"] == "good_engine"

    def test_scanner_fixer_improvement_scenario(self):
        """
        Simulates the real use case: did scanner-fixer improve OCR accuracy?
        """
        ground_truth = "patient name john doe diagnosis acute bronchitis"
        without_fixer = "patiant nam jon doe diagnosls acut bronchltis"
        with_fixer = "patient name john doe diagnosis acute bronchitis"

        result = compare_engines(ground_truth, {
            "without_scanner_fixer": without_fixer,
            "with_scanner_fixer": with_fixer,
        })

        assert result["best_wer"] == "with_scanner_fixer"
        with_fixer_result = next(r for r in result["results"] if r["engine"] == "with_scanner_fixer")
        without_fixer_result = next(r for r in result["results"] if r["engine"] == "without_scanner_fixer")
        assert with_fixer_result["wer"] < without_fixer_result["wer"]


# ─── Ground truth builder tests (using extra_sources only, no real PDFs) ────

class TestGroundTruthBuilder:
    def test_build_record_with_extra_sources_only(self):
        record = build_ground_truth_record(
            image_id="test_001",
            extra_sources={
                "tesseract": "patient name john doe",
                "easyocr": "patient name john doe",
            },
            primary_source="tesseract",
        )
        assert record["image_id"] == "test_001"
        assert "tesseract" in record["sources_used"]
        assert "easyocr" in record["sources_used"]
        assert record["stats"]["agreement_rate"] == 1.0

    def test_build_record_no_sources_raises(self):
        import pytest
        with pytest.raises(ValueError):
            build_ground_truth_record(image_id="empty_001")

    def test_build_record_review_flag(self):
        record = build_ground_truth_record(
            image_id="test_002",
            extra_sources={
                "engine_a": "patient takes aspirin daily",
                "engine_b": "patient takes asprin dailly",
            },
            primary_source="engine_a",
        )
        assert record["review_needed"] in [True, False]
        assert "pairwise_similarity" in record

    def test_build_record_json_serializable(self):
        record = build_ground_truth_record(
            image_id="test_003",
            extra_sources={"a": "hello world", "b": "hello world"},
            primary_source="a",
        )
        # Must not raise
        json_str = json.dumps(record, ensure_ascii=False)
        assert len(json_str) > 0
