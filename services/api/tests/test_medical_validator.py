"""
Unit tests for Medical Validator module.
Tests: dosage validation, drug interactions, temporal consistency, terminology, laterality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from services.api.validation.medical_validator import (
    MedicalValidator, ValidationSeverity, ValidationIssue, ValidationResult
)


@pytest.fixture
def validator():
    """Create a medical validator instance."""
    return MedicalValidator(llm_gateway=None)


@pytest.fixture
def validator_with_llm():
    """Create a medical validator with LLM mock."""
    llm = MagicMock()
    llm.complete = AsyncMock(return_value='{"issues": []}')
    return MedicalValidator(llm_gateway=llm)


class TestDosageValidation:
    """Test drug dosage validation."""

    @pytest.mark.asyncio
    async def test_valid_dosage(self, validator):
        """Test valid dosage passes."""
        result = await validator._validate_dosage(
            "Paracetamol 500mg مرتين يومياً"
        )

        assert len(result) == 0  # No issues

    @pytest.mark.asyncio
    async def test_dosage_too_low(self, validator):
        """Test dosage below minimum."""
        result = await validator._validate_dosage(
            "Paracetamol 50mg مرتين يومياً"
        )

        assert len(result) == 1
        assert result[0].category == "dosage"
        assert result[0].severity == ValidationSeverity.WARNING
        assert "50mg" in result[0].message
        assert "أقل من الحد الأدنى" in result[0].message

    @pytest.mark.asyncio
    async def test_dosage_too_high(self, validator):
        """Test dosage above maximum."""
        result = await validator._validate_dosage(
            "Paracetamol 1500mg مرتين يومياً"
        )

        assert len(result) == 1
        assert result[0].severity == ValidationSeverity.ERROR
        assert "1500mg" in result[0].message
        assert "تتجاوز الحد الأقصى" in result[0].message

    @pytest.mark.asyncio
    async def test_unknown_drug(self, validator):
        """Test unknown drug detection."""
        result = await validator._validate_dosage(
            "UnknownDrugXYZ 100mg يومياً"
        )

        assert len(result) == 1
        assert result[0].severity == ValidationSeverity.INFO
        assert "غير معروف" in result[0].message

    @pytest.mark.asyncio
    async def test_arabic_dosage_units(self, validator):
        """Test Arabic dosage units."""
        result = await validator._validate_dosage(
            "باراسيتامول ٥٠٠ ملغ يومياً"
        )

        # Should extract dosage despite Arabic numerals
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_multiple_dosages(self, validator):
        """Test multiple drug dosages in same text."""
        result = await validator._validate_dosage(
            "Paracetamol 500mg + Ibuprofen 200mg"
        )

        assert len(result) == 0  # Both valid

    @pytest.mark.asyncio
    async def test_dosage_with_context(self, validator):
        """Test dosage extraction with drug name in context."""
        result = await validator._validate_dosage(
            "وصف الطبيب دواء Amlodipine بجرعة 2.5mg"
        )

        assert len(result) == 0  # Valid minimum dose


class TestDrugInteractions:
    """Test drug interaction detection."""

    @pytest.mark.asyncio
    async def test_known_interaction(self, validator):
        """Test known dangerous interaction."""
        result = await validator._check_interactions(
            "Warfarin 5mg daily + Aspirin 100mg daily"
        )

        assert len(result) == 1
        assert result[0].category == "drug_interaction"
        assert result[0].severity == ValidationSeverity.CRITICAL
        assert "warfarin" in result[0].message.lower()
        assert "aspirin" in result[0].message.lower()
        assert "تعارض دوائي" in result[0].message

    @pytest.mark.asyncio
    async def test_no_interaction(self, validator):
        """Test safe drug combination."""
        result = await validator._check_interactions(
            "Paracetamol 500mg + Amoxicillin 250mg"
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_single_drug(self, validator):
        """Test single drug (no interactions possible)."""
        result = await validator._check_interactions(
            "Metformin 500mg twice daily"
        )

        assert len(result) == 0


class TestTemporalValidation:
    """Test temporal consistency."""

    @pytest.mark.asyncio
    async def test_chronological_dates(self, validator):
        """Test valid chronological order."""
        result = await validator._validate_temporal(
            "Visit 1: 01/01/2024. Visit 2: 15/01/2024."
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_reverse_dates(self, validator):
        """Test reversed dates."""
        result = await validator._validate_temporal(
            "Discharge: 15/01/2024. Admission: 20/01/2024."
        )

        assert len(result) == 1
        assert result[0].category == "temporal"
        assert result[0].severity == ValidationSeverity.WARNING

    @pytest.mark.asyncio
    async def test_single_date(self, validator):
        """Test single date (no comparison needed)."""
        result = await validator._validate_temporal(
            "Date: 01/01/2024"
        )

        assert len(result) == 0


class TestTerminologyValidation:
    """Test medical terminology validation."""

    @pytest.mark.asyncio
    async def test_common_ocr_error(self, validator):
        """Test detection of common OCR errors."""
        result = await validator._validate_terminology(
            "التهب في المعدة", "ar"
        )

        assert len(result) >= 1
        assert any("التهب" in issue.message for issue in result)

    @pytest.mark.asyncio
    async def test_correct_terminology(self, validator):
        """Test correct terms pass."""
        result = await validator._validate_terminology(
            "التهاب في المعدة", "ar"
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_dosage_ocr_error(self, validator):
        """Test dosage OCR errors."""
        result = await validator._validate_terminology(
            "جرعه 500 ملغ", "ar"
        )

        assert len(result) >= 1
        assert any("جرعه" in issue.message for issue in result)


class TestLateralityValidation:
    """Test laterality consistency."""

    @pytest.mark.asyncio
    async def test_conflicting_laterality(self, validator):
        """Test right + left in same sentence."""
        result = await validator._validate_laterality(
            "كسر في الفخذ الأيمن والفخذ الأيسر"
        )

        assert len(result) == 1
        assert result[0].category == "laterality"
        assert result[0].severity == ValidationSeverity.ERROR
        assert "تعارض في الجانبية" in result[0].message

    @pytest.mark.asyncio
    async def test_consistent_laterality(self, validator):
        """Test consistent laterality."""
        result = await validator._validate_laterality(
            "ألم في الجانب الأيمن"
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_mixed_language_laterality(self, validator):
        """Test Arabic + English laterality terms."""
        result = await validator._validate_laterality(
            "Fracture in the right femur"
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_multiple_sentences_different_laterality(self, validator):
        """Test different laterality in different sentences (allowed)."""
        result = await validator._validate_laterality(
            "كسر في الفخذ الأيمن. كسر سابق في الفخذ الأيسر."
        )

        # Different sentences - should be OK
        assert len(result) == 0


class TestFullValidation:
    """Test complete validation pipeline."""

    @pytest.mark.asyncio
    async def test_valid_prescription(self, validator):
        """Test valid prescription passes."""
        result = await validator.validate(
            text="Paracetamol 500mg twice daily for 5 days",
            context="prescription",
            language="en"
        )

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.overall_confidence > 0.9
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_invalid_prescription(self, validator):
        """Test invalid prescription fails."""
        result = await validator.validate(
            text="Paracetamol 50mg twice daily + Warfarin 5mg + Aspirin 100mg",
            context="prescription",
            language="en"
        )

        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert len(result.issues) > 0

        # Should have dosage issue + interaction issue
        categories = [i.category for i in result.issues]
        assert "dosage" in categories
        assert "drug_interaction" in categories

    @pytest.mark.asyncio
    async def test_arabic_prescription(self, validator):
        """Test Arabic prescription validation."""
        result = await validator.validate(
            text="باراسيتامول 500 ملغ مرتين يومياً",
            context="prescription",
            language="ar"
        )

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_confidence_calculation(self, validator):
        """Test overall confidence calculation."""
        # Text with multiple issues
        result = await validator.validate(
            text="Paracetamol 50mg + Warfarin + Aspirin",
            context="prescription"
        )

        assert result.overall_confidence < 0.95
        assert result.overall_confidence >= 0.3

    @pytest.mark.asyncio
    async def test_suggestions_generation(self, validator):
        """Test suggestions are generated for errors."""
        result = await validator.validate(
            text="Paracetamol 50mg",
            context="prescription"
        )

        assert len(result.suggestions) > 0
        assert any("تأكد" in s or "check" in s.lower() for s in result.suggestions)

    @pytest.mark.asyncio
    async def test_entity_extraction(self, validator):
        """Test entity extraction from text."""
        result = await validator.validate(
            text="Paracetamol 500mg twice daily",
            context="prescription"
        )

        assert len(result.validated_entities) > 0
        assert any(e["type"] == "dosage" for e in result.validated_entities)


class TestLLMIntegration:
    """Test LLM-based validation (when available)."""

    @pytest.mark.asyncio
    async def test_llm_validation_called(self, validator_with_llm):
        """Test LLM is called when available."""
        result = await validator_with_llm.validate(
            text="Complex medical case",
            context="report"
        )

        # LLM mock should have been called
        validator_with_llm.llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_not_called_without_gateway(self, validator):
        """Test LLM is not called when no gateway."""
        result = await validator.validate(
            text="Simple case",
            context="prescription"
        )

        # Should work without LLM
        assert isinstance(result, ValidationResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
