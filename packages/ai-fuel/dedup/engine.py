"""
AI Fuel Engine - Deduplication Engine

Orchestrator that combines exact, semantic, and context-aware deduplication
into a single, ordered pipeline.  The engine runs the cheapest strategy
first (exact hash) and falls through to progressively more expensive
strategies (semantic similarity), with a final context-protection gate
that can override deduplication decisions for medically critical content.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.schemas import DedupResult, TextChunk
from dedup.context_protector import MedicalContextProtector
from dedup.exact_dedup import ExactDeduplicator
from dedup.semantic_dedup import SemanticDeduplicator

logger = logging.getLogger(__name__)


class DeduplicationEngine:
    """Main deduplication engine combining exact and semantic methods.

    Pipeline order:
    1. **Exact dedup** — fast SHA-256 hash comparison.  Removes exact
       textual duplicates (after whitespace/casing normalisation).
    2. **Semantic dedup** — embedding-based cosine similarity.  Catches
       near-duplicates that differ superficially.
    3. **Context protection** — if a chunk flagged for removal contains
       protected medical data (drug dosages, vitals, lab values, etc.)
       it is restored to the output.

    The engine accumulates a :class:`DedupResult` for every chunk so that
    downstream consumers can audit deduplication decisions.
    """

    def __init__(self, config: Any = None) -> None:
        """Initialise the deduplication engine.

        Args:
            config: An :class:`AIFuelConfig` instance (or ``None`` for
                defaults).  Extracted fields:
                - ``exact_dedup`` (bool) – enable exact dedup.
                - ``semantic_dedup_threshold`` (float) – cosine similarity
                  threshold for semantic dedup.
                - ``semantic_model_name`` (str) – model name for encoding.
        """
        self.config = config

        # Resolve settings from config or use defaults
        if config is not None:
            exact_enabled = getattr(config, "exact_dedup", True)
            sem_threshold = getattr(config, "semantic_dedup_threshold", 0.95)
            sem_model = getattr(config, "semantic_model_name", "paraphrase-multilingual-mpnet-base-v2")
        else:
            exact_enabled = True
            sem_threshold = 0.95
            sem_model = "paraphrase-multilingual-mpnet-base-v2"

        self.exact_dedup = ExactDeduplicator()
        self.semantic_dedup = SemanticDeduplicator(
            threshold=sem_threshold,
            model_name=sem_model,
        )
        self.context_protector = MedicalContextProtector()

        self._exact_enabled: bool = exact_enabled
        self._results: Dict[str, DedupResult] = {}

        logger.info(
            "DeduplicationEngine initialised (exact=%s, semantic_threshold=%.2f).",
            self._exact_enabled,
            sem_threshold,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deduplicate(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Run the full deduplication pipeline on *chunks*.

        Processing order:
        1. Exact dedup (if enabled) removes textual duplicates.
        2. Semantic dedup removes near-duplicates among survivors.
        3. Context protection restores any chunk with protected medical data.

        The method populates :attr:`_results` so that each chunk's
        deduplication outcome can be inspected via :meth:`get_result`.

        Args:
            chunks: List of :class:`TextChunk` objects to deduplicate.

        Returns:
            Deduplicated list preserving original ordering of kept chunks.
        """
        start_time = time.time()
        self._results.clear()

        input_count = len(chunks)
        logger.info("Deduplication started with %d chunks.", input_count)

        # ── Phase 1: Exact dedup ─────────────────────────────────────
        if self._exact_enabled:
            exact_survivors: List[TextChunk] = []
            for chunk in chunks:
                is_dup, dup_id = self.exact_dedup.is_duplicate(chunk.text)

                if is_dup:
                    self._results[chunk.id] = DedupResult(
                        is_duplicate=True,
                        duplicate_of=dup_id,
                        method="exact",
                        similarity_score=1.0,
                    )
                    logger.debug(
                        "Exact duplicate removed: %s → %s", chunk.id, dup_id
                    )
                    continue

                # Register as canonical
                self.exact_dedup.add_to_index(chunk.text, chunk.id)
                exact_survivors.append(chunk)
                self._results[chunk.id] = DedupResult(is_duplicate=False, method="exact")

            logger.info(
                "Exact dedup: %d → %d chunks.", input_count, len(exact_survivors)
            )
        else:
            exact_survivors = list(chunks)

        # ── Phase 2: Semantic dedup ───────────────────────────────────
        sem_survivors: List[TextChunk] = []
        for chunk in exact_survivors:
            is_dup, dup_id, similarity = self.semantic_dedup.is_duplicate(chunk.text)

            if is_dup:
                self._results[chunk.id] = DedupResult(
                    is_duplicate=True,
                    duplicate_of=dup_id,
                    method="semantic",
                    similarity_score=round(similarity, 4),
                )
                logger.debug(
                    "Semantic duplicate removed: %s (sim=%.4f → %s).",
                    chunk.id,
                    similarity,
                    dup_id,
                )
                continue

            # Index the surviving chunk for future comparisons
            self.semantic_dedup.add_to_index(chunk.text, chunk.id)
            sem_survivors.append(chunk)

        logger.info(
            "Semantic dedup: %d → %d chunks.",
            len(exact_survivors),
            len(sem_survivors),
        )

        # ── Phase 3: Context protection ──────────────────────────────
        protected_count = 0
        output: List[TextChunk] = []
        for chunk in sem_survivors:
            result = self._results.get(chunk.id)
            if result is not None and result.is_duplicate:
                # Check if removed chunk has protected medical context
                if self.context_protector.has_protected_context(chunk.text):
                    # Restore the chunk
                    output.append(chunk)
                    self._results[chunk.id] = DedupResult(
                        is_duplicate=False,
                        method=result.method,
                        similarity_score=result.similarity_score,
                    )
                    protected_count += 1
                    logger.info(
                        "Chunk %s RESTORED – contains protected medical context.",
                        chunk.id,
                    )
                    continue

            output.append(chunk)

        elapsed = time.time() - start_time

        logger.info(
            "Deduplication complete: %d → %d chunks in %.2fs "
            "(protected_restored=%d).",
            input_count,
            len(output),
            elapsed,
            protected_count,
        )

        return output

    def get_result(self, chunk_id: str) -> Optional[DedupResult]:
        """Retrieve the :class:`DedupResult` for a specific chunk.

        Args:
            chunk_id: The chunk identifier.

        Returns:
            The dedup result, or ``None`` if the chunk was not processed.
        """
        return self._results.get(chunk_id)

    def get_stats(self) -> Dict:
        """Aggregate deduplication statistics from all sub-engines.

        Returns:
            Dictionary containing:
            - ``exact`` – stats from the exact deduplicator.
            - ``semantic`` – stats from the semantic deduplicator.
            - ``context_protector`` – info about protected patterns.
            - ``total_duplicates`` – combined duplicate count.
        """
        exact_stats = self.exact_dedup.get_stats()
        semantic_stats = self.semantic_dedup.get_stats()
        total_duplicates = exact_stats["duplicate_count"] + semantic_stats["duplicate_count"]

        return {
            "exact": exact_stats,
            "semantic": semantic_stats,
            "context_protector": self.context_protector.get_stats(),
            "total_duplicates": total_duplicates,
        }

    def clear(self) -> None:
        """Reset all internal state (indexes, results)."""
        self.exact_dedup.clear()
        self.semantic_dedup.clear_index()
        self._results.clear()
        logger.info("DeduplicationEngine fully reset.")

    def __repr__(self) -> str:
        return (
            f"DeduplicationEngine(exact={self._exact_enabled}, "
            f"exact_dupes={self.exact_dedup._duplicate_count}, "
            f"sem_dupes={self.semantic_dedup._duplicate_count})"
        )
