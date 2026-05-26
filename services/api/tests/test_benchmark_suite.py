#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for BenchmarkSuite — Evaluation framework for OmniMedical v2.0"""

import os
os.environ["API_KEY"] = "test-key"

import pytest
from app.evaluation.benchmark_suite import (
    BenchmarkSuite,
    BenchmarkResult,
    FusionBenchmarkCase,
    DedupBenchmarkCase,
)


class TestBenchmarkSuite:
    """Tests for the benchmark evaluation framework."""

    @pytest.fixture
    def suite(self):
        return BenchmarkSuite()

    def test_evaluate_fusion_improvement(self, suite):
        """Should detect fusion improvement over best single engine."""
        cases = [
            FusionBenchmarkCase(
                engine_outputs=[
                    {"text": "كسر في عظم فخد", "confidence": 0.75},
                    {"text": "كسر في عظم الفخذ", "confidence": 0.92},
                ],
                expected="كسر في عظم الفخذ",
                fused_output="كسر في عظم الفخذ",
            )
        ]
        results = suite.evaluate_fusion(cases)
        improvement = next(
            r for r in results if r.metric_name == "avg_fusion_improvement"
        )
        assert improvement.value >= 0

    def test_evaluate_fusion_no_improvement(self, suite):
        """Should report no improvement when fusion equals best single."""
        text = "نزيف داخلي"
        cases = [
            FusionBenchmarkCase(
                engine_outputs=[{"text": text, "confidence": 0.9}],
                expected=text,
                fused_output=text,
            )
        ]
        results = suite.evaluate_fusion(cases)
        improvement = next(
            r for r in results if r.metric_name == "avg_fusion_improvement"
        )
        assert improvement.value == 0.0

    def test_evaluate_fusion_empty_cases(self, suite):
        """Should handle empty test cases."""
        results = suite.evaluate_fusion([])
        assert len(results) == 0

    def test_evaluate_fusion_multiple_cases(self, suite):
        """Should aggregate across multiple test cases."""
        cases = [
            FusionBenchmarkCase(
                engine_outputs=[
                    {"text": "كسر في فخد", "confidence": 0.7},
                    {"text": "كسر في عظم الفخذ", "confidence": 0.9},
                ],
                expected="كسر في عظم الفخذ",
                fused_output="كسر في عظم الفخذ",
            ),
            FusionBenchmarkCase(
                engine_outputs=[
                    {"text": "نزيف خفيف", "confidence": 0.8},
                ],
                expected="نزيف داخلي خفيف",
                fused_output="نزيف داخلي خفيف",
            ),
        ]
        results = suite.evaluate_fusion(cases)
        avg_names = [
            r.metric_name for r in results if "avg_" in r.metric_name
        ]
        assert "avg_best_single_similarity" in avg_names
        assert "avg_fusion_similarity" in avg_names
        assert "avg_fusion_improvement" in avg_names

    def test_evaluate_dedup_safety_no_conflicts(self, suite):
        """Should report safety when no protected pairs are merged."""
        cases = [
            DedupBenchmarkCase(
                input_chunks=["كسر في عظم الفخذ الأيمن", "كسر في عظم الفخذ الأيسر", "نزيف خفيف"],
                deduped_output=[
                    {"text": "كسر في عظم الفخذ الأيمن"},
                    {"text": "كسر في عظم الفخذ الأيسر"},
                    {"text": "نزيف خفيف"},
                ],
                protected_pairs=[(0, 1)],
            )
        ]
        results = suite.evaluate_dedup_safety(cases)
        safety = next(
            r for r in results if r.metric_name == "total_medical_conflicts"
        )
        assert safety.value == 0
        assert safety.details["is_safe"] is True

    def test_evaluate_dedup_safety_with_conflicts(self, suite):
        """Should detect when protected pairs are incorrectly merged."""
        cases = [
            DedupBenchmarkCase(
                input_chunks=["كسر في عظم الفخذ الأيمن", "كسر في عظم الفخذ الأيسر"],
                deduped_output=[
                    {"text": "كسر في عظم الفخذ"},  # wrongfully merged
                ],
                protected_pairs=[(0, 1)],
            )
        ]
        results = suite.evaluate_dedup_safety(cases)
        protection = next(
            r for r in results if r.metric_name == "protected_preservation_rate"
        )
        assert protection.value < 1.0

    def test_evaluate_dedup_recall(self, suite):
        """Should compute information recall after dedup."""
        cases = [
            DedupBenchmarkCase(
                input_chunks=["كسر في الفخذ", "نزيف داخلي خفيف"],
                deduped_output=[
                    {"text": "كسر في الفخذ"},
                    {"text": "نزيف داخلي خفيف"},
                ],
            )
        ]
        results = suite.evaluate_dedup_safety(cases)
        recall = next(
            r for r in results if r.metric_name == "avg_recall"
        )
        assert recall.value == 1.0  # all words preserved

    def test_generate_summary_report(self, suite):
        """Should generate readable report."""
        cases = [
            FusionBenchmarkCase(
                engine_outputs=[{"text": "كسر", "confidence": 0.9}],
                expected="كسر",
                fused_output="كسر",
            )
        ]
        fusion_results = suite.evaluate_fusion(cases)
        dedup_results = suite.evaluate_dedup_safety([])
        report = suite.generate_summary_report([fusion_results, dedup_results])
        assert "Benchmark Summary Report" in report
        assert len(report) > 50

    def test_word_overlap_similarity(self, suite):
        """_word_overlap_similarity should compute Jaccard index."""
        assert suite._word_overlap_similarity("a b c", "a b c") == 1.0
        assert suite._word_overlap_similarity("a b", "c d") == 0.0
        # Jaccard: |{a,b}| / |{a,b,c,d}| = 2/4 = 0.5
        assert suite._word_overlap_similarity("a b c", "a b d") == 0.5

    def test_word_overlap_empty(self, suite):
        """Should handle empty strings."""
        assert suite._word_overlap_similarity("", "") == 1.0
        assert suite._word_overlap_similarity("a", "") == 0.0
        assert suite._word_overlap_similarity("", "a") == 0.0


class TestBenchmarkResult:
    def test_creation(self):
        r = BenchmarkResult(metric_name="test", value=0.5, details={"k": "v"})
        assert r.metric_name == "test"
        assert r.value == 0.5
        assert r.details == {"k": "v"}


class TestFusionBenchmarkCase:
    def test_creation(self):
        c = FusionBenchmarkCase(
            engine_outputs=[{"text": "a", "confidence": 0.9}],
            expected="a", fused_output="a"
        )
        assert len(c.engine_outputs) == 1


class TestDedupBenchmarkCase:
    def test_creation(self):
        c = DedupBenchmarkCase(
            input_chunks=["a", "b"],
            deduped_output=[{"text": "a"}],
            protected_pairs=[(0, 1)]
        )
        assert len(c.input_chunks) == 2
        assert c.protected_pairs == [(0, 1)]
