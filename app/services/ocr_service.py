"""
OCR processing service — integrates with existing OCR fusion system.
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OCRService:
    """Service layer for OCR processing operations."""
    
    def __init__(self):
        self._fusion_system = None
    
    @property
    def fusion_system(self):
        """Lazy-load the fusion system to avoid import-time overhead."""
        if self._fusion_system is None:
            try:
                from services.api.app.vision.ocr_fusion_system import OCRFusionSystem
                self._fusion_system = OCRFusionSystem()
                logger.info("OCR Fusion System loaded successfully")
            except ImportError as e:
                logger.warning(f"Could not import OCRFusionSystem: {e}")
        return self._fusion_system
    
    async def process_image(
        self,
        image_path: str,
        engines: Optional[list[str]] = None,
        fusion_method: str = "v2_spatial",
        medical_mode: bool = True,
    ) -> dict:
        """
        Process an image through the OCR fusion pipeline.
        Returns fused text, individual results, and extracted medical terms.
        """
        from app.core.telemetry import trace_operation, record_ocr_request
        
        start_time = time.time()
        
        with trace_operation("ocr.process_image", {
            "ocr.fusion_method": fusion_method,
            "ocr.medical_mode": str(medical_mode),
        }):
            try:
                if self.fusion_system is None:
                    raise RuntimeError("OCR Fusion System not available")
                
                # Process with fusion system
                result = self.fusion_system.process(
                    image_path=image_path,
                    engines=engines,
                    fusion_method=fusion_method,
                )
                
                duration = time.time() - start_time
                record_ocr_request(fusion_method, duration, success=True)
                
                return {
                    "fused_text": result.get("fused_text", ""),
                    "confidence": result.get("confidence", 0.0),
                    "engines_used": result.get("engines_used", []),
                    "processing_time": duration,
                }
            except Exception as e:
                duration = time.time() - start_time
                record_ocr_request(fusion_method, duration, success=False)
                logger.error(f"OCR processing failed: {e}")
                raise
    
    async def extract_medical_terms(self, text: str) -> list[dict]:
        """Extract medical terms from text using the knowledge graph."""
        try:
            from services.api.app.nlp.semantic_deduplication import SemanticDedup
            dedup = SemanticDedup()
            terms = dedup.extract_medical_entities(text)
            return terms
        except ImportError:
            logger.warning("Medical term extraction not available")
            return []


# Singleton instance
ocr_service = OCRService()
