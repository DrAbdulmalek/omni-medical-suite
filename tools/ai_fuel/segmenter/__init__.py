"""
AI Fuel Engine - Document Segmenter Module

Provides advanced text segmentation strategies for splitting source documents
into semantically meaningful chunks suitable for classification, embedding,
and AI model training.

Three primary segmentation strategies are available:

- **Size-based**: Token-count windows with configurable overlap.
- **Semantic**: Topic-boundary detection via sentence-level similarity.
- **Structural**: Header / list / paragraph-aware splitting.

A **hybrid** method combines all three for optimal results.

Quick Start::

    from segmenter import DocumentSegmenter

    seg = DocumentSegmenter()
    chunks = seg.segment(long_text, method="hybrid")
"""

from segmenter.document_segmenter import DocumentSegmenter
from segmenter.context_preserver import ContextPreserver
from segmenter.chunk_validator import ChunkValidator

__all__ = [
    "DocumentSegmenter",
    "ContextPreserver",
    "ChunkValidator",
]