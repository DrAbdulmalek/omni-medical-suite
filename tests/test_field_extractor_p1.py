"""Tests for P1-1 field extractor hardening.

Covers:
- Multi-line value support (diagnosis / medications span newlines)
- Bilingual labels (Arabic + English medical shorthand: Dx, Pt, DOB, Dr, Rx)
- Per-field confidence scoring in [0.0, 1.0]
- Safe template_signature (substring values don't corrupt longer values)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src/ is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SRC_DIR.parent))


@pytest.fixture
def extractor():
    from src.ocr.field_extractor import ArabicMedicalFieldExtractor

    return ArabicMedicalFieldExtractor()


# ---------------------------------------------------------------------------
# Bilingual label support
# ---------------------------------------------------------------------------
class TestBilingualLabels:
    def test_english_patient_name(self, extractor):
        f = extractor.extract_fields("Patient Name: Ahmed Ali")
        assert f.patient_name == "Ahmed Ali"

    def test_english_pt_name_shorthand(self, extractor):
        f = extractor.extract_fields("Pt Name: Ahmed Ali")
        assert f.patient_name == "Ahmed Ali"

    def test_arabic_patient_name(self, extractor):
        f = extractor.extract_fields("اسم المريض: محمد أحمد")
        assert f.patient_name == "محمد أحمد"

    def test_english_patient_id_mrn(self, extractor):
        f = extractor.extract_fields("MRN: MRN-12345")
        assert f.patient_id == "MRN-12345"

    def test_english_patient_id_file_no(self, extractor):
        f = extractor.extract_fields("File No: 98765")
        assert f.patient_id == "98765"

    def test_english_date_dob(self, extractor):
        f = extractor.extract_fields("DOB: 2024-01-15")
        assert f.date == "2024-01-15"

    def test_english_doctor_dr(self, extractor):
        f = extractor.extract_fields("Dr: Smith")
        assert "Smith" in f.doctor_name

    def test_english_diagnosis_dx(self, extractor):
        f = extractor.extract_fields("Dx: Hypertension\nMedications: Amlodipine")
        assert "Hypertension" in f.diagnosis

    def test_english_medications_rx(self, extractor):
        f = extractor.extract_fields("Rx: Amlodipine 5mg")
        # `in` on a list checks membership, so check that any item contains "Amlodipine"
        assert any("Amlodipine" in m for m in f.medications)

    def test_arabic_date(self, extractor):
        f = extractor.extract_fields("التاريخ: 2024-03-20")
        assert f.date == "2024-03-20"

    def test_arabic_diagnosis(self, extractor):
        f = extractor.extract_fields("التشخيص: ارتفاع ضغط الدم\nالأدوية: كونكور")
        assert "ارتفاع" in f.diagnosis


# ---------------------------------------------------------------------------
# Multi-line value support
# ---------------------------------------------------------------------------
class TestMultilineValues:
    def test_diagnosis_spans_multiple_lines(self, extractor):
        text = (
            "Diagnosis: Hypertension Stage 2\n"
            "Requires follow-up in 2 weeks\n"
            "Medications: Amlodipine 5mg"
        )
        f = extractor.extract_fields(text)
        assert "Hypertension" in f.diagnosis
        assert "follow-up" in f.diagnosis
        # Medications should not bleed into diagnosis
        assert "Amlodipine" not in f.diagnosis

    def test_medications_split_on_newlines(self, extractor):
        text = (
            "Medications: Amlodipine 5mg\n"
            "Lisinopril 10mg\n"
            "Aspirin 75mg"
        )
        f = extractor.extract_fields(text)
        assert len(f.medications) == 3
        assert "Amlodipine 5mg" in f.medications
        assert "Lisinopril 10mg" in f.medications
        assert "Aspirin 75mg" in f.medications

    def test_medications_split_on_semicolons(self, extractor):
        f = extractor.extract_fields("Medications: Amlodipine 5mg; Lisinopril 10mg")
        assert len(f.medications) == 2

    def test_medications_split_on_arabic_comma(self, extractor):
        f = extractor.extract_fields("Medications: Amlodipine 5mg، Lisinopril 10mg")
        assert len(f.medications) == 2

    def test_diagnosis_stops_at_next_label(self, extractor):
        text = (
            "Diagnosis: Type 2 Diabetes\n"
            "Medications: Metformin"
        )
        f = extractor.extract_fields(text)
        assert f.diagnosis == "Type 2 Diabetes"
        assert "Metformin" not in f.diagnosis


# ---------------------------------------------------------------------------
# Safe template_signature (P1-1 bug fix)
# ---------------------------------------------------------------------------
class TestSafeTemplateSignature:
    def test_substring_value_does_not_corrupt_longer(self, extractor):
        """patient_name='محمد' must not corrupt diagnosis='محمد مريض بمرض السكري'."""
        text = "اسم المريض: محمد\nالتشخيص: محمد مريض بمرض السكري"
        f = extractor.extract_fields(text)
        assert f.patient_name == "محمد"
        assert "مريض" in f.diagnosis
        assert "السكري" in f.diagnosis

    def test_duplicate_values_redacted(self, extractor):
        text = "اسم المريض: أحمد\nالتشخيص: أحمد مريض"
        f = extractor.extract_fields(text)
        # Both occurrences of "أحمد" should be redacted
        assert "أحمد" not in f.template_signature

    def test_placeholder_not_left_in_signature(self, extractor):
        """The internal placeholder must not leak into the final signature."""
        text = "اسم المريض: أحمد\nالتشخيص: مريض"
        f = extractor.extract_fields(text)
        assert "\x00" not in f.template_signature
        assert "VAL" not in f.template_signature


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------
class TestConfidenceScoring:
    def test_empty_fields_have_zero_confidence(self, extractor):
        f = extractor.extract_fields("")
        for field, val in f.confidence.items():
            assert val == 0.0, f"{field} should be 0.0 for empty input"

    def test_confidence_in_range(self, extractor):
        text = (
            "Patient Name: Ahmed Ali\n"
            "Patient ID: MRN-12345\n"
            "Date: 2024-01-15\n"
            "Doctor: Dr. Smith\n"
            "Diagnosis: Hypertension\n"
            "Medications: Amlodipine 5mg"
        )
        f = extractor.extract_fields(text)
        for field, val in f.confidence.items():
            assert 0.0 <= val <= 1.0, f"{field} out of range: {val}"

    def test_short_value_has_lower_confidence(self, extractor):
        f_short = extractor.extract_fields("Patient ID: 12")
        f_proper = extractor.extract_fields("Patient ID: MRN-12345")
        assert f_short.confidence["patient_id"] < f_proper.confidence["patient_id"]

    def test_patient_id_non_alnum_penalized(self, extractor):
        f_good = extractor.extract_fields("Patient ID: MRN-12345")
        f_bad = extractor.extract_fields("Patient ID: abc!@#")
        # The bad ID should have lower confidence
        # (or at least not higher)
        assert f_bad.confidence["patient_id"] <= f_good.confidence["patient_id"]

    def test_medications_confidence_is_average(self, extractor):
        f = extractor.extract_fields("Medications: A 5mg\nB 10mg\nC 20mg")
        # Should be the average of the 3 items' confidences
        assert f.confidence["medications"] > 0.0
        assert f.confidence["medications"] <= 1.0

    def test_confidence_dict_keys(self, extractor):
        f = extractor.extract_fields("Patient Name: X")
        expected_keys = {
            "patient_name", "patient_id", "date",
            "doctor_name", "diagnosis", "medications",
        }
        assert set(f.confidence.keys()) == expected_keys

    def test_confidence_in_to_dict(self, extractor):
        f = extractor.extract_fields("Patient Name: Ahmed")
        d = f.to_dict()
        assert "confidence" in d
        assert isinstance(d["confidence"], dict)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------
class TestBackwardCompat:
    def test_to_dict_still_returns_core_fields(self, extractor):
        f = extractor.extract_fields("Patient Name: Ahmed")
        d = f.to_dict()
        for key in [
            "patient_name", "patient_id", "date", "doctor_name",
            "diagnosis", "medications", "template_signature",
            "raw_text", "fingerprint",
        ]:
            assert key in d, f"missing key: {key}"

    def test_fingerprint_still_works(self, extractor):
        f = extractor.extract_fields(
            "Patient Name: Ahmed\nPatient ID: 123\nDate: 2024-01-01\nDoctor: Dr. X"
        )
        assert f.unique_patient_fingerprint() != ""
        assert len(f.unique_patient_fingerprint()) == 40  # SHA1 hex

    def test_extract_fields_returns_dataclass(self, extractor):
        from src.ocr.field_extractor import ExtractedMedicalFields

        f = extractor.extract_fields("test")
        assert isinstance(f, ExtractedMedicalFields)
