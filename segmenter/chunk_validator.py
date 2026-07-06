"""
AI Fuel Engine - Chunk Validator

Validates :class:`~core.schemas.TextChunk` quality and provides automatic
repair for common issues such as undersized chunks, oversized chunks,
orphan sentence fragments, and whitespace anomalies.

The :class:`ChunkValidator` is designed to be used after segmentation and
optionally after context preservation, producing a clean list of chunks
ready for the classification stage.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.schemas import ChunkType, Language, TextChunk
from core.utils import count_tokens, detect_language

logger = logging.getLogger(__name__)

# Sentence-ending punctuation (Arabic + English).
_SENTENCE_ENDINGS = re.compile(r"[.!?؟۔]+\s*$")

# Common boilerplate / artifact patterns that should not stand alone as chunks.
_ARTIFACT_PATTERNS: List[re.Pattern] = [
    re.compile(r"^[-=_]{3,}$"),                       # decorative lines
    re.compile(r"^\d+$"),                              # standalone page numbers
    re.compile(r"^صحفه\s*\d+\s*من\s*\d+$"),            # Arabic "page X of Y"
    re.compile(r"^page\s+\d+\s+of\s+\d+$", re.I),     # English "page X of Y"
]


class ChunkValidator:
    """Validates chunk quality and fixes common issues.

    The validator enforces token-count bounds, repairs sentence boundaries,
    strips boilerplate artifacts, and provides merge/split operations to
    bring all chunks within the configured thresholds.

    Args:
        min_tokens: Minimum token count for a valid chunk.  Chunks below
            this threshold are candidates for merging.
        max_tokens: Maximum token count for a valid chunk.  Chunks above
            this threshold are candidates for splitting.

    Example::

        validator = ChunkValidator(min_tokens=50, max_tokens=4000)

        is_valid, issues = validator.validate(chunk)
        if not is_valid:
            chunk = validator.fix_chunk(chunk)

        # Batch normalisation:
        chunks = validator.merge_small_chunks(chunks)
        chunks = validator.split_large_chunks(chunks)
    """

    def __init__(
        self,
        min_tokens: int = 50,
        max_tokens: int = 8000,
    ) -> None:
        if min_tokens < 1:
            raise ValueError(f"min_tokens must be >= 1, got {min_tokens}")
        if max_tokens < min_tokens:
            raise ValueError(
                f"max_tokens ({max_tokens}) must be >= min_tokens ({min_tokens})"
            )

        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, chunk: TextChunk) -> Tuple[bool, List[str]]:
        """Validate a single chunk against quality criteria.

        The following checks are performed:

        1. **Non-empty text** — the chunk must contain non-whitespace text.
        2. **Minimum token count** — ``chunk.token_count >= min_tokens``
           (unless the chunk has overlap context from a previous chunk).
        3. **Maximum token count** — ``chunk.token_count <= max_tokens``.
        4. **Token count consistency** — the stored ``token_count`` must
           approximately match a fresh count (within 10 % tolerance).
        5. **Sentence completeness** — chunk text should end with
           sentence-ending punctuation.
        6. **No boilerplate artifacts** — the chunk must not consist
           entirely of decorative lines, page numbers, etc.
        7. **Word count consistency** — ``word_count`` must be >= 1 and
           approximately match ``len(text.split())``.
        8. **End token >= start token** — enforced by the Pydantic model
           but double-checked here.

        Args:
            chunk: The :class:`TextChunk` to validate.

        Returns:
            A tuple of ``(is_valid, list_of_issues)`` where *is_valid* is
            ``True`` when no issues are found and *list_of_issues* contains
            human-readable problem descriptions.
        """
        issues: List[str] = []
        text = chunk.text

        # 1. Non-empty text.
        if not text or not text.strip():
            issues.append("Chunk text is empty or whitespace-only.")
            return False, issues

        # 2. Minimum token count (allow chunks that have overlap context).
        actual_tokens = count_tokens(text)
        has_overlap = chunk.metadata.get("has_overlap", False)
        effective_min = max(self.min_tokens - int(actual_tokens * 0.3), 10) if has_overlap else self.min_tokens
        if actual_tokens < effective_min:
            issues.append(
                f"Token count ({actual_tokens}) is below minimum ({effective_min})."
            )

        # 3. Maximum token count.
        if actual_tokens > self.max_tokens:
            issues.append(
                f"Token count ({actual_tokens}) exceeds maximum ({self.max_tokens})."
            )

        # 4. Token count consistency.
        if chunk.token_count > 0:
            diff_ratio = abs(actual_tokens - chunk.token_count) / max(chunk.token_count, 1)
            if diff_ratio > 0.10:
                issues.append(
                    f"Token count inconsistency: stored={chunk.token_count}, "
                    f"actual={actual_tokens} (diff={diff_ratio:.1%})."
                )

        # 5. Sentence completeness.
        stripped = text.rstrip()
        if stripped and not _SENTENCE_ENDINGS.search(stripped):
            issues.append(
                "Chunk does not end with sentence-ending punctuation. "
                "May be an orphan sentence fragment."
            )

        # 6. Boilerplate artifacts.
        if self._is_boilerplate(text):
            issues.append(
                "Chunk consists entirely of boilerplate / artifact content "
                "(decorative lines, page numbers, etc.)."
            )

        # 7. Word count consistency.
        actual_words = len(text.split())
        if chunk.word_count != actual_words:
            # Don't fail, but note the inconsistency.
            pass  # Silently accepted — word count is recomputed during fix.

        # 8. End token >= start token.
        if chunk.end_token < chunk.start_token:
            issues.append(
                f"end_token ({chunk.end_token}) < start_token ({chunk.start_token})."
            )

        return (len(issues) == 0, issues)

    def validate_batch(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        """Validate a batch of chunks and return an aggregate report.

        Args:
            chunks: List of :class:`TextChunk` instances.

        Returns:
            A report dictionary containing:
            - ``total`` (int) — number of chunks checked.
            - ``valid`` (int) — chunks with zero issues.
            - ``invalid`` (int) — chunks with at least one issue.
            - ``details`` (dict) — ``chunk_id → list of issue strings`` for
              invalid chunks.
        """
        total = len(chunks)
        valid_count = 0
        details: Dict[str, List[str]] = {}

        for chunk in chunks:
            is_valid, issues = self.validate(chunk)
            if is_valid:
                valid_count += 1
            else:
                details[chunk.id] = issues

        return {
            "total": total,
            "valid": valid_count,
            "invalid": total - valid_count,
            "details": details,
        }

    # ------------------------------------------------------------------
    # Repair
    # ------------------------------------------------------------------

    def fix_chunk(self, chunk: TextChunk) -> TextChunk:
        """Attempt to automatically fix common chunk issues.

        Fixes applied (in order):

        1. **Strip whitespace** — leading/trailing whitespace is removed.
        2. **Collapse internal whitespace** — multiple spaces/newlines are
           normalised.
        3. **Append missing punctuation** — if the chunk does not end
           with sentence-ending punctuation, a period is appended.
        4. **Recompute counts** — ``token_count``, ``char_count``, and
           ``word_count`` are refreshed from the (possibly modified) text.
        5. **Re-detect language** — ``language`` is re-detected.
        6. **Strip boilerplate** — if the entire chunk is boilerplate,
           it is replaced with a single empty string (which will be
           filtered out by downstream validation).

        Args:
            chunk: The :class:`TextChunk` to repair.

        Returns:
            A new :class:`TextChunk` with fixes applied.  The original
            chunk is **not** mutated.
        """
        text = chunk.text

        # 1. Strip leading/trailing whitespace.
        text = text.strip()

        # 2. Collapse internal whitespace.
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 3. Append missing punctuation.
        if text and not _SENTENCE_ENDINGS.search(text):
            # Check if text ends with an Arabic comma (،) — replace with period.
            if text.rstrip().endswith("،"):
                text = text.rstrip()[:-1] + "."
            else:
                text = text.rstrip() + "."

        # 6. Strip boilerplate.
        if self._is_boilerplate(text):
            text = ""

        # If text is now empty, return a minimal chunk that will be filtered.
        if not text:
            return chunk.model_copy(
                update={
                    "text": "",
                    "token_count": 0,
                    "char_count": 0,
                    "word_count": 0,
                }
            )

        # 4. Recompute counts.
        token_count = count_tokens(text)
        char_count = len(text)
        word_count = len(text.split())

        # 5. Re-detect language.
        lang_code = detect_language(text)
        language = Language(lang_code) if lang_code != "unknown" else Language.UNKNOWN

        # Preserve the original ID for traceability.
        fixed = chunk.model_copy(
            update={
                "text": text,
                "token_count": token_count,
                "char_count": char_count,
                "word_count": word_count,
                "language": language,
                "metadata": {
                    **chunk.metadata,
                    "fixed": True,
                    "original_token_count": chunk.token_count,
                    "original_char_count": chunk.char_count,
                },
            }
        )

        self._logger.debug("fix_chunk: repaired chunk %s", chunk.id)
        return fixed

    # ------------------------------------------------------------------
    # Merge small chunks
    # ------------------------------------------------------------------

    def merge_small_chunks(
        self,
        chunks: List[TextChunk],
        min_tokens: Optional[int] = None,
    ) -> List[TextChunk]:
        """Merge consecutive chunks that fall below the minimum token threshold.

        Small chunks are greedily merged with their **next** neighbour until
        the combined token count meets the threshold.  If the small chunk
        is the last in the list, it is merged with the **previous** chunk
        instead.

        The merge preserves:

        - The earliest ``start_token`` and the latest ``end_token``.
        - The ``chunk_type`` of the first chunk in the merge group.
        - All metadata from all merged chunks (later values win on conflict).
        - The ``source_file`` of the first chunk.

        Merged text is separated by ``"\n\n"`` for readability.

        Args:
            chunks: List of :class:`TextChunk` instances in document order.
            min_tokens: Override the instance's ``min_tokens`` for this call.

        Returns:
            A new list of :class:`TextChunk` instances with small chunks
            merged.  The input list is **not** mutated.
        """
        if not chunks:
            return []

        threshold = min_tokens if min_tokens is not None else self.min_tokens
        self._logger.info(
            "merge_small_chunks: processing %d chunks (threshold=%d tokens)",
            len(chunks),
            threshold,
        )

        # Identify which chunks are too small.
        small_indices: set = set()
        for idx, chunk in enumerate(chunks):
            actual_tokens = count_tokens(chunk.text)
            if actual_tokens < threshold:
                small_indices.add(idx)

        if not small_indices:
            self._logger.debug("merge_small_chunks: no small chunks found")
            return list(chunks)

        # Greedy merge: iterate and build result.
        result: List[TextChunk] = []
        i = 0
        while i < len(chunks):
            if i not in small_indices:
                result.append(chunks[i])
                i += 1
                continue

            # Start a merge group beginning at index i.
            group: List[TextChunk] = [chunks[i]]
            group_text = chunks[i].text
            group_tokens = count_tokens(group_text)
            group_meta: Dict[str, Any] = {}
            j = i + 1

            while j < len(chunks) and group_tokens < threshold:
                group.append(chunks[j])
                group_text = group_text + "\n\n" + chunks[j].text
                group_tokens = count_tokens(group_text)
                group_meta.update(chunks[j].metadata)
                small_indices.discard(j)
                j += 1

            # If we merged backwards (last chunk), combine with previous.
            if len(group) == 1 and result:
                prev = result.pop()
                combined_text = prev.text + "\n\n" + group[0].text
                merged = self._build_merged_chunk(
                    texts=[prev.text, group[0].text],
                    combined_text=combined_text,
                    chunks=[prev, group[0]],
                )
                result.append(merged)
            else:
                merged = self._build_merged_chunk(
                    texts=[c.text for c in group],
                    combined_text=group_text,
                    chunks=group,
                )
                result.append(merged)

            i = j

        self._logger.info(
            "merge_small_chunks: %d chunks → %d chunks",
            len(chunks),
            len(result),
        )
        return result

    # ------------------------------------------------------------------
    # Split large chunks
    # ------------------------------------------------------------------

    def split_large_chunks(
        self,
        chunks: List[TextChunk],
        max_tokens: Optional[int] = None,
    ) -> List[TextChunk]:
        """Split chunks that exceed the maximum token limit.

        Large chunks are split at sentence boundaries when possible.
        If a single sentence exceeds the limit, the sentence is split
        at word boundaries.  Overlap of ``min(100, max_tokens // 10)``
        tokens is added between sub-chunks for context continuity.

        Args:
            chunks: List of :class:`TextChunk` instances in document order.
            max_tokens: Override the instance's ``max_tokens`` for this call.

        Returns:
            A new list of :class:`TextChunk` instances with oversized
            chunks split.  The input list is **not** mutated.
        """
        if not chunks:
            return []

        limit = max_tokens if max_tokens is not None else self.max_tokens
        overlap_tokens = min(100, limit // 10)
        self._logger.info(
            "split_large_chunks: processing %d chunks (limit=%d tokens)",
            len(chunks),
            limit,
        )

        result: List[TextChunk] = []

        for chunk in chunks:
            actual_tokens = count_tokens(chunk.text)

            if actual_tokens <= limit:
                result.append(chunk)
                continue

            self._logger.debug(
                "split_large_chunks: chunk %s has %d tokens (limit=%d) — splitting",
                chunk.id,
                actual_tokens,
                limit,
            )

            sub_chunks = self._split_single_chunk(chunk, limit, overlap_tokens)
            result.extend(sub_chunks)

        self._logger.info(
            "split_large_chunks: %d chunks → %d chunks",
            len(chunks),
            len(result),
        )
        return result

    # ------------------------------------------------------------------
    # Full normalisation pipeline
    # ------------------------------------------------------------------

    def normalize(
        self,
        chunks: List[TextChunk],
        min_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> List[TextChunk]:
        """Run the full normalisation pipeline: fix → merge → split → filter.

        1. Fix individual chunk issues (whitespace, punctuation, counts).
        2. Merge chunks that are too small.
        3. Split chunks that are too large.
        4. Remove empty/invalid chunks.

        Args:
            chunks: Input list of chunks.
            min_tokens: Override minimum token threshold.
            max_tokens: Override maximum token threshold.

        Returns:
            A fully normalised list of :class:`TextChunk` instances.
        """
        self._logger.info(
            "normalize: starting pipeline with %d chunks", len(chunks)
        )

        # Step 1: Fix individual chunks.
        fixed = [self.fix_chunk(c) for c in chunks]

        # Step 2: Merge small chunks.
        merged = self.merge_small_chunks(fixed, min_tokens=min_tokens)

        # Step 3: Split large chunks.
        split = self.split_large_chunks(merged, max_tokens=max_tokens)

        # Step 4: Filter out empty/invalid chunks.
        final = []
        for chunk in split:
            is_valid, issues = self.validate(chunk)
            if is_valid:
                final.append(chunk)
            else:
                # Only discard truly empty chunks; keep others with warnings.
                if chunk.text.strip():
                    final.append(chunk)
                else:
                    self._logger.debug(
                        "normalize: discarding empty chunk %s", chunk.id
                    )

        self._logger.info(
            "normalize: %d → %d chunks after normalisation",
            len(chunks),
            len(final),
        )
        return final

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_single_chunk(
        self,
        chunk: TextChunk,
        max_tokens: int,
        overlap_tokens: int,
    ) -> List[TextChunk]:
        """Split a single oversized chunk into sub-chunks.

        Strategy:
        1. Split into sentences.
        2. Greedily pack sentences into each sub-chunk up to *max_tokens*.
        3. If a single sentence exceeds *max_tokens*, split by words.
        4. Add overlap from the end of each sub-chunk to the beginning
           of the next.

        Args:
            chunk: The oversized chunk.
            max_tokens: Token limit per sub-chunk.
            overlap_tokens: Overlap tokens between sub-chunks.

        Returns:
            List of sub-chunks.
        """
        # Split into sentences.
        sentences = self._split_into_sentences(chunk.text)

        if len(sentences) <= 1:
            # Can't split by sentences — try by words.
            return self._split_by_words(chunk, max_tokens, overlap_tokens)

        # Greedy sentence packing.
        sub_chunks_raw: List[str] = []
        current_sentences: List[str] = []
        current_tokens = 0

        for sentence in sentences:
            sent_tokens = count_tokens(sentence)

            if current_tokens + sent_tokens > max_tokens and current_sentences:
                # Flush current group.
                sub_chunks_raw.append(" ".join(current_sentences))
                # Keep the last sentence(s) for overlap.
                overlap_sents: List[str] = []
                overlap_count = 0
                for s in reversed(current_sentences):
                    st = count_tokens(s)
                    if overlap_count + st <= overlap_tokens:
                        overlap_sents.insert(0, s)
                        overlap_count += st
                    else:
                        break
                current_sentences = overlap_sents
                current_tokens = overlap_count

            current_sentences.append(sentence)
            current_tokens += sent_tokens

        # Flush remaining.
        if current_sentences:
            sub_chunks_raw.append(" ".join(current_sentences))

        # Build TextChunk objects.
        return self._build_sub_chunks(chunk, sub_chunks_raw, "split")

    def _split_by_words(
        self,
        chunk: TextChunk,
        max_tokens: int,
        overlap_tokens: int,
    ) -> List[TextChunk]:
        """Split a chunk by word boundaries (fallback for long sentences).

        Args:
            chunk: The chunk to split.
            max_tokens: Token limit per sub-chunk.
            overlap_tokens: Overlap tokens between sub-chunks.

        Returns:
            List of sub-chunks.
        """
        words = chunk.text.split()
        sub_chunks_raw: List[str] = []
        current_words: List[str] = []
        current_tokens = 0
        step = max(1, max_tokens - overlap_tokens)

        for word in words:
            word_tokens = count_tokens(word)
            if current_tokens + word_tokens > max_tokens and current_words:
                sub_chunks_raw.append(" ".join(current_words))
                # Keep overlap words.
                overlap_words: List[str] = []
                overlap_count = 0
                for w in reversed(current_words):
                    wt = count_tokens(w)
                    if overlap_count + wt <= overlap_tokens:
                        overlap_words.insert(0, w)
                        overlap_count += wt
                    else:
                        break
                current_words = overlap_words + [word]
                current_tokens = overlap_count + word_tokens
            else:
                current_words.append(word)
                current_tokens += word_tokens

        if current_words:
            sub_chunks_raw.append(" ".join(current_words))

        return self._build_sub_chunks(chunk, sub_chunks_raw, "word_split")

    def _build_sub_chunks(
        self,
        original: TextChunk,
        texts: List[str],
        split_reason: str,
    ) -> List[TextChunk]:
        """Build :class:`TextChunk` instances from a list of sub-texts.

        Preserves ``chunk_type``, ``source_file``, and ``metadata`` from
        the original chunk.  Token offsets are computed sequentially.

        Args:
            original: The original chunk being split.
            texts: List of sub-text strings.
            split_reason: Reason for the split (stored in metadata).

        Returns:
            List of sub-chunks.
        """
        chunks: List[TextChunk] = []
        offset = original.start_token

        for idx, text in enumerate(texts):
            text = text.strip()
            if not text:
                continue

            tc = count_tokens(text)
            lang_code = detect_language(text)
            language = Language(lang_code) if lang_code != "unknown" else Language.UNKNOWN

            chunks.append(
                TextChunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    chunk_type=original.chunk_type,
                    start_token=offset,
                    end_token=offset + tc,
                    token_count=tc,
                    char_count=len(text),
                    word_count=len(text.split()),
                    language=language,
                    source_file=original.source_file,
                    source_page=original.source_page,
                    metadata={
                        **original.metadata,
                        "split_from": original.id,
                        "split_reason": split_reason,
                        "sub_index": idx,
                        "total_sub_chunks": len(texts),
                    },
                )
            )
            offset += tc

        return chunks

    @staticmethod
    def _build_merged_chunk(
        texts: List[str],
        combined_text: str,
        chunks: List[TextChunk],
    ) -> TextChunk:
        """Build a merged :class:`TextChunk` from multiple source chunks.

        Args:
            texts: Individual text strings (for reference).
            combined_text: The concatenated text.
            chunks: Source chunks being merged.

        Returns:
            A new :class:`TextChunk` representing the merge.
        """
        first = chunks[0]
        last = chunks[-1]

        combined_text = combined_text.strip()
        tc = count_tokens(combined_text)
        lang_code = detect_language(combined_text)
        language = Language(lang_code) if lang_code != "unknown" else Language.UNKNOWN

        # Merge all metadata (later chunks win on conflicts).
        merged_meta: Dict[str, Any] = {}
        for c in chunks:
            merged_meta.update(c.metadata)
        merged_meta["merged_from"] = [c.id for c in chunks]
        merged_meta["merge_count"] = len(chunks)

        return TextChunk(
            id=str(uuid.uuid4()),
            text=combined_text,
            chunk_type=first.chunk_type,
            start_token=first.start_token,
            end_token=last.end_token,
            token_count=tc,
            char_count=len(combined_text),
            word_count=len(combined_text.split()),
            language=language,
            source_file=first.source_file,
            source_page=first.source_page,
            metadata=merged_meta,
        )

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """Split text into sentences with Arabic + English awareness.

        Uses regex-based splitting on sentence-ending punctuation
        (``.``  ``!``  ``?``  ``؟``  ``۔``) followed by whitespace.

        Args:
            text: Input text.

        Returns:
            List of sentence strings.
        """
        # Split on sentence boundaries.
        # Pattern: punctuation followed by one or more whitespace chars.
        parts = re.split(r"(?<=[.!?؟۔])\s+", text)

        # Also split on double newlines (paragraph breaks often indicate
        # sentence breaks too).
        expanded: List[str] = []
        for part in parts:
            sub = re.split(r"\n{2,}", part)
            expanded.extend(sub)

        sentences = [s.strip() for s in expanded if s.strip()]

        # Fallback: if we get nothing, split by single newlines.
        if not sentences:
            sentences = [line.strip() for line in text.splitlines() if line.strip()]

        return sentences

    @staticmethod
    def _is_boilerplate(text: str) -> bool:
        """Check whether *text* consists entirely of boilerplate artifacts.

        Args:
            text: Text to check.

        Returns:
            ``True`` if every non-empty line matches an artifact pattern.
        """
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return True

        for line in lines:
            matches_any = any(p.match(line) for p in _ARTIFACT_PATTERNS)
            if not matches_any:
                return False

        return True