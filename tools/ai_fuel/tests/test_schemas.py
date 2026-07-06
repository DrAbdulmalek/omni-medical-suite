"""
Tests for Pydantic schemas: TextChunk, ClassificationResult, validation.
"""

import pytest
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError


# ---------------------------------------------------------------------------
# Schema replicas (lightweight — no engine import required)
# ---------------------------------------------------------------------------

class TextChunk(BaseModel):
    """A single segment of extracted text."""

    id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    chunk_index: int = Field(..., ge=0)
    source_file: str = Field(default="unknown.pdf")
    page_number: int | None = Field(default=None, ge=1)
    token_count: int = Field(default=0, ge=0)
    language: str = Field(default="en")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class ClassificationResult(BaseModel):
    """Result of classifying a text chunk."""

    chunk_id: str
    category: str = Field(..., min_length=1)
    sub_category: str = Field(default="")
    confidence: float = Field(..., ge=0.0, le=1.0)
    method: str = Field(default="keyword")
    metadata: dict = Field(default_factory=dict)


class ProcessingStats(BaseModel):
    """Aggregate statistics for a processing run."""

    total_chunks: int = Field(default=0, ge=0)
    classified: int = Field(default=0, ge=0)
    duplicates_removed: int = Field(default=0, ge=0)
    exported: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)


# ── Tests ──────────────────────────────────────────────────────────────────

class TestTextChunk:
    """Test TextChunk schema creation and validation."""

    def test_create_minimal(self):
        chunk = TextChunk(id="c1", text="Hello world", chunk_index=0)
        assert chunk.id == "c1"
        assert chunk.text == "Hello world"
        assert chunk.chunk_index == 0
        assert chunk.source_file == "unknown.pdf"
        assert chunk.page_number is None
        assert chunk.token_count == 0
        assert chunk.language == "en"
        assert chunk.created_at is not None

    def test_create_full(self):
        chunk = TextChunk(
            id="c42",
            text="Medical text about cardiology.",
            chunk_index=5,
            source_file="heart_book.pdf",
            page_number=12,
            token_count=38,
            language="ar",
        )
        assert chunk.source_file == "heart_book.pdf"
        assert chunk.page_number == 12
        assert chunk.token_count == 38
        assert chunk.language == "ar"

    def test_empty_id_raises(self):
        with pytest.raises(ValidationError):
            TextChunk(id="", text="some text", chunk_index=0)

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError):
            TextChunk(id="c1", text="", chunk_index=0)

    def test_negative_index_raises(self):
        with pytest.raises(ValidationError):
            TextChunk(id="c1", text="text", chunk_index=-1)

    def test_negative_page_raises(self):
        with pytest.raises(ValidationError):
            TextChunk(id="c1", text="text", chunk_index=0, page_number=0)

    def test_serialization_round_trip(self):
        chunk = TextChunk(id="x", text="data", chunk_index=3)
        data = chunk.model_dump()
        restored = TextChunk.model_validate(data)
        assert restored.id == chunk.id
        assert restored.text == chunk.text

    def test_json_export(self):
        chunk = TextChunk(id="j", text="json test", chunk_index=1)
        json_str = chunk.model_dump_json()
        assert '"id":"j"' in json_str
        assert '"text":"json test"' in json_str


class TestClassificationResult:
    """Test ClassificationResult schema."""

    def test_create(self):
        result = ClassificationResult(
            chunk_id="c1",
            category="pharmacology",
            confidence=0.92,
        )
        assert result.chunk_id == "c1"
        assert result.category == "pharmacology"
        assert result.confidence == 0.92
        assert result.method == "keyword"
        assert result.metadata == {}

    def test_full_result(self):
        result = ClassificationResult(
            chunk_id="c2",
            category="anatomy",
            sub_category="cardiovascular",
            confidence=0.88,
            method="embedding",
            metadata={"model": "multilingual-v2"},
        )
        assert result.sub_category == "cardiovascular"
        assert result.method == "embedding"
        assert result.metadata["model"] == "multilingual-v2"

    def test_confidence_bounds(self):
        # Exactly 0.0 and 1.0 should be valid
        ClassificationResult(chunk_id="c", category="test", confidence=0.0)
        ClassificationResult(chunk_id="c", category="test", confidence=1.0)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValidationError):
            ClassificationResult(chunk_id="c", category="test", confidence=1.1)

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError):
            ClassificationResult(chunk_id="c", category="test", confidence=-0.01)

    def test_empty_category_raises(self):
        with pytest.raises(ValidationError):
            ClassificationResult(chunk_id="c", category="", confidence=0.5)


class TestProcessingStats:
    """Test ProcessingStats aggregation schema."""

    def test_default_zeros(self):
        stats = ProcessingStats()
        assert stats.total_chunks == 0
        assert stats.classified == 0
        assert stats.duplicates_removed == 0
        assert stats.exported == 0
        assert stats.errors == 0

    def test_negative_raises(self):
        with pytest.raises(ValidationError):
            ProcessingStats(total_chunks=-1)

    def test_update_pattern(self):
        stats = ProcessingStats(total_chunks=100)
        stats.classified = 80
        stats.duplicates_removed = 5
        stats.exported = 75
        stats.errors = 2
        assert stats.total_chunks == 100
        assert stats.classified == 80
        assert stats.exported == 75
