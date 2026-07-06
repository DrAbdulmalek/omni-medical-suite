"""
AI Fuel Engine - Schemas Module

Pydantic v2 data models used throughout the pipeline for type-safe
serialization, validation, and API contracts.  Every stage of the
AI Fuel Engine (segmentation, classification, deduplication, export)
produces or consumes one of these models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ======================================================================
# Enumerations
# ======================================================================


class ChunkType(str, Enum):
    """Strategy used to create a text chunk."""

    SIZE_BASED = "size_based"
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"


class ClassificationMethod(str, Enum):
    """Method used to assign a category to a text chunk."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    LLM = "llm"
    MANUAL = "manual"


class ExportFormat(str, Enum):
    """Supported export file formats."""

    JSONL = "jsonl"
    PARQUET = "parquet"
    RAG = "rag"
    CSV = "csv"


class Language(str, Enum):
    """Detected language of a text chunk."""

    ARABIC = "ar"
    ENGLISH = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# ======================================================================
# Chunk & Classification Models
# ======================================================================


class TextChunk(BaseModel):
    """A single, contiguous segment of source text.

    Produced by the **Segmenter** stage and consumed by downstream
    classifiers and deduplicators.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique chunk identifier (UUID4).")
    text: str = Field(..., min_length=1, description="The raw text content of the chunk.")
    chunk_type: ChunkType = Field(default=ChunkType.SIZE_BASED, description="Strategy used for segmentation.")
    start_token: int = Field(default=0, ge=0, description="Token offset of the chunk's start in the source document.")
    end_token: int = Field(default=0, ge=0, description="Token offset of the chunk's end in the source document.")
    token_count: int = Field(default=0, ge=0, description="Number of tokens in the chunk.")
    char_count: int = Field(default=0, ge=0, description="Number of characters in the chunk.")
    word_count: int = Field(default=0, ge=0, description="Number of whitespace-delimited words in the chunk.")
    language: Language = Field(default=Language.UNKNOWN, description="Detected primary language.")
    source_file: Optional[str] = Field(default=None, description="Path or name of the originating file.")
    source_page: Optional[int] = Field(default=None, ge=0, description="Page number within the source document (if applicable).")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary key-value metadata.")

    @field_validator("end_token")
    @classmethod
    def end_token_after_start(cls, v: int, info) -> int:
        """Ensure ``end_token`` is not less than ``start_token``."""
        if "start_token" in info.data and v < info.data["start_token"]:
            raise ValueError("end_token must be >= start_token")
        return v

    @field_validator("text")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from chunk text."""
        return v.strip()


class ClassificationResult(BaseModel):
    """Output of a single classification decision on a :class:`TextChunk`."""

    chunk_id: str = Field(..., description="ID of the chunk that was classified.")
    category: str = Field(..., min_length=1, description="Primary category label assigned to the chunk.")
    subcategory: Optional[str] = Field(default=None, description="Optional finer-grained sub-category.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence score in [0, 1].")
    method: ClassificationMethod = Field(..., description="The classification method that produced this result.")
    alternatives: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ordered list of runner-up categories with their scores.",
    )
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="Wall-clock time taken to classify (milliseconds).")

    @field_validator("alternatives")
    @classmethod
    def validate_alternatives(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure each alternative has at least 'category' and 'confidence' keys."""
        for idx, alt in enumerate(v):
            if "category" not in alt:
                raise ValueError(f"alternative[{idx}] missing 'category' key")
            if "confidence" not in alt:
                raise ValueError(f"alternative[{idx}] missing 'confidence' key")
        return v


class ClassifiedChunk(BaseModel):
    """A :class:`TextChunk` paired with its :class:`ClassificationResult`."""

    chunk: TextChunk = Field(..., description="The source text chunk.")
    classification: ClassificationResult = Field(..., description="Classification result for the chunk.")

    @field_validator("classification")
    @classmethod
    def chunk_id_matches(cls, v: ClassificationResult, info) -> ClassificationResult:
        """Ensure the classification's ``chunk_id`` references the owning chunk."""
        if "chunk" in info.data and v.chunk_id != info.data["chunk"].id:
            raise ValueError("classification.chunk_id must match chunk.id")
        return v


# ======================================================================
# Deduplication Model
# ======================================================================


class DedupResult(BaseModel):
    """Result of deduplication analysis for a single chunk."""

    is_duplicate: bool = Field(default=False, description="Whether the chunk is a duplicate of an earlier one.")
    duplicate_of: Optional[str] = Field(default=None, description="ID of the canonical chunk this is a duplicate of.")
    method: str = Field(default="exact", description="Deduplication method used ('exact' or 'semantic').")
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Cosine similarity to the canonical chunk.")


# ======================================================================
# Processing Statistics & Results
# ======================================================================


class ProcessingStats(BaseModel):
    """Aggregate statistics for a single processing run or batch."""

    total_documents: int = Field(default=0, ge=0, description="Total number of documents processed.")
    total_pages: int = Field(default=0, ge=0, description="Total pages across all documents.")
    total_chunks: int = Field(default=0, ge=0, description="Total chunks created before deduplication.")
    chunks_after_dedup: int = Field(default=0, ge=0, description="Chunks remaining after deduplication.")
    classification_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Map of category name → chunk count.",
    )
    processing_time_seconds: float = Field(default=0.0, ge=0.0, description="Total wall-clock processing time.")
    avg_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Mean classification confidence across all chunks.")
    phi_detections: int = Field(default=0, ge=0, description="Number of PHI detections during processing.")
    export_format: Optional[str] = Field(default=None, description="Format used for export (if exported).")
    output_path: Optional[str] = Field(default=None, description="File system path to the exported output.")


