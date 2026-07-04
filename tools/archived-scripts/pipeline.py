"""OmniMedical Suite v2.0 — Processing Pipeline Service"""

import time
from typing import Optional, Dict, Any
from PIL import Image

from app.core.config import settings
from app.core.metrics import (
    document_processing_duration, fusion_engine_usage,
    context_conflicts, dedup_reduction_ratio, dedup_protected_chunks
)
from app.schemas.document import DocumentResponse

# Import pipeline stages (from the Gradio UI script)
# In production, these would be in app/core/pipeline/
from omnimedical_gradio_ui import (
    OCRFusionV2, MedicalContextProtector, SemanticDeduplicator,
    CorrectionMemoryV2, AutoPromotionEngine, MedicalVectorStore
)


class ProcessingPipeline:
    """
    End-to-end document processing pipeline.

    Stages:
    1. OCR (Tesseract → multi-engine in production)
    2. Fusion V2 (spatial alignment + weighted voting)
    3. Auto-Correction (CorrectionMemory lookup)
    4. Semantic Dedup (HDBSCAN + MedicalContextProtector)
    5. Vector Storage (Qdrant)
    """

    def __init__(self):
        self.fusion = OCRFusionV2(
            spatial_eps=settings.FUSION_SPATIAL_EPS,
            min_confidence=settings.FUSION_MIN_CONFIDENCE
        )
        self.protector = MedicalContextProtector()
        self.dedup = SemanticDeduplicator()
        self.memory = CorrectionMemoryV2(settings.CORRECTION_DB_PATH)
        self.promoter = AutoPromotionEngine(self.memory, self.protector)
        self.vector_store = MedicalVectorStore(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )

    async def process(
        self,
        image: Image.Image,
        language_hint: str = "auto",
        enable_correction: bool = True,
        enable_dedup: bool = True,
        patient_id: Optional[str] = None
    ) -> DocumentResponse:
        """Process a single medical document image"""

        stage_start = time.time()

        # Stage 1: OCR (simulated multi-engine for now)
        raw_text = self._run_ocr(image, language_hint)
        document_processing_duration.labels(stage="ocr").observe(time.time() - stage_start)

        # Stage 2: Fusion (simulated — would merge multiple engine outputs)
        stage_start = time.time()
        # In production: collect results from tesseract, easyocr, paddleocr, etc.
        # fused_tokens = self.fusion.fuse(engine_results)
        # For now, pass through
        document_processing_duration.labels(stage="fusion").observe(time.time() - stage_start)

        # Stage 3: Auto-Correction
        stage_start = time.time()
        corrected_text = raw_text
        if enable_correction:
            corrected_text, changes = self.memory.apply_to_text(raw_text)
        document_processing_duration.labels(stage="correction").observe(time.time() - stage_start)

        # Stage 4: Semantic Deduplication
        stage_start = time.time()
        final_text = corrected_text
        chunk_count = 0
        if enable_dedup:
            chunks = [c.strip() for c in corrected_text.split("\n") if len(c.strip()) > 10]
            if len(chunks) > 1:
                deduped = self.dedup.dedup(chunks)
                final_text = "\n".join([d["text"] for d in deduped])
                chunk_count = len(deduped)

                # Metrics
                reduction = 1 - (len(deduped) / len(chunks)) if chunks else 0
                dedup_reduction_ratio.set(reduction)
                protected = sum(1 for d in deduped if d["type"] == "protected_unique")
                if protected > 0:
                    dedup_protected_chunks.inc(protected)
        document_processing_duration.labels(stage="dedup").observe(time.time() - stage_start)

        # Stage 5: Vector Storage
        stage_start = time.time()
        doc_id = f"doc_{int(time.time() * 1000)}"
        # In production: use sentence-transformers
        # embedding = embedder.encode(final_text).tolist()
        # self.vector_store.store(doc_id, final_text, embedding, {"patient_id": patient_id})
        document_processing_duration.labels(stage="vectorize").observe(time.time() - stage_start)

        # Build response
        return DocumentResponse(
            id=doc_id,  # In production: UUID from database
            status="completed",
            processing_stage="vectorized",
            raw_text=raw_text[:1000] if len(raw_text) > 1000 else raw_text,
            corrected_text=corrected_text[:1000] if len(corrected_text) > 1000 else corrected_text,
            final_text=final_text[:1000] if len(final_text) > 1000 else final_text,
            confidence_score=0.85,  # In production: calculate from fusion
            language_detected=language_hint if language_hint != "auto" else "ar",
            chunk_count=chunk_count,
            created_at=time.time()
        )

    def _run_ocr(self, image: Image.Image, language: str) -> str:
        """Run OCR on image"""
        import pytesseract
        lang_code = "ara+eng" if language == "auto" or language == "ar+en" else language
        return pytesseract.image_to_string(image, lang=lang_code)
