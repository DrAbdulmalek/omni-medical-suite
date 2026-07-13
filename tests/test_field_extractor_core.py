from src.ocr.field_extractor import ArabicMedicalFieldExtractor


class TestArabicMedicalFieldExtractor:
    def test_extracts_core_fields(self):
        extractor = ArabicMedicalFieldExtractor()
        text = """
        اسم المريض: أحمد محمد
        رقم المريض: P-1007
        التاريخ: 2026-07-12
        التشخيص: ارتفاع ضغط الدم
        الأدوية: أملوديبين 5mg، أسبرين 81mg
        """
        fields = extractor.extract_fields(text)
        assert fields.patient_name == "أحمد محمد"
        assert fields.patient_id == "P-1007"
        assert fields.date == "2026-07-12"
        assert fields.diagnosis == "ارتفاع ضغط الدم"
        assert fields.medications == ["أملوديبين 5mg", "أسبرين 81mg"]

    def test_template_signature_redacts_patient_values(self):
        extractor = ArabicMedicalFieldExtractor()
        text = "اسم المريض: أحمد محمد\nرقم المريض: P-1007\nالتشخيص: التهاب"
        fields = extractor.extract_fields(text)
        assert "أحمد محمد" not in fields.template_signature
        assert "P-1007" not in fields.template_signature
        assert "اسم المريض" in fields.template_signature
