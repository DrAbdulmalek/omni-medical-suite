"""
AI Fuel Engine - Core Module

Provides the foundational components for the AI Fuel Engine pipeline,
including configuration management, data schemas, utility functions,
PHI protection, and metrics collection.
"""

from core.config import AIFuelConfig
from core.schemas import (
    ChunkType,
    ClassificationMethod,
    ExportFormat,
    Language,
    TextChunk,
    ClassificationResult,
    ClassifiedChunk,
    DedupResult,
    ProcessingStats,
    DocumentResult,
    ReviewSample,
    PHIDetection,
)
from core.utils import (
    count_tokens,
    detect_language,
    normalize_arabic,
    clean_ocr_artifacts,
    compute_hash,
    calculate_similarity,
    format_processing_time,
    setup_logging,
    safe_filename,
    chunk_overlap_text,
)
from core.phi_protection import PHIMasker
from core.metrics import (
    documents_processed,
    chunks_created,
    classification_accuracy,
    dedup_rate,
    processing_duration,
    phi_detections,
)

__all__ = [
    # Config
    "AIFuelConfig",
    # Enums
    "ChunkType",
    "ClassificationMethod",
    "ExportFormat",
    "Language",
    # Schemas
    "TextChunk",
    "ClassificationResult",
    "ClassifiedChunk",
    "DedupResult",
    "ProcessingStats",
    "DocumentResult",
    "ReviewSample",
    "PHIDetection",
    # Utilities
    "count_tokens",
    "detect_language",
    "normalize_arabic",
    "clean_ocr_artifacts",
    "compute_hash",
    "calculate_similarity",
    "format_processing_time",
    "setup_logging",
    "safe_filename",
    "chunk_overlap_text",
    # PHI Protection
    "PHIMasker",
    # Metrics
    "documents_processed",
    "chunks_created",
    "classification_accuracy",
    "dedup_rate",
    "processing_duration",
    "phi_detections",
]
