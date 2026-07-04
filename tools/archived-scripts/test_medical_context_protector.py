"""OmniMedical Suite v2.0 — MedicalContextProtector Tests"""

import pytest
from omnimedical_gradio_ui import MedicalContextProtector


class TestMedicalContextProtector:
    """Test suite for medical context protection (safety-critical)."""

    def test_laterality_conflict(self):
        """Test that right vs left is detected as conflict."""
        protector = MedicalContextProtector()

        chunk1 = "كسر في عظم الفخذ الأيمن"
        chunk2 = "كسر في عظم الفخذ الأيسر"

        allow, reason = protector.check_merge_safety(chunk1, chunk2)
        assert not allow
        assert "laterality" in reason.lower() or "تعارض" in reason
        assert "حرج" in reason  # High severity

    def test_fracture_type_conflict(self):
        """Test that open vs closed fracture is detected."""
        protector = MedicalContextProtector()

        chunk1 = "كسر مفتوح في عظم الفخذ"
        chunk2 = "كسر مغلق في عظم الفخذ"

        allow, reason = protector.check_merge_safety(chunk1, chunk2)
        assert not allow
        assert "fracture_type" in reason.lower() or "نوع" in reason

    def test_severity_conflict(self):
        """Test that acute vs chronic is detected."""
        protector = MedicalContextProtector()

        chunk1 = "نزيف حاد داخلي"
        chunk2 = "نزيف مزمن داخلي"

        allow, reason = protector.check_merge_safety(chunk1, chunk2)
        assert not allow
        assert "severity" in reason.lower() or "شدة" in reason

    def test_no_conflict_similar_text(self):
        """Test that similar text without medical conflicts is safe."""
        protector = MedicalContextProtector()

        chunk1 = "كسر في عظم الفخذ الأيمن"
        chunk2 = "كسر سابق في عظم الفخذ الأيمن"  # Same laterality

        allow, reason = protector.check_merge_safety(chunk1, chunk2)
        assert allow
        assert reason is None

    def test_safe_merge_with_conflicts(self, conflicting_medical_chunks):
        """Test safe_merge keeps conflicting chunks separate."""
        protector = MedicalContextProtector()
        result = protector.safe_merge(conflicting_medical_chunks)

        # Should have 4 items (none merged due to conflicts)
        assert len(result) == 4

        # Check that conflicts are recorded
        conflicted = [r for r in result if r["status"] == "protected_unique"]
        assert len(conflicted) >= 2  # At least 2 have conflicts

    def test_english_laterality_conflict(self):
        """Test English laterality detection."""
        protector = MedicalContextProtector()

        chunk1 = "fracture of the right femur"
        chunk2 = "fracture of the left femur"

        allow, reason = protector.check_merge_safety(chunk1, chunk2)
        assert not allow
        assert "laterality" in reason.lower() or "right" in reason

    def test_temporal_conflict(self):
        """Test recent vs old conflict."""
        protector = MedicalContextProtector()

        chunk1 = "نزيف حديث"
        chunk2 = "نزيف قديم"

        allow, reason = protector.check_merge_safety(chunk1, chunk2)
        assert not allow
        assert "temporal" in reason.lower() or "زمن" in reason

    def test_generate_conflict_report(self, conflicting_medical_chunks):
        """Test conflict report generation."""
        protector = MedicalContextProtector()
        merged = protector.safe_merge(conflicting_medical_chunks)
        report = protector.generate_conflict_report(merged)

        assert not report.empty
        assert "requires_doctor_review" in report.columns
        assert any(report["requires_doctor_review"])
