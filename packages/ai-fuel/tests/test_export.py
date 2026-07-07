"""
Tests for JSONLExporter — export sample chunks, verify file format.
"""

import json
import os
import tempfile
import pytest
from typing import List, Optional


# ---------------------------------------------------------------------------
# Minimal TextChunk and JSONLExporter replicas for standalone testing
# ---------------------------------------------------------------------------

class TextChunk:
    """Lightweight text chunk for export testing."""

    __slots__ = ("id", "text", "chunk_index", "source_file", "category", "confidence")

    def __init__(
        self,
        id: str,
        text: str,
        chunk_index: int,
        source_file: str = "unknown.pdf",
        category: str = "",
        confidence: float = 0.0,
    ):
        self.id = id
        self.text = text
        self.chunk_index = chunk_index
        self.source_file = source_file
        self.category = category
        self.confidence = confidence

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "source_file": self.source_file,
            "category": self.category,
            "confidence": self.confidence,
        }


class JSONLExporter:
    """Export text chunks to JSONL format."""

    def __init__(self, include_metadata: bool = True):
        self.include_metadata = include_metadata

    def export(
        self,
        chunks: List[TextChunk],
        filepath: str,
    ) -> int:
        """Write chunks to a JSONL file. Returns number of lines written."""
        count = 0
        with open(filepath, "w", encoding="utf-8") as f:
            for chunk in chunks:
                record = chunk.to_dict()
                if not self.include_metadata:
                    # Strip to just id + text
                    record = {"id": record["id"], "text": record["text"]}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        return count

    def export_batch(
        self,
        chunks: List[TextChunk],
        filepath: str,
        batch_size: int = 1000,
    ) -> int:
        """Export in batches, appending to file. Returns total lines."""
        total = 0
        mode = "w"  # first batch overwrites
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            with open(filepath, mode, encoding="utf-8") as f:
                for chunk in batch:
                    record = chunk.to_dict()
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total += 1
            mode = "a"  # subsequent batches append
        return total


# ── Helpers ────────────────────────────────────────────────────────────────

SAMPLE_CHUNKS = [
    TextChunk(
        id="c1",
        text="Cardiology is the study of heart diseases.",
        chunk_index=0,
        source_file="heart_book.pdf",
        category="cardiology",
        confidence=0.95,
    ),
    TextChunk(
        id="c2",
        text="Pharmacology deals with drug interactions and dosages.",
        chunk_index=1,
        source_file="pharma_book.pdf",
        category="pharmacology",
        confidence=0.88,
    ),
    TextChunk(
        id="c3",
        text="The anatomy of the human brain includes the cerebrum and cerebellum.",
        chunk_index=2,
        source_file="anatomy_book.pdf",
        category="anatomy",
        confidence=0.91,
    ),
    TextChunk(
        id="c4",
        text="مرض السكري هو حالة مزمنة تؤثر على مستوى السكر في الدم.",
        chunk_index=3,
        source_file="arabic_med.pdf",
        category="pathology",
        confidence=0.85,
    ),
]


# ── Tests ──────────────────────────────────────────────────────────────────

class TestJSONLExporterInit:
    """Test exporter initialization."""

    def test_default_include_metadata(self):
        exporter = JSONLExporter()
        assert exporter.include_metadata is True

    def test_exclude_metadata(self):
        exporter = JSONLExporter(include_metadata=False)
        assert exporter.include_metadata is False


class TestJSONLExporterExport:
    """Test exporting chunks to JSONL format."""

    def test_export_creates_file(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "output.jsonl")
            count = exporter.export(SAMPLE_CHUNKS, filepath)

            assert os.path.isfile(filepath)
            assert count == len(SAMPLE_CHUNKS)

    def test_export_valid_jsonl(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "output.jsonl")
            exporter.export(SAMPLE_CHUNKS, filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == len(SAMPLE_CHUNKS)
            for line in lines:
                record = json.loads(line.strip())
                assert "id" in record
                assert "text" in record

    def test_export_preserves_fields(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "output.jsonl")
            exporter.export(SAMPLE_CHUNKS, filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f]

            # Verify first record fields
            assert records[0]["id"] == "c1"
            assert records[0]["text"] == SAMPLE_CHUNKS[0].text
            assert records[0]["source_file"] == "heart_book.pdf"
            assert records[0]["category"] == "cardiology"
            assert records[0]["confidence"] == 0.95

    def test_export_unicode_text(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "unicode.jsonl")
            exporter.export(SAMPLE_CHUNKS, filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f]

            # The Arabic chunk should be preserved
            arabic_record = records[3]
            assert "مرض السكري" in arabic_record["text"]

    def test_export_without_metadata(self):
        exporter = JSONLExporter(include_metadata=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "minimal.jsonl")
            exporter.export(SAMPLE_CHUNKS, filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f]

            for record in records:
                assert set(record.keys()) == {"id", "text"}

    def test_export_empty_list(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "empty.jsonl")
            count = exporter.export([], filepath)
            assert count == 0
            assert os.path.isfile(filepath)
            # File should be empty
            assert os.path.getsize(filepath) == 0

    def test_export_one_chunk(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "single.jsonl")
            count = exporter.export([SAMPLE_CHUNKS[0]], filepath)
            assert count == 1

            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 1

    def test_export_overwrites_existing(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "overwrite.jsonl")
            exporter.export(SAMPLE_CHUNKS, filepath)
            exporter.export([SAMPLE_CHUNKS[0]], filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Second export should overwrite
            assert len(lines) == 1


class TestJSONLExporterBatch:
    """Test batch export functionality."""

    def test_batch_export_single_batch(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "batch.jsonl")
            total = exporter.export_batch(SAMPLE_CHUNKS, filepath, batch_size=10)
            assert total == len(SAMPLE_CHUNKS)

    def test_batch_export_multiple_batches(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "batch.jsonl")
            total = exporter.export_batch(SAMPLE_CHUNKS, filepath, batch_size=2)
            assert total == len(SAMPLE_CHUNKS)

            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == len(SAMPLE_CHUNKS)

    def test_batch_export_batch_size_one(self):
        exporter = JSONLExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "tiny_batch.jsonl")
            total = exporter.export_batch(SAMPLE_CHUNKS, filepath, batch_size=1)
            assert total == len(SAMPLE_CHUNKS)

            with open(filepath, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f]
            assert len(records) == len(SAMPLE_CHUNKS)
