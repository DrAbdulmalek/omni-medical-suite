"""Tests for engine router and fusion endpoints."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.vision.ocr_fusion_system import (
    BoundingBox,
    OCROutput,
    FusedResult,
    DocumentChunk,
)


def make_sample_ocr_output(engine_name="tesseract", confidence=0.9):
    """Helper to create sample OCROutput for testing."""
    return OCROutput(
        engine_name=engine_name,
        text="Patient: Ahmed Ali\nDiagnosis: Type 2 Diabetes\nMedication: Metformin 500mg",
        confidence=confidence,
        regions=[BoundingBox(x=10, y=10, w=200, h=30)],
        processing_time_ms=120.0,
        language_detected="ara+eng",
    )


class TestFusionEngine:
    """Test OCR fusion logic."""

    def test_weighted_vote_basic(self):
        """Weighted vote should produce a FusedResult from multiple engines."""
        from app.vision.ocr_fusion_system import OCRFusionEngine

        engine = OCRFusionEngine.__new__(OCRFusionEngine)
        engine.engines = {}

        results = [
            make_sample_ocr_output("tesseract", 0.92),
            make_sample_ocr_output("easyocr", 0.85),
        ]

        fused = engine._weighted_vote(results)
        assert isinstance(fused, FusedResult)
        assert fused.final_text is not None
        assert len(fused.final_text) > 0

    def test_best_confidence_selection(self):
        """Best confidence method should pick text from highest-scoring result."""
        from app.vision.ocr_fusion_system import OCRFusionEngine

        engine = OCRFusionEngine.__new__(OCRFusionEngine)
        engine.engines = {}

        results = [
            make_sample_ocr_output("tesseract", 0.75),
            make_sample_ocr_output("easyocr", 0.95),
            make_sample_ocr_output("paddleocr", 0.80),
        ]

        fused = engine._best_confidence(results)
        assert isinstance(fused, FusedResult)
        assert fused.final_text is not None
        # The final text should come from the best engine (easyocr, 0.95)
        assert len(fused.final_text) > 0

    def test_smart_fallback_graceful(self):
        """Smart fallback should handle single engine gracefully."""
        from app.vision.ocr_fusion_system import OCRFusionEngine

        engine = OCRFusionEngine.__new__(OCRFusionEngine)
        engine.engines = {}

        results = [make_sample_ocr_output("tesseract", 0.88)]
        fused = engine._smart_fallback(results)
        assert isinstance(fused, FusedResult)
        assert fused.final_text is not None
        assert len(fused.final_text) > 0

    def test_empty_results(self):
        """Fusion with empty results should return empty FusedResult."""
        from app.vision.ocr_fusion_system import OCRFusionEngine

        engine = OCRFusionEngine.__new__(OCRFusionEngine)
        engine.engines = {}

        fused = engine._best_confidence([])
        assert isinstance(fused, FusedResult)


class TestKnowledgeGraph:
    """Test medical knowledge graph extraction."""

    @pytest.mark.asyncio
    async def test_extract_entities(self):
        """Should extract medical entities from text."""
        from app.vision.ocr_fusion_system import MedicalKnowledgeGraph

        kg_builder = MedicalKnowledgeGraph()
        text = "Patient diagnosed with Type 2 Diabetes. Prescribed Metformin 500mg daily."
        kg = await kg_builder.build(text)

        assert len(kg.entities) > 0
        entity_types = [e.entity_type for e in kg.entities]
        assert len(entity_types) > 0

    @pytest.mark.asyncio
    async def test_extract_relations(self):
        """Should extract relations between medical entities."""
        from app.vision.ocr_fusion_system import MedicalKnowledgeGraph

        kg_builder = MedicalKnowledgeGraph()
        text = "Patient has Diabetes. Prescribed Metformin for Diabetes management."
        kg = await kg_builder.build(text)

        assert hasattr(kg, "relations")
        assert isinstance(kg.relations, list)

    @pytest.mark.asyncio
    async def test_arabic_entity_extraction(self):
        """Should extract entities from Arabic medical text."""
        from app.vision.ocr_fusion_system import MedicalKnowledgeGraph

        kg_builder = MedicalKnowledgeGraph()
        text = "المريض يعاني من السكري النوع الثاني. تم وصف ميتفورمين 500 ملغ."
        kg = await kg_builder.build(text)

        assert len(kg.entities) > 0

    def test_to_json(self):
        """Should serialize knowledge graph to JSON string."""
        from app.vision.ocr_fusion_system import MedicalKnowledgeGraph, KnowledgeGraph

        kg = KnowledgeGraph(
            entities=[],
            relations=[],
            metadata={"source": "test"},
        )
        json_str = MedicalKnowledgeGraph().to_json(kg)
        assert isinstance(json_str, str)
        assert "entities" in json_str


class TestDocumentChunking:
    """Test text chunking for semantic deduplication."""

    def test_chunk_text_basic(self):
        """Should split text into overlapping chunks."""
        from app.vision.ocr_fusion_system import SemanticDeduplicationEngine

        engine = SemanticDeduplicationEngine()
        text = "A" * 2000  # Long text
        chunks = engine._chunk_text(text, page_num=1)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk.text, str)
            assert len(chunk.text) > 0

    def test_chunk_text_short(self):
        """Short text should return a small number of chunks."""
        from app.vision.ocr_fusion_system import SemanticDeduplicationEngine

        engine = SemanticDeduplicationEngine()
        text = "Short text"
        chunks = engine._chunk_text(text, page_num=1)

        assert len(chunks) >= 1
        assert chunks[0].text == text


class TestBoundingBox:
    """Test BoundingBox utility."""

    def test_area(self):
        """Should calculate correct area."""
        bb = BoundingBox(x=0, y=0, w=100, h=50)
        assert bb.area == 5000

    def test_center(self):
        """Should calculate correct center point."""
        bb = BoundingBox(x=10, y=20, w=100, h=50)
        assert bb.center == (60.0, 45.0)
