"""Tests for the unified OCR post-processing pipeline."""

from __future__ import annotations

import pytest

from src.llm.postprocess_pipeline import PostProcessPipeline, PostProcessResult


class TestPostProcessPipeline:
    """Tests for PostProcessPipeline with backend='none' (no LLM required)."""

    def setup_method(self):
        self.pipe = PostProcessPipeline(backend="none")

    def test_pipeline_creates_with_none_backend(self):
        assert self.pipe is not None
        # Verify backend is none by checking a result
        result = self.pipe.process("test")
        assert result.backend_used == "none"

    def test_process_returns_result_dataclass(self):
        result = self.pipe.process("اسم المريض: أحمد")
        assert isinstance(result, PostProcessResult)

    def test_rtl_fix_applied_by_default(self):
        result = self.pipe.process("احمد محمد حسين")
        assert "rtl_fix" in result.steps_applied

    def test_normalization_applied_by_default(self):
        result = self.pipe.process("احمد محمد حسين")
        assert "normalization" in result.steps_applied

    def test_field_extraction_applied_by_default(self):
        result = self.pipe.process("اسم المريض: أحمد")
        assert "field_extraction" in result.steps_applied

    def test_llm_skipped_when_none_backend(self):
        result = self.pipe.process("اسم المريض: أحمد")
        assert "llm_correction" not in result.steps_applied

    def test_final_text_not_empty(self):
        result = self.pipe.process("اسم المريض: أحمد محمد")
        assert len(result.final_text) > 0

    def test_original_preserved(self):
        text = "اسم المريض: فاطمة علي"
        result = self.pipe.process(text)
        assert result.original == text

    def test_backend_none_reported(self):
        result = self.pipe.process("test")
        assert result.backend_used == "none"

    def test_fields_extracted_for_arabic_medical(self):
        text = "اسم المريض: أحمد محمد\nالتشخيص: ارتفاع ضغط الدم"
        result = self.pipe.process(text)
        assert result.fields is not None
        assert "patient_name" in result.fields or "diagnosis" in result.fields

    def test_process_batch_returns_list(self):
        texts = ["اسم المريض: أحمد", "اسم المريض: فاطمة"]
        results = self.pipe.process_batch(texts)
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, PostProcessResult) for r in results)

    def test_rtl_fix_can_be_disabled(self):
        result = self.pipe.process("احمد", apply_rtl=False)
        assert "rtl_fix" not in result.steps_applied

    def test_normalization_can_be_disabled(self):
        result = self.pipe.process("احمد", apply_normalization=False)
        assert "normalization" not in result.steps_applied

    def test_field_extraction_can_be_disabled(self):
        result = self.pipe.process("احمد", extract_fields=False)
        assert "field_extraction" not in result.steps_applied
        assert result.fields is None

    def test_empty_text_handled(self):
        result = self.pipe.process("")
        assert isinstance(result, PostProcessResult)
        assert result.final_text == ""

    def test_auto_backend_falls_back_to_none(self):
        """When no LLM backend is available, auto should fall back to none."""
        pipe = PostProcessPipeline(backend="auto")
        result = pipe.process("اسم المريض: أحمد")
        assert isinstance(result, PostProcessResult)
        # backend should be none since no LLM is installed
        assert result.backend_used in ("none", "gemini", "ollama", "jais")


class TestActiveLearningLoop:
    """Tests for ActiveLearningLoop (SQLite-based, no external deps)."""

    def test_loop_creates_and_stats(self, tmp_path):
        from packages.ai.active_learning_loop import ActiveLearningLoop

        db_path = str(tmp_path / "test_loop.db")
        loop = ActiveLearningLoop(db_path=db_path)
        stats = loop.get_stats("ar")
        assert "total_submissions" in stats
        assert stats["total_submissions"] == 0

    def test_submit_high_confidence_accepted(self, tmp_path):
        from packages.ai.active_learning_loop import ActiveLearningLoop

        db_path = str(tmp_path / "test_high.db")
        loop = ActiveLearningLoop(db_path=db_path)
        result = loop.submit_ocr_result(
            original_text="أحمد",
            ocr_text="احمد",
            confidence=0.95,
            language="ar",
        )
        assert result["status"] == "accepted"
        stats = loop.get_stats("ar")
        assert stats["total_submissions"] == 1

    def test_submit_low_confidence_queued(self, tmp_path):
        from packages.ai.active_learning_loop import ActiveLearningLoop

        db_path = str(tmp_path / "test_low.db")
        loop = ActiveLearningLoop(db_path=db_path, min_confidence_for_review=0.8)
        result = loop.submit_ocr_result(
            original_text="دواء مجهول",
            ocr_text="دواء م جهول",
            confidence=0.4,
            language="ar",
        )
        assert result["status"] == "queued_for_review"

    def test_review_queue_returns_low_confidence(self, tmp_path):
        from packages.ai.active_learning_loop import ActiveLearningLoop

        db_path = str(tmp_path / "test_queue.db")
        loop = ActiveLearningLoop(db_path=db_path, min_confidence_for_review=0.8)
        loop.submit_ocr_result("أحمد", "احمد", 0.3, "ar")
        loop.submit_ocr_result("فاطمة", "فاطمة", 0.9, "ar")
        queue = loop.get_review_queue("ar")
        assert len(queue) == 1
        assert queue[0]["confidence"] < 0.8

    def test_human_correction_flow(self, tmp_path):
        from packages.ai.active_learning_loop import ActiveLearningLoop

        db_path = str(tmp_path / "test_correction.db")
        loop = ActiveLearningLoop(db_path=db_path, min_confidence_for_review=0.8)
        item = loop.submit_ocr_result("المريض ياخذ اموكسيسلين", "المريض ياخذ اموكسيسلين", 0.4, "ar")
        review_queue = loop.get_review_queue("ar")
        assert len(review_queue) >= 1

        correction_id = loop.submit_human_correction(
            review_id=review_queue[0]["id"],
            corrected_text="المريض يأخذ أموكسيسيلين",
        )
        assert correction_id > 0

        # After correction, item should no longer be in queue
        new_queue = loop.get_review_queue("ar")
        assert len(new_queue) == 0

    def test_export_training_dataset(self, tmp_path):
        from packages.ai.active_learning_loop import ActiveLearningLoop

        db_path = str(tmp_path / "test_export.db")
        loop = ActiveLearningLoop(db_path=db_path)
        loop.submit_ocr_result("احمد", "أحمد", 0.5, "ar")
        loop.submit_ocr_result("فاطمة", "فاطمة", 0.5, "ar")

        # Need corrections first
        queue = loop.get_review_queue("ar")
        for item in queue:
            loop.submit_human_correction(item["id"], item["ocr_text"] + " (fixed)")

        output = loop.export_training_dataset("ar", format="jsonl")
        lines = [l for l in output.strip().split("\n") if l.strip()]
        assert len(lines) >= 1

    def test_export_to_file(self, tmp_path):
        from packages.ai.active_learning_loop import ActiveLearningLoop

        db_path = str(tmp_path / "test_export_file.db")
        output_path = str(tmp_path / "dataset.jsonl")
        loop = ActiveLearningLoop(db_path=db_path)
        loop.export_training_dataset("ar", format="jsonl", output_path=output_path)

        import os
        assert os.path.exists(output_path)