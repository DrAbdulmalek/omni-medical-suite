"""OCR engines and OCR post-processing helpers for Omni Medical Suite."""

from .deduplication import QdrantMedicalSearch, WeightedMedicalDeduplicator, field_aware_similarity
from .deduplication_pipeline import DeduplicationPipeline, DeduplicationResult
from .easyocr_engine import EasyOCREngine
from .field_extractor import ArabicMedicalFieldExtractor, ExtractedMedicalFields
from .rtl_utils import ArabicRTLFixer

__all__ = [
    "ArabicMedicalFieldExtractor",
    "ArabicRTLFixer",
    "DeduplicationPipeline",
    "DeduplicationResult",
    "EasyOCREngine",
    "ExtractedMedicalFields",
    "QdrantMedicalSearch",
    "WeightedMedicalDeduplicator",
    "field_aware_similarity",
]
