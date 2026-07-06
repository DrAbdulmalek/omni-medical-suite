"""
AI Fuel Engine - Context Preserver

Preserves context between consecutive text chunks by maintaining overlap
regions and enriching each chunk with source metadata for downstream
traceability.

The :class:`ContextPreserver` operates on lists of :class:`TextChunk`
instances produced by the :class:`~segmenter.document_segmenter.DocumentSegmenter`
and is typically applied **after** segmentation but **before** classification.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.schemas import TextChunk
from core.utils import chunk_overlap_text, count_tokens

logger = logging.getLogger(__name__)


class ContextPreserver:
    """Preserves context between chunks and enriches them with metadata.

    The preserver provides three capabilities:

    1. **Overlap injection** — prepend the tail of the previous chunk to
       the current chunk so that models processing the chunk have access
       to surrounding context.
    2. **Metadata enrichment** — stamp each chunk with source-file
       information, timestamps, hash fingerprints, and custom user
       metadata.
    3. **Quality pre-check** — detect common issues (orphan sentences,
       insufficient tokens, etc.) before the chunk enters the pipeline.

    Example::

        preserver = ContextPreserver()
        chunks = preserver.add_overlap(chunks, overlap_tokens=200)
        chunks = preserver.add_metadata_context(chunks, {"source": "report.pdf"})
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ------------------------------------------------------------------
    # 1. Overlap injection
    # ------------------------------------------------------------------

    def add_overlap(
        self,
        chunks: List[TextChunk],
        overlap_tokens: int = 200,
    ) -> List[TextChunk]:
        """Add overlapping context between consecutive chunks.

        For each chunk (except the first), the tail of the *previous*
        chunk's text is prepended, separated by a contextual delimiter.
        The overlap is measured in **characters** (derived from the
        *overlap_tokens* parameter using an average chars-per-token
        heuristic of ≈ 4 for English and ≈ 3.5 for Arabic).

        The overlap region is stored in the chunk's ``metadata["overlap_text"]``
        for downstream inspection and the chunk's ``token_count`` and
        ``char_count`` are updated accordingly.

        Args:
            chunks: List of :class:`TextChunk` instances (in document order).
            overlap_tokens: Approximate number of overlapping tokens to
                preserve from the previous chunk.

        Returns:
            A new list of :class:`TextChunk` instances with overlap applied.
            The input list is **not** mutated.
        """
        if not chunks or len(chunks) <= 1:
            self._logger.debug("add_overlap: nothing to do (%d chunks)", len(chunks) if chunks else 0)
            return list(chunks)  # return a shallow copy

        result: List[TextChunk] = [chunks[0].model_copy(deep=True)]

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i].model_copy(deep=True)

            # Estimate overlap characters from token count.
            avg_chars_per_token = self._avg_chars_per_token(prev_chunk.text)
            overlap_chars = int(overlap_tokens * avg_chars_per_token)

            overlap_text = chunk_overlap_text(prev_chunk.text, overlap_chars)

            if overlap_text:
                # Find a clean break point (sentence or word boundary).
                clean_overlap = self._clean_overlap_boundary(overlap_text)

                if clean_overlap:
                    # Prepend with a delimiter.
                    new_text = f"[...context...] {clean_overlap}\n\n{curr_chunk.text}"
                    curr_chunk.text = new_text
                    curr_chunk.token_count = count_tokens(new_text)
                    curr_chunk.char_count = len(new_text)
                    curr_chunk.word_count = len(new_text.split())
                    curr_chunk.metadata["has_overlap"] = True
                    curr_chunk.metadata["overlap_text"] = clean_overlap
                    curr_chunk.metadata["overlap_chars"] = len(clean_overlap)

            result.append(curr_chunk)

        self._logger.info(
            "add_overlap: applied overlap (%d tokens) to %d of %d chunks",
            overlap_tokens,
            sum(1 for c in result if c.metadata.get("has_overlap")),
            len(result),
        )
        return result

    # ------------------------------------------------------------------
    # 2. Metadata enrichment
    # ------------------------------------------------------------------

    def add_metadata_context(
        self,
        chunks: List[TextChunk],
        source_info: Dict[str, Any],
    ) -> List[TextChunk]:
        """Enrich every chunk with source metadata for traceability.

        The following metadata keys are automatically set (if not already
        present):

        - ``source_file`` — from *source_info["source_file"]* (also stored
          in the chunk's ``source_file`` field).
        - ``source_page`` — from *source_info["source_page"]*.
        - ``processed_at`` — ISO-8601 UTC timestamp of when enrichment
          happened.
        - ``document_index`` — zero-based position in the original
          document (if *source_info["document_index"]* is provided).
        - ``total_chunks_in_document`` — total chunk count (if
          *source_info["total_chunks"]* is provided).

        All additional keys in *source_info* are merged into the chunk's
        ``metadata`` dict without overwriting existing values.

        Args:
            chunks: List of :class:`TextChunk` instances.
            source_info: Dictionary of source-level metadata to apply.

        Returns:
            A new list of enriched :class:`TextChunk` instances.
            The input list is **not** mutated.
        """
        if not chunks:
            return []

        timestamp = datetime.now(timezone.utc).isoformat()
        total = source_info.get("total_chunks", len(chunks))

        result: List[TextChunk] = []
        for idx, chunk in enumerate(chunks):
            enriched = chunk.model_copy(deep=True)

            # Set source_file on the model field and in metadata.
            if "source_file" in source_info and enriched.source_file is None:
                enriched.source_file = str(source_info["source_file"])
            if "source_page" in source_info and enriched.source_page is None:
                try:
                    enriched.source_page = int(source_info["source_page"])
                except (TypeError, ValueError):
                    pass

            # Automatic metadata fields.
            auto_meta: Dict[str, Any] = {
                "processed_at": timestamp,
                "chunk_index_in_document": idx,
                "total_chunks_in_document": total,
            }

            # Merge: auto_meta < source_info < existing chunk metadata
            # (existing takes precedence).
            merged = {**auto_meta, **source_info, **enriched.metadata}
            # Remove keys that belong on the model's top-level fields.
            for field_key in ("source_file", "source_page", "total_chunks"):
                merged.pop(field_key, None)

            enriched.metadata = merged
            result.append(enriched)

        self._logger.info(
            "add_metadata_context: enriched %d chunks with %d metadata keys",
            len(result),
            len(source_info),
        )
        return result

    # ------------------------------------------------------------------
    # 3. Chunk quality pre-check
    # ------------------------------------------------------------------

    def validate_chunk_quality(self, chunk: TextChunk) -> Dict[str, Any]:
        """Check a single chunk for common quality issues.

        The returned dictionary always contains:

        - ``is_valid`` (bool) — ``True`` when no issues are found.
        - ``issues`` (list of str) — human-readable descriptions of
          detected issues.
        - ``warnings`` (list of str) — non-fatal concerns.

        Checks performed:

        1. **Minimum token count** — Chunks with fewer than 50 tokens are
           flagged (may contain orphan sentences).
        2. **Maximum token count** — Chunks exceeding 8000 tokens are
           flagged (may exceed model context windows).
        3. **Orphan sentence detection** — Chunks ending mid-sentence
           (no terminal punctuation) are flagged.
        4. **Empty or whitespace-only text** — Always invalid.
        5. **Excessive overlap ratio** — If overlap text makes up more
           than 50 % of the chunk's total tokens, a warning is issued.
        6. **Language consistency** — If the chunk text is empty after
           stripping, a warning is issued.

        Args:
            chunk: The :class:`TextChunk` to validate.

        Returns:
            A dictionary with ``is_valid``, ``issues``, and ``warnings``.
        """
        issues: List[str] = []
        warnings: List[str] = []

        text = chunk.text.strip()

        # 1. Empty text.
        if not text:
            issues.append("Chunk text is empty or whitespace-only.")
            return {
                "is_valid": False,
                "issues": issues,
                "warnings": warnings,
                "chunk_id": chunk.id,
                "token_count": 0,
                "char_count": 0,
            }

        # 2. Minimum token count.
        MIN_TOKENS = 50
        if chunk.token_count < MIN_TOKENS:
            issues.append(
                f"Token count ({chunk.token_count}) is below minimum ({MIN_TOKENS}). "
                "May contain orphan sentences or insignificant content."
            )

        # 3. Maximum token count.
        MAX_TOKENS = 8000
        if chunk.token_count > MAX_TOKENS:
            issues.append(
                f"Token count ({chunk.token_count}) exceeds maximum ({MAX_TOKENS}). "
                "May exceed model context windows."
            )

        # 4. Orphan sentence — text does not end with sentence-ending punctuation.
        sentence_endings = {".", "!", "?", "؟", "!", "۔", "،"}
        if text[-1] not in sentence_endings:
            warnings.append(
                "Chunk does not end with sentence-ending punctuation. "
                "May be an orphan sentence fragment."
            )

        # 5. Excessive overlap ratio.
        overlap_text = chunk.metadata.get("overlap_text", "")
        if overlap_text:
            overlap_tokens = count_tokens(overlap_text)
            if chunk.token_count > 0:
                overlap_ratio = overlap_tokens / chunk.token_count
                if overlap_ratio > 0.5:
                    warnings.append(
                        f"Overlap ratio ({overlap_ratio:.1%}) exceeds 50%. "
                        "Consider reducing overlap_tokens or merging with adjacent chunk."
                    )

        # 6. Check for very short text with many metadata (likely a header-only chunk).
        if len(text) < 20 and chunk.token_count < 10:
            warnings.append(
                "Chunk is extremely short (< 20 chars). May be a header or fragment."
            )

        # 7. Check for repeated content within the chunk (possible duplication).
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) > 3:
            # Check if the first and last lines are identical (common PDF artifact).
            if lines[0] == lines[-1]:
                warnings.append(
                    "First and last lines of the chunk are identical. "
                    "Possible header/footer artifact from PDF extraction."
                )

        is_valid = len(issues) == 0

        return {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "chunk_id": chunk.id,
            "token_count": chunk.token_count,
            "char_count": chunk.char_count,
        }

    def validate_chunks_quality(
        self,
        chunks: List[TextChunk],
    ) -> Dict[str, Any]:
        """Validate all chunks and return an aggregate report.

        Args:
            chunks: List of :class:`TextChunk` instances.

        Returns:
            A report dictionary with:
            - ``total`` (int) — total chunks checked.
            - ``valid`` (int) — chunks with no issues.
            - ``invalid`` (int) — chunks with at least one issue.
            - ``issues`` (dict) — ``chunk_id → list of issue strings``.
            - ``warnings`` (dict) — ``chunk_id → list of warning strings``.
        """
        total = len(chunks)
        valid_count = 0
        all_issues: Dict[str, List[str]] = {}
        all_warnings: Dict[str, List[str]] = {}

        for chunk in chunks:
            result = self.validate_chunk_quality(chunk)
            if result["is_valid"]:
                valid_count += 1
            if result["issues"]:
                all_issues[chunk.id] = result["issues"]
            if result["warnings"]:
                all_warnings[chunk.id] = result["warnings"]

        report = {
            "total": total,
            "valid": valid_count,
            "invalid": total - valid_count,
            "issues": all_issues,
            "warnings": all_warnings,
        }

        self._logger.info(
            "validate_chunks_quality: %d/%d chunks valid, %d with warnings",
            valid_count,
            total,
            len(all_warnings),
        )
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _avg_chars_per_token(text: str) -> float:
        """Estimate average characters per token for a given text.

        Arabic text tends to have fewer characters per token (≈ 3.5)
        compared to English (≈ 4.0) due to tiktoken's BPE encoding.

        Args:
            text: Sample text to estimate from.

        Returns:
            Estimated average characters per token.
        """
        if not text:
            return 4.0

        # Check for Arabic proportion.
        arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        arabic_ratio = arabic_chars / max(len(text), 1)

        if arabic_ratio > 0.5:
            return 3.5
        if arabic_ratio > 0.2:
            return 3.75
        return 4.0

    @staticmethod
    def _clean_overlap_boundary(text: str) -> str:
        """Trim the overlap text to a clean sentence or word boundary.

        Tries, in order:

        1. Truncate at the last complete sentence (ending in ``.`` / ``!`` / ``?`` / ``؟``).
        2. Truncate at the last whitespace boundary.
        3. Return the text as-is if no good break point exists.

        Args:
            text: The overlap text to clean.

        Returns:
            Cleaned overlap text, or empty string if too short.
        """
        if not text or len(text) < 10:
            return ""

        # 1. Try sentence boundary.
        # Find the last sentence-ending punctuation followed by a space or end.
        last_sentence_match = -1
        for i, ch in enumerate(text):
            if ch in {".", "!", "?", "؟", "۔"}:
                # Make sure it's not an abbreviation or number (e.g., "Dr." or "3.5")
                if i + 1 < len(text) and text[i + 1].isspace():
                    last_sentence_match = i + 1
                elif i == len(text) - 1:
                    last_sentence_match = i + 1

        if last_sentence_match > 10:
            return text[:last_sentence_match].strip()

        # 2. Try word boundary.
        last_space = text.rfind(" ")
        if last_space > 10:
            return text[:last_space].strip()

        # 3. Return as-is.
        return text.strip() if len(text) > 5 else ""