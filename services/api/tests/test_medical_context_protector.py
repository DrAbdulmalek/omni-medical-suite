#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for MedicalContextProtector — Stage 1 of OmniMedical v2.0"""

import os
os.environ["API_KEY"] = "test-key"

import pytest
from app.nlp.medical_context_protector import MedicalContextProtector


class TestMedicalContextProtector:
    """Tests for medical context protection in semantic dedup."""

    @pytest.fixture
    def protector(self):
        return MedicalContextProtector()

    def test_check_merge_safety_no_conflict(self, protector):
        """Should allow merging when no protected attributes conflict."""
        safe, reason = protector.check_merge_safety(
            "كسر في عظم الفخذ مع نزيف",
            "إصابة في عظم الفخذ الأيمن"
        )
        assert safe is True
        assert reason is None

    def test_check_merge_safety_laterality_conflict_arabic(self, protector):
        """Should block merging when laterality conflicts (Arabic)."""
        safe, reason = protector.check_merge_safety(
            "كسر في عظم الفخذ الأيمن",
            "كسر في عظم الفخذ الأيسر"
        )
        assert safe is False
        assert reason is not None
        assert "laterality" in reason

    def test_check_merge_safety_laterality_conflict_english(self, protector):
        """Should block merging when laterality conflicts (English)."""
        safe, reason = protector.check_merge_safety(
            "fracture of right femur",
            "fracture of left femur"
        )
        assert safe is False
        assert "laterality" in reason

    def test_check_merge_safety_severity_conflict(self, protector):
        """Should block merging when severity conflicts."""
        safe, reason = protector.check_merge_safety(
            "نزيف حاد في البطن",
            "نزيف مزمن في البطن"
        )
        assert safe is False
        assert "severity" in reason

    def test_check_merge_safety_fracture_type_conflict(self, protector):
        """Should block merging when fracture type conflicts."""
        safe, reason = protector.check_merge_safety(
            "كسر مفتوح في عظم العضد",
            "كسر مغلق في عظم العضد"
        )
        assert safe is False
        assert "fracture_type" in reason

    def test_check_merge_safety_temporal_conflict(self, protector):
        """Should block merging when temporal descriptors conflict."""
        safe, reason = protector.check_merge_safety(
            "نزيف حديث",
            "نزيف قديم"
        )
        assert safe is False
        assert "temporal" in reason

    def test_check_merge_safety_same_attributes_ok(self, protector):
        """Should allow merging when same attribute values."""
        safe, reason = protector.check_merge_safety(
            "كسر في عظم الفخذ الأيمن مع نزيف حاد",
            "إصابة في عظم الفخذ الأيمن مع نزيف حاد"
        )
        assert safe is True

    def test_check_merge_safety_case_insensitive(self, protector):
        """Should be case insensitive."""
        safe, reason = protector.check_merge_safety(
            "FRACTURE of RIGHT femur",
            "fracture of left femur"
        )
        assert safe is False

    def test_safe_merge_all_safe(self, protector):
        """safe_merge should mark all as safe_to_merge when no conflicts."""
        chunks = ["نزيف داخلي خفيف", "كسر في عظم الفخذ", "إصابة في الكتف"]
        result = protector.safe_merge(chunks)
        assert len(result) == 3
        assert all(item["status"] == "safe_to_merge" for item in result)

    def test_safe_merge_with_conflict(self, protector):
        """safe_merge should mark conflicting items as protected_unique."""
        chunks = [
            "كسر في عظم الفخذ الأيمن",
            "كسر في عظم الفخذ الأيسر",
            "نزيف داخلي خفيف"
        ]
        result = protector.safe_merge(chunks)
        statuses = [item["status"] for item in result]
        assert "protected_unique" in statuses
        assert "safe_to_merge" in statuses

    def test_safe_merge_preserves_all_items(self, protector):
        """safe_merge should return all input items."""
        chunks = ["أ", "ب", "ج"]
        result = protector.safe_merge(chunks)
        assert len(result) == len(chunks)

    def test_get_conflict_report(self, protector):
        """get_conflict_report should list conflicts."""
        chunks = [
            "كسر في عظم الفخذ الأيمن",
            "كسر في عظم الفخذ الأيسر",
        ]
        merged = protector.safe_merge(chunks)
        report = protector.get_conflict_report(merged)
        assert len(report) > 0
        assert report[0]["reason"] is not None

    def test_get_conflict_report_no_conflicts(self, protector):
        """get_conflict_report should return empty list when no conflicts."""
        chunks = ["نزيف داخلي", "كسر في الكتف"]
        merged = protector.safe_merge(chunks)
        report = protector.get_conflict_report(merged)
        assert len(report) == 0

    def test_is_medical_term_true(self, protector):
        """Should detect medical terms."""
        assert protector.is_medical_term("كسر مفتوح في الفخذ الأيمن")
        assert protector.is_medical_term("acute fracture of right femur")

    def test_is_medical_term_false(self, protector):
        """Should return False for non-medical text."""
        assert not protector.is_medical_term("مرحبا بالعالم")
        assert not protector.is_medical_term("hello world")

    def test_bilingual_protection(self, protector):
        """Should detect conflicts across Arabic and English."""
        safe, reason = protector.check_merge_safety(
            "fracture of right femur",
            "كسر في عظم الفخذ الأيسر"
        )
        assert safe is False
