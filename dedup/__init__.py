"""
AI Fuel Engine - Deduplication Module

Provides exact, semantic, and context-aware deduplication for the AI Fuel Engine
pipeline.  The :class:`DeduplicationEngine` orchestrates all strategies to
eliminate duplicate and near-duplicate text chunks while preserving critical
medical context.

Modules:
    exact_dedup:     SHA-256 based exact-match deduplication.
    semantic_dedup:  Embedding-based cosine-similarity deduplication.
    context_protector: Medical-context aware protection against over-aggressive dedup.
    engine:          Top-level orchestrator combining all strategies.
"""

from dedup.exact_dedup import ExactDeduplicator
from dedup.semantic_dedup import SemanticDeduplicator
from dedup.context_protector import MedicalContextProtector
from dedup.engine import DeduplicationEngine

__all__ = [
    "ExactDeduplicator",
    "SemanticDeduplicator",
    "MedicalContextProtector",
    "DeduplicationEngine",
]
