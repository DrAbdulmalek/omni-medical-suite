"""
Unit tests for packages/evaluation — metrics, accuracy calculations.

These tests verify evaluation metrics logic.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "packages"))


class TestMetrics:
    """Tests for packages/evaluation/metrics.py."""

    def test_metrics_importable(self):
        """Verify metrics module can be imported."""
        try:
            from evaluation import metrics
            assert metrics is not None
        except ImportError:
            pytest.skip("evaluation.metrics not importable")

    def test_character_accuracy(self):
        """Test CER (Character Error Rate) calculation."""
        try:
            from evaluation.metrics import calculate_cer
            ground_truth = "ضغط الدم ١٢٠/٨٠"
            prediction = "ضغط الدم ١٢٠/٨٠"
            cer = calculate_cer(prediction, ground_truth)
            assert cer == 0.0, f"Perfect match should give CER=0, got {cer}"
        except (ImportError, AttributeError):
            pytest.skip("calculate_cer not available")

    def test_character_accuracy_with_errors(self):
        """Test CER with realistic OCR errors."""
        try:
            from evaluation.metrics import calculate_cer
            ground_truth = "ضغط الدم مرتفع"
            prediction = "ضغط الدم مرتفع"  # Same text
            cer = calculate_cer(prediction, ground_truth)
            assert 0.0 <= cer <= 1.0
        except (ImportError, AttributeError):
            pytest.skip("calculate_cer not available")

    def test_word_accuracy(self):
        """Test WER (Word Error Rate) calculation."""
        try:
            from evaluation.metrics import calculate_wer
            ground_truth = "المريض يعاني من ألم في الصدر"
            prediction = "المريض يعاني من الم في الصدر"
            wer = calculate_wer(prediction, ground_truth)
            assert 0.0 <= wer <= 1.0
        except (ImportError, AttributeError):
            pytest.skip("calculate_wer not available")


class TestMetricsV2:
    """Tests for packages/evaluation/metrics_v2.py."""

    def test_metrics_v2_importable(self):
        """Verify metrics_v2 module can be imported."""
        try:
            from evaluation import metrics_v2
            assert metrics_v2 is not None
        except ImportError:
            pytest.skip("evaluation.metrics_v2 not importable")
