"""
AI Fuel Engine - Core Module

Provides the foundational components for the AI Fuel Engine pipeline,
including configuration management, data schemas, utility functions,
PHI protection, and metrics collection.
"""

from core.config import AIFuelConfig
from core.metrics import (
    chunks_created,
    classification_accuracy,
    dedup_rate,
    documents_processed,
    phi_detections,
    processing_duration,
)
from core.phi_protection import PHIMasker
from core.schemas import (
    ChunkType,
    ClassificationMethod,
    ClassificationResult,
    ClassifiedChunk,
    DedupResult,
    DocumentResult,
    ExportFormat,
    Language,
    PHIDetection,
    ProcessingStats,
    ReviewSample,
    TextChunk,
)
from core.utils import (
    calculate_similarity,
    chunk_overlap_text,
    clean_ocr_artifacts,
    compute_hash,
    count_tokens,
    detect_language,
    format_processing_time,
    normalize_arabic,
    safe_filename,
    setup_logging,
)

__all__ = [
    # Config
    "AIFuelConfig",
    # Enums
    "ChunkType",
    "ClassificationMethod",
    "ClassificationResult",
    "ClassifiedChunk",
    "DedupResult",
    "DocumentResult",
    "ExportFormat",
    "Language",
    "PHIDetection",
    # PHI Protection
    "PHIMasker",
    "ProcessingStats",
    "ReviewSample",
    # Schemas
    "TextChunk",
    "calculate_similarity",
    "chunk_overlap_text",
    "chunks_created",
    "classification_accuracy",
    "clean_ocr_artifacts",
    "compute_hash",
    # Utilities
    "count_tokens",
    "dedup_rate",
    "detect_language",
    # Metrics
    "documents_processed",
    "format_processing_time",
    "normalize_arabic",
    "phi_detections",
    "processing_duration",
    "safe_filename",
    "setup_logging",
]
