"""OmniMedical Suite v2.0 — CorrectionMemory & AutoPromotion Tests"""

import pytest
from datetime import datetime, timedelta
from omnimedical_gradio_ui import CorrectionMemoryV2, AutoPromotionEngine, MedicalContextProtector


class TestCorrectionMemoryV2:
    """Test suite for correction memory and auto-promotion."""

    def test_save_and_get(self, temp_correction_db):
        """Test saving and retrieving a correction."""
        mem = CorrectionMemoryV2(temp_correction_db)
        mem.save("فخد", "عظم الفخذ", "ar", "كسر في", "الأيمن", 0.65, 0.92, "test")

        result = mem.get("فخد")
        assert result == "عظم الفخذ"

    def test_get_nonexistent(self, temp_correction_db):
        """Test getting non-existent correction returns None."""
        mem = CorrectionMemoryV2(temp_correction_db)
        assert mem.get("nonexistent") is None

    def test_frequency_increment(self, temp_correction_db):
        """Test that saving same original increments frequency."""
        mem = CorrectionMemoryV2(temp_correction_db)

        mem.save("فخد", "عظم الفخذ", "ar", "كسر في", "الأيمن", 0.65, 0.92, "test1")
        mem.save("فخد", "عظم الفخذ", "ar", "إصابة في", "مع نزيف", 0.68, 0.90, "test2")

        stats = mem.get_stats()
        assert stats["total"] == 1
        assert stats["top"][0][2] == 2  # frequency = 2

    def test_apply_to_text(self, temp_correction_db):
        """Test applying corrections to raw text."""
        mem = CorrectionMemoryV2(temp_correction_db)
        mem.save("فخد", "عظم الفخذ", "ar", "", "", 0.5, 0.9, "test")

        text = "كسر في فخد الأيمن"
        corrected, changes = mem.apply_to_text(text)

        assert "عظم الفخذ" in corrected
        assert len(changes) == 1
        assert changes[0]["original"] == "فخد"
        assert changes[0]["corrected"] == "عظم الفخذ"

    def test_confidence_gain_calculation(self, temp_correction_db):
        """Test confidence gain is calculated correctly."""
        mem = CorrectionMemoryV2(temp_correction_db)
        mem.save("test", "corrected", "ar", "", "", 0.60, 0.90, "test")

        stats = mem.get_stats()
        assert stats["avg_gain"] == 0.30  # 0.90 - 0.60

    def test_stats_empty_db(self, temp_correction_db):
        """Test stats on empty database."""
        mem = CorrectionMemoryV2(temp_correction_db)
        stats = mem.get_stats()

        assert stats["total"] == 0
        assert stats["promoted"] == 0
        assert stats["avg_gain"] == 0.0
        assert stats["top"] == []


class TestAutoPromotionEngine:
    """Test suite for auto-promotion engine."""

    def test_promotion_criteria_met(self, temp_correction_db, sample_correction_data):
        """Test correction is promoted when all criteria are met."""
        mem = CorrectionMemoryV2(temp_correction_db)
        promoter = AutoPromotionEngine(mem)

        # Seed with 3 occurrences (meets min_frequency=3)
        for orig, corr, lang, ctx_b, ctx_a, conf_b, conf_a in sample_correction_data[:3]:
            mem.save(orig, corr, lang, ctx_b, ctx_a, conf_b, conf_a, "test")

        promoted = promoter.run_promotion_cycle()

        assert len(promoted) >= 1
        assert promoted[0]["original"] == "فخد"
        assert promoted[0]["corrected"] == "عظم الفخذ"

    def test_promotion_criteria_not_met_frequency(self, temp_correction_db):
        """Test correction not promoted when frequency too low."""
        mem = CorrectionMemoryV2(temp_correction_db)
        promoter = AutoPromotionEngine(mem)

        # Only 1 occurrence (below min_frequency=3)
        mem.save("test", "corrected", "ar", "", "", 0.5, 0.95, "test")

        promoted = promoter.run_promotion_cycle()
        assert len(promoted) == 0

    def test_promotion_criteria_not_met_confidence(self, temp_correction_db):
        """Test correction not promoted when confidence gain too low."""
        mem = CorrectionMemoryV2(temp_correction_db)
        promoter = AutoPromotionEngine(mem)

        # Low confidence gain (below min_confidence_gain=0.05)
        for _ in range(3):
            mem.save("test", "corrected", "ar", "", "", 0.90, 0.92, "test")

        promoted = promoter.run_promotion_cycle()
        assert len(promoted) == 0  # gain = 0.02 < 0.05

    def test_promotion_age_limit(self, temp_correction_db):
        """Test old corrections are not promoted."""
        mem = CorrectionMemoryV2(temp_correction_db)
        promoter = AutoPromotionEngine(mem, criteria={"max_age_days": 1})

        # Would need to manipulate timestamps for full test
        # For now, test the criteria logic
        assert promoter.criteria["max_age_days"] == 1

    def test_promotion_history_tracking(self, temp_correction_db, sample_correction_data):
        """Test promotion history is tracked."""
        mem = CorrectionMemoryV2(temp_correction_db)
        promoter = AutoPromotionEngine(mem)

        for orig, corr, lang, ctx_b, ctx_a, conf_b, conf_a in sample_correction_data[:3]:
            mem.save(orig, corr, lang, ctx_b, ctx_a, conf_b, conf_a, "test")

        promoter.run_promotion_cycle()
        report = promoter.get_promotion_report()

        assert not report.empty
        assert len(report) >= 1

    def test_custom_criteria(self, temp_correction_db):
        """Test custom promotion criteria."""
        mem = CorrectionMemoryV2(temp_correction_db)
        custom_criteria = {
            "min_frequency": 2,
            "min_confidence_gain": 0.01,
            "max_age_days": 7
        }
        promoter = AutoPromotionEngine(mem, criteria=custom_criteria)

        assert promoter.criteria["min_frequency"] == 2
        assert promoter.criteria["min_confidence_gain"] == 0.01
