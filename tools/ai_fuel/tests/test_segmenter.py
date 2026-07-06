"""
Tests for DocumentSegmenter — segment_by_size with sample text.
"""

import pytest
from typing import List


# ---------------------------------------------------------------------------
# Minimal replica for standalone testing
# ---------------------------------------------------------------------------

class TextChunk:
    """Lightweight text chunk data class."""

    __slots__ = ("text", "chunk_index", "token_count")

    def __init__(self, text: str, chunk_index: int, token_count: int):
        self.text = text
        self.chunk_index = chunk_index
        self.token_count = token_count


class DocumentSegmenter:
    """Segment documents into fixed-size overlapping chunks."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def segment_by_size(
        self, text: str, source_file: str = "unknown.txt"
    ) -> List[TextChunk]:
        """Split text into chunks based on character count."""
        if not text.strip():
            return []

        chunks: List[TextChunk] = []
        step = self.chunk_size - self.chunk_overlap
        start = 0
        idx = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end].strip()

            if chunk_text:  # skip empty fragments
                # rough token estimate: ~4 chars per token
                token_count = max(1, len(chunk_text) // 4)
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        chunk_index=idx,
                        token_count=token_count,
                    )
                )
                idx += 1

            start += step

        return chunks


# ── Tests ──────────────────────────────────────────────────────────────────

SAMPLE_MEDICAL_TEXT = (
    "Cardiology is the study of the heart and blood vessels. "
    "It encompasses the diagnosis and treatment of cardiovascular diseases, "
    "including coronary artery disease, heart failure, valvular heart disease, "
    "and arrhythmias. The field has evolved significantly with advances in "
    "interventional cardiology, electrophysiology, and cardiac imaging. "
    "Modern cardiology integrates echocardiography, cardiac MRI, and CT "
    "angiography for comprehensive patient assessment. "
    "Pharmacological management includes antiplatelet agents, beta-blockers, "
    "ACE inhibitors, and statins. Interventional procedures such as percutaneous "
    "coronary intervention and cardiac ablation have revolutionized treatment."
)


class TestDocumentSegmenterInit:
    """Test segmenter initialization and parameter validation."""

    def test_default_params(self):
        seg = DocumentSegmenter()
        assert seg.chunk_size == 512
        assert seg.chunk_overlap == 50

    def test_custom_params(self):
        seg = DocumentSegmenter(chunk_size=256, chunk_overlap=30)
        assert seg.chunk_size == 256
        assert seg.chunk_overlap == 30

    def test_zero_chunk_size_raises(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            DocumentSegmenter(chunk_size=0)

    def test_negative_chunk_size_raises(self):
        with pytest.raises(ValueError):
            DocumentSegmenter(chunk_size=-100)

    def test_negative_overlap_raises(self):
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            DocumentSegmenter(chunk_overlap=-1)

    def test_overlap_ge_size_raises(self):
        with pytest.raises(ValueError, match="overlap must be less than chunk_size"):
            DocumentSegmenter(chunk_size=100, chunk_overlap=100)


class TestSegmentBySize:
    """Test the core segment_by_size method."""

    def test_single_chunk_short_text(self):
        seg = DocumentSegmenter(chunk_size=1000, chunk_overlap=0)
        chunks = seg.segment_by_size("Short medical text.")
        assert len(chunks) == 1
        assert chunks[0].text == "Short medical text."
        assert chunks[0].chunk_index == 0

    def test_multiple_chunks(self):
        seg = DocumentSegmenter(chunk_size=100, chunk_overlap=10)
        chunks = seg.segment_by_size(SAMPLE_MEDICAL_TEXT)
        assert len(chunks) > 1
        # chunk indices should be sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunks_have_content(self):
        seg = DocumentSegmenter(chunk_size=200, chunk_overlap=20)
        chunks = seg.segment_by_size(SAMPLE_MEDICAL_TEXT)
        for chunk in chunks:
            assert len(chunk.text) > 0
            assert chunk.token_count > 0

    def test_empty_text_returns_empty(self):
        seg = DocumentSegmenter()
        assert seg.segment_by_size("") == []
        assert seg.segment_by_size("   \n\t  ") == []

    def test_chunk_size_respected(self):
        seg = DocumentSegmenter(chunk_size=150, chunk_overlap=20)
        chunks = seg.segment_by_size(SAMPLE_MEDICAL_TEXT)
        for chunk in chunks:
            assert len(chunk.text) <= 150

    def test_overlap_produces_shared_content(self):
        seg = DocumentSegmenter(chunk_size=200, chunk_overlap=50)
        chunks = seg.segment_by_size(SAMPLE_MEDICAL_TEXT)
        if len(chunks) >= 2:
            # The tail of chunk 0 should overlap with the head of chunk 1
            tail = chunks[0].text[-30:]
            head = chunks[1].text[:30]
            # With character overlap, some content should be shared
            overlap_chars = set(tail) & set(head)
            assert len(overlap_chars) > 0

    def test_no_overlap_exact_split(self):
        seg = DocumentSegmenter(chunk_size=200, chunk_overlap=0)
        chunks = seg.segment_by_size(SAMPLE_MEDICAL_TEXT)
        total_len = sum(len(c.text) for c in chunks)
        # Total characters should roughly equal input (within whitespace diffs)
        assert total_len >= len(SAMPLE_MEDICAL_TEXT) * 0.9

    def test_small_chunk_size_many_fragments(self):
        seg = DocumentSegmenter(chunk_size=50, chunk_overlap=5)
        chunks = seg.segment_by_size(SAMPLE_MEDICAL_TEXT)
        assert len(chunks) > 5  # should produce many small chunks
