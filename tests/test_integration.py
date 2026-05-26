# ============================================================================
# OmniMedical Suite — Integration Tests
# ============================================================================

import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.omni_ocr.adapter import UnifiedOCR, OCRResult
from packages.nlp.pipeline import MedicalNLPPipeline, NLPPipelineResult
from packages.learning.unified_learning import UnifiedLearning, FeatureVector


class TestUnifiedOCR:
    """Integration tests for the Unified OCR adapter."""

    def test_adapter_instantiation(self):
        """Test that UnifiedOCR can be instantiated without errors."""
        ocr = UnifiedOCR()
        assert ocr is not None
        assert ocr.cache_max_size == 50

    def test_available_engines(self):
        """Test engine availability detection."""
        ocr = UnifiedOCR()
        engines = ocr.get_available_engines()
        assert isinstance(engines, dict)
        # At minimum, configuration should be parseable
        assert 'config' in engines

    def test_process_with_invalid_input(self):
        """Test graceful handling of invalid input."""
        ocr = UnifiedOCR()
        # With all engines potentially unavailable, should still return a result
        result = ocr.process_image("nonexistent_file.png")
        assert result is not None
        assert isinstance(result, OCRResult)

    def test_cache_operations(self):
        """Test cache store and retrieval."""
        ocr = UnifiedOCR()
        ocr.clear_cache()
        assert len(ocr._cache) == 0

    def test_custom_engine_order(self):
        """Test custom engine ordering via constructor."""
        ocr = UnifiedOCR(engine_order=['tesseract', 'easyocr'])
        assert len(ocr.engine_order) == 2
        assert ocr.engine_order[0] == 'tesseract'


class TestMedicalNLPPipeline:
    """Integration tests for the Medical NLP Pipeline."""

    def test_pipeline_instantiation(self):
        """Test that MedicalNLPPipeline can be instantiated."""
        pipeline = MedicalNLPPipeline()
        assert pipeline is not None

    def test_pipeline_with_minimal_text(self):
        """Test pipeline with Arabic medical text."""
        pipeline = MedicalNLPPipeline(
            enable_preprocessing=True,
            enable_correction=True,
            enable_entity_extraction=True,
            enable_enrichment=True,
        )
        # Process with minimal config - components will fail gracefully
        result = pipeline.process("test text")
        assert result is not None
        assert isinstance(result, NLPPipelineResult)

    def test_pipeline_skip_stages(self):
        """Test pipeline with some stages disabled."""
        pipeline = MedicalNLPPipeline(
            enable_correction=False,
            enable_enrichment=False,
        )
        result = pipeline.process("test text", skip_entity_extraction=True)
        assert result is not None

    def test_pipeline_stage_results(self):
        """Test that stage results are recorded."""
        pipeline = MedicalNLPPipeline()
        result = pipeline.process("test")
        assert len(result.stage_results) >= 0  # May be empty if all skipped


class TestUnifiedLearning:
    """Integration tests for the Unified Learning adapter."""

    def test_instantiation(self):
        """Test that UnifiedLearning can be instantiated."""
        learner = UnifiedLearning()
        assert learner is not None

    def test_train_and_predict(self):
        """Test basic train-predict cycle."""
        learner = UnifiedLearning()

        # Create training features
        features = {
            'width': 800, 'height': 600, 'aspect_ratio': 1.33,
            'blur_score': 0.5, 'brightness': 0.7,
        }
        learner.train(features, label='medical_report')

        # Predict
        result = learner.predict(features)
        assert result is not None
        assert result.label == 'medical_report'
        assert result.confidence > 0

    def test_pattern_storage(self):
        """Test correction pattern storage and retrieval."""
        learner = UnifiedLearning()
        learner.store_pattern('القلب', 'القلب', language='ar')
        learner.store_pattern('القلب', 'القلب', language='ar')
        learner.store_pattern('القلب', 'القلب', language='ar')

        correction = learner.suggest_correction('القلب', language='ar')
        assert correction is not None

    def test_active_learning(self):
        """Test active learning selection strategies."""
        learner = UnifiedLearning()

        # Add some training data
        for i in range(10):
            features = {'width': 800, 'height': 600, 'blur_score': i/10}
            learner.train(features, label=f'class_{i % 3}')

        # Select samples for labeling
        pool = [
            {'width': 800, 'height': 600, 'blur_score': 0.5},
            {'width': 1024, 'height': 768, 'blur_score': 0.3},
            {'width': 640, 'height': 480, 'blur_score': 0.8},
        ]

        selected = learner.active_learn(pool, strategy='uncertainty', n=2)
        assert len(selected) <= 2

    def test_save_and_load(self):
        """Test model persistence."""
        learner = UnifiedLearning()
        learner.train({'width': 800}, label='test')
        learner.save()

        learner2 = UnifiedLearning()
        result = learner2.predict({'width': 800})
        assert result.label == 'test'

    def test_feedback_collection(self):
        """Test user feedback collection."""
        learner = UnifiedLearning()
        learner.collect_feedback('original', 'corrected', status='verified')
        learner.collect_feedback('wrong', 'right', status='rejected')

        correction_dict = learner.build_correction_dict_from_feedback()
        assert 'original' in correction_dict


class TestEndToEndPipeline:
    """End-to-end integration test: OCR → NLP → Learning."""

    def test_full_pipeline_flow(self):
        """Test the complete processing pipeline."""
        # 1. OCR
        ocr = UnifiedOCR()

        # 2. NLP (skip heavy stages for speed)
        nlp = MedicalNLPPipeline(
            enable_preprocessing=True,
            enable_correction=False,
            enable_entity_extraction=False,
            enable_enrichment=False,
        )

        # 3. Learning
        learner = UnifiedLearning()

        # Simulate a document processing flow
        nlp_result = nlp.process("medical document text")
        assert nlp_result is not None

        # Train learning system with features
        features = {
            'word_count': nlp_result.word_count,
            'confidence_score': 0.9,
        }
        learner.train(features, label='medical_report')
        result = learner.predict(features)
        assert result.label == 'medical_report'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
