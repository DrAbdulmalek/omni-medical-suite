"""
AI Fuel Engine - Exact Deduplicator

Fast, hash-based exact-match deduplication using SHA-256.  Text is
normalised (stripped, lowercased) before hashing so that superficial
differences in whitespace or casing do not defeat the dedup.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ExactDeduplicator:
    """Exact text deduplication using hash-based matching.

    Each unique piece of text (after normalisation) is stored as a SHA-256
    digest.  Subsequent chunks whose normalised text hashes to the same
    value are reported as duplicates of the first occurrence.

    Attributes:
        seen_hashes: Mapping from SHA-256 hex digest → chunk_id of the
            canonical (first seen) chunk.
    """

    def __init__(self) -> None:
        """Initialise an empty dedup index."""
        self.seen_hashes: Dict[str, str] = {}
        self._total_checks: int = 0
        self._duplicate_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, text: str) -> Tuple[bool, Optional[str]]:
        """Check whether *text* is an exact duplicate of a previously indexed chunk.

        The text is normalised (strip + lowercase) before hashing so that
        whitespace-only or casing differences do not produce false negatives.

        Args:
            text: The raw chunk text to test.

        Returns:
            A tuple ``(is_duplicate, duplicate_of_id)`` where
            *duplicate_of_id* is the ``chunk_id`` of the first chunk that
            produced the same hash, or ``None`` if the text is unique.
        """
        self._total_checks += 1
        if not text or not text.strip():
            logger.debug("Empty text passed to is_duplicate; skipping.")
            return (False, None)

        text_hash = self._compute_hash(text)

        if text_hash in self.seen_hashes:
            self._duplicate_count += 1
            canonical_id = self.seen_hashes[text_hash]
            logger.debug(
                "Exact duplicate found (hash=%s, canonical_id=%s).",
                text_hash[:12],
                canonical_id,
            )
            return (True, canonical_id)

        return (False, None)

    def add_to_index(self, text: str, chunk_id: str) -> None:
        """Register *text* (identified by *chunk_id*) in the dedup index.

        If the text's hash already exists the entry is **not** overwritten;
        the first chunk to arrive is always treated as canonical.

        Args:
            text: The raw chunk text.
            chunk_id: Unique identifier for this chunk.
        """
        if not text or not text.strip():
            logger.debug("Empty text passed to add_to_index; skipping.")
            return

        text_hash = self._compute_hash(text)

        if text_hash in self.seen_hashes:
            logger.warning(
                "add_to_index called for hash %s that already exists "
                "(existing_id=%s, new_id=%s). Keeping canonical.",
                text_hash[:12],
                self.seen_hashes[text_hash],
                chunk_id,
            )
            return

        self.seen_hashes[text_hash] = chunk_id
        logger.debug(
            "Added chunk %s to exact dedup index (hash=%s).",
            chunk_id,
            text_hash[:12],
        )

    def get_stats(self) -> Dict:
        """Return deduplication statistics.

        Returns:
            A dictionary containing:
            - ``total_checks`` – number of ``is_duplicate`` calls.
            - ``unique_hashes`` – number of unique hashes in the index.
            - ``duplicate_count`` – number of duplicates detected.
            - ``duplication_rate`` – ratio of duplicates to total checks.
        """
        total = max(self._total_checks, 1)
        return {
            "total_checks": self._total_checks,
            "unique_hashes": len(self.seen_hashes),
            "duplicate_count": self._duplicate_count,
            "duplication_rate": round(self._duplicate_count / total, 4),
        }

    def clear(self) -> None:
        """Reset the dedup index and counters."""
        self.seen_hashes.clear()
        self._total_checks = 0
        self._duplicate_count = 0
        logger.info("Exact dedup index cleared.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(text: str) -> str:
        """Normalise text and return its SHA-256 hex digest.

        Normalisation steps:
        1. Strip leading/trailing whitespace.
        2. Collapse internal whitespace runs to a single space.
        3. Lowercase.

        Args:
            text: Raw text.

        Returns:
            64-character hexadecimal SHA-256 digest.
        """
        import re

        normalised = re.sub(r"\s+", " ", text.strip().lower())
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        return (
            f"ExactDeduplicator(indexed={len(self.seen_hashes)}, "
            f"duplicates={self._duplicate_count})"
        )
