from src.ocr.deduplication import WeightedMedicalDeduplicator, field_aware_similarity


class TestWeightedMedicalDeduplication:
    def test_same_template_different_patient_is_not_duplicate(self):
        dedup = WeightedMedicalDeduplicator()
        left = """
        اسم المريض: أحمد محمد
        رقم المريض: P-1007
        التاريخ: 2026-07-12
        التشخيص: ارتفاع ضغط الدم
        """
        right = """
        اسم المريض: خالد علي
        رقم المريض: P-2044
        التاريخ: 2026-07-12
        التشخيص: ارتفاع ضغط الدم
        """
        result = field_aware_similarity(left, right)
        assert result["field_scores"]["template_signature"] >= 0.8
        assert result["is_same_patient"] is False

    def test_same_patient_duplicate_is_detected(self):
        dedup = WeightedMedicalDeduplicator()
        left = "اسم المريض: أحمد محمد\nرقم المريض: P-1007\nالتاريخ: 2026-07-12\nالتشخيص: ارتفاع ضغط الدم"
        right = "اسم المريض: أحمد محمد\nرقم المريض: P-1007\nالتاريخ: 2026-07-12\nالتشخيص: ارتفاع ضغط الدم الأساسي"
        result = dedup.compare(left, right)
        assert result.is_same_patient is True
        assert result.score >= 0.85

    def test_batch_dedup_returns_two_uniques_when_patients_differ(self):
        dedup = WeightedMedicalDeduplicator()
        records = [
            "اسم المريض: أحمد محمد\nرقم المريض: P-1007\nالتاريخ: 2026-07-12",
            "اسم المريض: خالد علي\nرقم المريض: P-2044\nالتاريخ: 2026-07-12",
        ]
        result = dedup.deduplicate(records)
        assert result["unique_count"] == 2
        assert result["duplicates"] == []
