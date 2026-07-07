"""
AI Fuel Engine - Semantic Deduplicator

Embedding-based deduplication that detects near-duplicate text chunks via
cosine similarity.  Uses *sentence-transformers* for encoding when
available, with graceful degradation when the library is absent.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

from core.schemas import TextChunk

logger = logging.getLogger(__name__)


# Lazy-load guard for optional heavy dependencies
_sentence_transformers_available = False
_np_available = False

try:
    import numpy as _np

    _np_available = True
except ImportError:  # pragma: no cover
    _np = None  # type: ignore[assignment]

try:
    from sentence_transformers import SentenceTransformer as _ST

    _sentence_transformers_available = True
except ImportError:  # pragma: no cover
    _ST = None  # type: ignore[assignment,misc]


class SemanticDeduplicator:
    """Semantic deduplication using vector similarity.

    Chunks are encoded into dense vectors and compared via cosine similarity.
    If the similarity to any previously indexed chunk exceeds the configurable
    *threshold* (default 0.95), the chunk is flagged as a duplicate.

    Attributes:
        threshold: Cosine-similarity threshold above which chunks are
            considered duplicates.
        embeddings_cache: List of numpy arrays representing cached embeddings.
        chunk_ids: Parallel list of chunk identifiers.
        model: Lazy-loaded ``SentenceTransformer`` model.
    """

    def __init__(
        self,
        threshold: float = 0.95,
        model_name: str = "paraphrase-multilingual-mpnet-base-v2",
    ) -> None:
        """Initialise the semantic deduplicator.

        Args:
            threshold: Cosine similarity threshold (0–1).  Higher values
                are more conservative (fewer duplicates).
            model_name: Name of the sentence-transformers model to use
                for encoding.

        Raises:
            ValueError: If *threshold* is not in [0, 1].
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {threshold}")

        self.threshold = threshold
        self.model_name = model_name
        self.model = None
        self.embeddings_cache: List = []  # type: ignore[type-arg]
        self.chunk_ids: List[str] = []
        self._total_checks: int = 0
        self._duplicate_count: int = 0
        self._model_loaded: bool = False

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _ensure_model(self) -> None:
        """Lazily load the sentence-transformers model.

        If ``sentence-transformers`` or ``numpy`` is not installed the
        deduplicator logs a warning and falls back to always returning
        *not a duplicate*.
        """
        if self._model_loaded:
            return

        if not _sentence_transformers_available:
            logger.warning(
                "sentence-transformers not installed; "
                "semantic deduplication is disabled. "
                "Install with: pip install sentence-transformers"
            )
            self._model_loaded = True
            return

        if not _np_available:
            logger.warning(
                "numpy not installed; semantic deduplication is disabled. "
                "Install with: pip install numpy"
            )
            self._model_loaded = True
            return

        try:
            logger.info("Loading sentence-transformers model: %s", self.model_name)
            self.model = _ST(self.model_name)  # type: ignore[operator]
            self._model_loaded = True
            logger.info("Model loaded successfully.")
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Failed to load model %s: %s. Semantic dedup disabled.",
                self.model_name,
                exc,
            )
            self.model = None
            self._model_loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(
        self, text: str
    ) -> Tuple[bool, Optional[str], float]:
        """Check whether *text* is semantically similar to any indexed chunk.

        Args:
            text: The raw chunk text to test.

        Returns:
            A tuple ``(is_duplicate, duplicate_of_id, similarity)`` where:
            - *is_duplicate* is ``True`` when the best cosine similarity
              exceeds the threshold.
            - *duplicate_of_id* is the chunk id of the best-matching cached
              chunk (or ``None``).
            - *similarity* is the highest cosine similarity found.
        """
        self._total_checks += 1

        if not text or not text.strip():
            return (False, None, 0.0)

        self._ensure_model()

        if self.model is None or _np is None:
            # Fallback: cannot compute embeddings
            return (False, None, 0.0)

        if not self.embeddings_cache:
            return (False, None, 0.0)

        try:
            start_time = time.time()
            query_embedding = self.model.encode(text, normalize_embeddings=True)  # type: ignore[union-attr]
            elapsed_ms = (time.time() - start_time) * 1000

            # Compute cosine similarities against all cached embeddings
            cache_matrix = _np.stack(self.embeddings_cache)  # (N, dim)
            similarities = _np.dot(cache_matrix, query_embedding)  # (N,)

            best_idx = int(_np.argmax(similarities))
            best_similarity = float(similarities[best_idx])

            logger.debug(
                "Semantic check: best similarity=%.4f (chunk=%s, %.1fms).",
                best_similarity,
                self.chunk_ids[best_idx],
                elapsed_ms,
            )

            if best_similarity >= self.threshold:
                self._duplicate_count += 1
                return (True, self.chunk_ids[best_idx], best_similarity)

            return (False, None, best_similarity)

        except Exception as exc:  # pragma: no cover
            logger.error("Error during semantic dedup check: %s", exc)
            return (False, None, 0.0)

    def add_to_index(self, text: str, chunk_id: str) -> None:
        """Encode *text* and store the embedding alongside *chunk_id*.

        Args:
            text: The raw chunk text.
            chunk_id: Unique identifier for this chunk.
        """
        if not text or not text.strip():
            return

        self._ensure_model()

        if self.model is None or _np is None:
            return

        try:
            embedding = self.model.encode(text, normalize_embeddings=True)  # type: ignore[union-attr]
            self.embeddings_cache.append(embedding)
            self.chunk_ids.append(chunk_id)
            logger.debug(
                "Added chunk %s to semantic index (%d cached).",
                chunk_id,
                len(self.embeddings_cache),
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Error encoding chunk %s: %s", chunk_id, exc)

    def batch_dedup(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Remove semantic duplicates from a batch of chunks.

        Iterates over *chunks* in order.  The first occurrence of any
        semantically unique text is kept; subsequent near-duplicates are
        discarded.

        Args:
            chunks: List of :class:`TextChunk` objects.

        Returns:
            Deduplicated list preserving original order.
        """
        unique: List[TextChunk] = []

        for chunk in chunks:
            is_dup, _dup_id, similarity = self.is_duplicate(chunk.text)

            if is_dup:
                logger.debug(
                    "Chunk %s removed (semantic dup, sim=%.4f).",
                    chunk.id,
                    similarity,
                )
                continue

            # Protect against over-aggressive dedup on very short text
            if len(chunk.text.strip()) < 50 and similarity < self.threshold:
                unique.append(chunk)
                self.add_to_index(chunk.text, chunk.id)
                continue

            unique.append(chunk)
            self.add_to_index(chunk.text, chunk.id)

        logger.info(
            "Batch semantic dedup: %d → %d chunks.",
            len(chunks),
            len(unique),
        )
        return unique

    def clear_index(self) -> None:
        """Clear all embeddings and chunk ids from the index."""
        self.embeddings_cache.clear()
        self.chunk_ids.clear()
        self._total_checks = 0
        self._duplicate_count = 0
        logger.info("Semantic dedup index cleared.")

    def get_stats(self) -> Dict:
        """Return semantic deduplication statistics.

        Returns:
            Dictionary with ``total_checks``, ``cached_embeddings``,
            ``duplicate_count``, and ``duplication_rate``.
        """
        total = max(self._total_checks, 1)
        return {
            "total_checks": self._total_checks,
            "cached_embeddings": len(self.embeddings_cache),
            "duplicate_count": self._duplicate_count,
            "duplication_rate": round(self._duplicate_count / total, 4),
            "threshold": self.threshold,
            "model_name": self.model_name,
        }

    def __repr__(self) -> str:
        return (
            f"SemanticDeduplicator(threshold={self.threshold}, "
            f"cached={len(self.embeddings_cache)}, "
            f"duplicates={self._duplicate_count})"
        )


# Re-export for external type-checking when dependencies are available
if _np_available:
    import numpy as np  # noqa: F811
else:
    np = None  # type: ignore