class DocumentResult(BaseModel):
    """Complete result of processing a single document through the full pipeline."""

    source_file: str = Field(..., description="Path or name of the processed document.")
    chunks: List[ClassifiedChunk] = Field(default_factory=list, description="All classified (and optionally deduplicated) chunks.")
    stats: ProcessingStats = Field(default_factory=ProcessingStats, description="Processing statistics for this document.")
    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp when the result was created.")


# ======================================================================
# Active Learning / Review Models
# ======================================================================


class ReviewSample(BaseModel):
    """A chunk flagged for human review as part of the active-learning loop."""

    id: Optional[int] = Field(default=None, description="Auto-incremented database primary key (set on persist).")
    text: str = Field(..., min_length=1, description="The chunk text under review.")
    predictions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Model predictions [{'category': ..., 'confidence': ...}, ...].",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Highest prediction confidence (used to flag low-confidence samples).")
    status: str = Field(default="pending", description="Review status: pending, approved, rejected, skipped.")
    correct_category: Optional[str] = Field(default=None, description="Human-annotated correct category.")
    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp when the sample was created.")
    reviewed_at: Optional[datetime] = Field(default=None, description="Timestamp when the sample was reviewed.")

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        """Ensure the status is one of the allowed values."""
        allowed = {"pending", "approved", "rejected", "skipped"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v


# ======================================================================
# PHI Detection Model
# ======================================================================


class PHIDetection(BaseModel):
    """A single detected instance of Protected Health Information."""

    phi_type: str = Field(
        ...,
        description="Type of PHI detected (EMAIL, PHONE, DATE, ID, NAME_AR, NAME_EN, MRN).",
    )
    value: str = Field(..., description="The raw detected value from the source text.")
    start_pos: int = Field(..., ge=0, description="Character offset where the PHI starts in the source text.")
    end_pos: int = Field(..., ge=0, description="Character offset where the PHI ends in the source text.")
    masked_value: str = Field(default="", description="The masked/redacted replacement string.")

    @field_validator("end_pos")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        """Ensure ``end_pos`` >= ``start_pos``."""
        if "start_pos" in info.data and v < info.data["start_pos"]:
            raise ValueError("end_pos must be >= start_pos")
        return v

    @field_validator("phi_type")
    @classmethod
    def valid_phi_type(cls, v: str) -> str:
        """Ensure the PHI type is recognized."""
        allowed = {"EMAIL", "PHONE", "DATE", "ID", "NAME_AR", "NAME_EN", "MRN"}
        if v not in allowed:
            raise ValueError(f"phi_type must be one of {allowed}, got '{v}'")
        return v
