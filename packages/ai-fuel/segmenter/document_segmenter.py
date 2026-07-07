"""
AI Fuel Engine - Document Segmenter

Advanced document segmentation for AI training data preparation.  Splits raw
text into :class:`~core.schemas.TextChunk` instances using one of four
strategies:

1. **size**     — Fixed token windows with overlap.
2. **semantic** — Sentence similarity grouping at topic boundaries.
3. **structure** — Markdown / heading / list / paragraph-aware splitting.
4. **hybrid**   — Combines structural → size → semantic for best results.

All methods handle Arabic and English text transparently via the
:mod:`core.utils` helpers.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.config import AIFuelConfig
from core.schemas import ChunkType, Language, TextChunk
from core.utils import calculate_similarity, clean_ocr_artifacts, count_tokens, detect_language

logger = logging.getLogger(__name__)


# ======================================================================
# Internal helpers
# ======================================================================

# Sentence splitters — handle Arabic (،.؟!) and English (.?!) punctuation.
_SENTENCE_END_RE = re.compile(
    r"(?<=[.؟!])\s+|(?<=[,،])\s+(?=[أاابتثجحخدذرزسشصضطظعغفقكلمنهوية])"
)

# Headings: markdown-style (## Title) and plain ALL-CAPS lines.
_HEADING_RE = re.compile(
    r"^(#{1,6})\s+.+|^[A-Z\u0621-\u064A][A-Z\u0621-\u064A\s\-_]{2,}$",
    re.MULTILINE,
)

# Numbered list items (Arabic & Western numerals).
_NUMBERED_LIST_RE = re.compile(
    r"^\s*(?:\d+[\.\)、]|[\u0661-\u066A][\.\)、])\s+", re.MULTILINE
)

# Bullet list items (Arabic & Western bullets).
_BULLET_LIST_RE = re.compile(
    r"^\s*[-*•‣▸▫]\s+", re.MULTILINE
)


def _split_sentences(text: str) -> List[str]:
    """Split *text* into a list of sentences.

    Handles both Arabic and English sentence-ending punctuation.  Empty
    sentences and pure-whitespace segments are filtered out.

    Args:
        text: Input text.

    Returns:
        List of non-empty sentence strings.
    """
    if not text or not text.strip():
        return []

    # First try splitting on common sentence boundaries
    raw_parts = _SENTENCE_END_RE.split(text)

    # Also split on newlines that likely indicate sentence breaks
    expanded: List[str] = []
    for part in raw_parts:
        sub_parts = re.split(r"\n{2,}", part)
        expanded.extend(sub_parts)

    sentences: List[str] = []
    for s in expanded:
        s = s.strip()
        if s:
            sentences.append(s)

    # Fallback: if no sentences found, split on newlines
    if not sentences and text.strip():
        sentences = [line.strip() for line in text.splitlines() if line.strip()]

    return sentences


def _detect_chunk_type(method: str) -> ChunkType:
    """Map a method name string to its :class:`ChunkType` enum variant.

    Args:
        method: One of ``"size"``, ``"semantic"``, ``"structure"``, ``"hybrid"``.

    Returns:
        The corresponding :class:`ChunkType`.

    Raises:
        ValueError: If *method* is unrecognised.
    """
    mapping = {
        "size": ChunkType.SIZE_BASED,
        "semantic": ChunkType.SEMANTIC,
        "structure": ChunkType.STRUCTURAL,
        "hybrid": ChunkType.STRUCTURAL,  # hybrid uses structural as the primary type
    }
    try:
        return mapping[method]
    except KeyError as exc:
        raise ValueError(
            f"Unknown segmentation method {method!r}. "
            f"Choose from: {', '.join(repr(m) for m in mapping)}"
        ) from exc


def _build_chunk(
    text: str,
    chunk_type: ChunkType,
    start_token: int,
    end_token: int,
    token_count: int,
    source_file: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TextChunk:
    """Factory for building a fully-populated :class:`TextChunk`.

    Automatically computes ``char_count``, ``word_count``, and ``language``
    from the text content.

    Args:
        text: The chunk's raw text.
        chunk_type: Strategy used to produce this chunk.
        start_token: Token offset at which this chunk starts in the source.
        end_token: Token offset at which this chunk ends.
        token_count: Number of tokens in this chunk.
        source_file: Optional originating file name.
        metadata: Optional key-value metadata.

    Returns:
        A ready-to-use :class:`TextChunk` instance.
    """
    lang_code = detect_language(text)
    language = Language(lang_code) if lang_code != "unknown" else Language.UNKNOWN

    return TextChunk(
        id=str(uuid.uuid4()),
        text=text,
        chunk_type=chunk_type,
        start_token=start_token,
        end_token=end_token,
        token_count=token_count,
        char_count=len(text),
        word_count=len(text.split()),
        language=language,
        source_file=source_file,
        metadata=metadata or {},
    )


# ======================================================================
# DocumentSegmenter
# ======================================================================


class DocumentSegmenter:
    """Advanced document segmentation for AI training data preparation.

    Supports four segmentation strategies — size-based, semantic,
    structural, and hybrid — and integrates with the pipeline's
    :class:`~core.schemas.TextChunk` schema and
    :class:`~core.config.AIFuelConfig` configuration.

    Args:
        config: Optional pipeline configuration.  When ``None``, default
            :class:`~core.config.AIFuelConfig` values are used.

    Example::

        seg = DocumentSegmenter()
        chunks = seg.segment(document_text, method="hybrid")
    """

    def __init__(self, config: Optional[AIFuelConfig] = None) -> None:
        self.config = config or AIFuelConfig()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def segment(
        self,
        text: str,
        method: str = "size",
        source_file: Optional[str] = None,
    ) -> List[TextChunk]:
        """Main entry point — route to the appropriate segmentation method.

        Args:
            text: The source document text to segment.
            method: Segmentation strategy.  One of ``"size"``, ``"semantic"``,
                ``"structure"``, or ``"hybrid"``.
            source_file: Optional file name for traceability.

        Returns:
            A list of :class:`TextChunk` instances.

        Raises:
            ValueError: If *method* is not recognised.
        """
        if not text or not text.strip():
            self._logger.warning("segment() called with empty text — returning []")
            return []

        # Clean OCR artifacts before any processing
        text = clean_ocr_artifacts(text)

        self._logger.info(
            "Segmenting text (%d chars, %d tokens) with method=%r",
            len(text),
            count_tokens(text),
            method,
        )

        dispatch = {
            "size": self.segment_by_size,
            "semantic": self.segment_by_semantic,
            "structure": self.segment_by_structure,
            "hybrid": self.segment_hybrid,
        }

        if method not in dispatch:
            raise ValueError(
                f"Unknown method {method!r}. Choose from: {', '.join(repr(m) for m in dispatch)}"
            )

        chunks = dispatch[method](text, source_file=source_file)

        self._logger.info("Produced %d chunks", len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # 1. Size-based segmentation
    # ------------------------------------------------------------------

    def segment_by_size(
        self,
        text: str,
        max_tokens: Optional[int] = None,
        overlap: Optional[int] = None,
        source_file: Optional[str] = None,
    ) -> List[TextChunk]:
        """Token-based segmentation with configurable overlap.

        Splits *text* into windows of at most *max_tokens* tokens, keeping
        the last *overlap* tokens of each window as a prefix for the next
        window.  This preserves context across chunk boundaries.

        Arabic text is handled correctly via the
        :func:`~core.utils.count_tokens` utility, which uses ``tiktoken``
        when available and a language-aware heuristic otherwise.

        Args:
            text: Source document text.
            max_tokens: Maximum tokens per chunk.  Defaults to
                ``config.max_tokens`` (4000).
            overlap: Overlapping tokens between consecutive chunks.  Defaults
                to ``config.overlap_tokens`` (200).
            source_file: Optional originating file name.

        Returns:
            List of :class:`TextChunk` instances with ``chunk_type=SIZE_BASED``.
        """
        max_tokens = max_tokens or self.config.max_tokens
        overlap = overlap or self.config.overlap_tokens

        if overlap >= max_tokens:
            raise ValueError(
                f"overlap ({overlap}) must be less than max_tokens ({max_tokens})"
            )

        total_tokens = count_tokens(text)
        if total_tokens <= max_tokens:
            # The entire text fits in one chunk
            return [
                _build_chunk(
                    text=text,
                    chunk_type=ChunkType.SIZE_BASED,
                    start_token=0,
                    end_token=total_tokens,
                    token_count=total_tokens,
                    source_file=source_file,
                    metadata={"segmentation_method": "size_based", "chunk_index": 0},
                )
            ]

        chunks: List[TextChunk] = []
        # We operate on a word-level approximation for splitting, then measure
        # token counts precisely.  This is because tiktoken encodes
        # unpredictably at sub-word boundaries.
        words = text.split()
        step = max(1, max_tokens - overlap)

        chunk_index = 0
        start_word = 0

        while start_word < len(words):
            end_word = min(start_word + max_tokens * 2, len(words))  # generous upper bound

            # Binary-search for the actual end word that fits in max_tokens
            best_end = start_word + 1  # at least one word
            for candidate_end in range(start_word + 1, end_word + 1):
                candidate_text = " ".join(words[start_word:candidate_end])
                if count_tokens(candidate_text) <= max_tokens:
                    best_end = candidate_end
                else:
                    break

            chunk_text = " ".join(words[start_word:best_end])
            token_count = count_tokens(chunk_text)

            # Compute the global token offset for this chunk
            preceding_text = " ".join(words[:start_word])
            start_token = count_tokens(preceding_text)
            end_token = start_token + token_count

            chunks.append(
                _build_chunk(
                    text=chunk_text,
                    chunk_type=ChunkType.SIZE_BASED,
                    start_token=start_token,
                    end_token=end_token,
                    token_count=token_count,
                    source_file=source_file,
                    metadata={
                        "segmentation_method": "size_based",
                        "chunk_index": chunk_index,
                        "max_tokens": max_tokens,
                        "overlap": overlap,
                    },
                )
            )

            chunk_index += 1

            # Advance by the step size (max_tokens - overlap) worth of words
            # We need to find how many words correspond to `step` tokens
            overlap_words = max(1, best_end - start_word - step)
            if overlap_words < 1:
                overlap_words = 1
            start_word = best_end - overlap_words

            # Safety: ensure progress
            if start_word <= best_end - max_tokens * 2:
                start_word = best_end

        return chunks

    # ------------------------------------------------------------------
    # 2. Semantic segmentation
    # ------------------------------------------------------------------

    def segment_by_semantic(
        self,
        text: str,
        similarity_threshold: float = 0.75,
        source_file: Optional[str] = None,
    ) -> List[TextChunk]:
        """Semantic segmentation — split at natural topic boundaries.

        The algorithm works in three phases:

        1. Split *text* into individual sentences.
        2. Compute pairwise cosine similarity between consecutive sentences.
        3. Group consecutive sentences whose similarity exceeds
           *similarity_threshold*, and split whenever a topic shift is
           detected.
        4. Merge groups that are too small (below ``config.min_chunk_tokens``).

        Similarity is computed using the bag-of-words cosine similarity
        from :func:`~core.utils.calculate_similarity`.  For production
        deployments with sentence-transformers, replace the call site
        with a proper embedding model.

        Args:
            text: Source document text.
            similarity_threshold: Minimum cosine similarity between
                consecutive sentences to consider them part of the same
                topic group.  Defaults to ``0.75``.
            source_file: Optional originating file name.

        Returns:
            List of :class:`TextChunk` instances with ``chunk_type=SEMANTIC``.
        """
        sentences = _split_sentences(text)

        if not sentences:
            return []
        if len(sentences) == 1:
            tok_count = count_tokens(sentences[0])
            return [
                _build_chunk(
                    text=sentences[0],
                    chunk_type=ChunkType.SEMANTIC,
                    start_token=0,
                    end_token=tok_count,
                    token_count=tok_count,
                    source_file=source_file,
                    metadata={"segmentation_method": "semantic", "chunk_index": 0},
                )
            ]

        # Phase 1: Compute consecutive similarities and detect topic breaks.
        breaks: List[int] = [0]  # always break at the start
        for i in range(1, len(sentences)):
            sim = calculate_similarity(sentences[i - 1], sentences[i])
            if sim < similarity_threshold:
                breaks.append(i)

        breaks.append(len(sentences))  # always break at the end

        # Phase 2: Build preliminary groups.
        groups: List[List[str]] = []
        for i in range(len(breaks) - 1):
            group = sentences[breaks[i] : breaks[i + 1]]
            if group:
                groups.append(group)

        # Phase 3: Merge small groups with their neighbours.
        min_tokens = self.config.min_chunk_tokens
        merged_groups = self._merge_small_groups(groups, min_tokens)

        # Phase 4: Build TextChunk objects.
        chunks: List[TextChunk] = []
        global_token_offset = 0

        for idx, group in enumerate(merged_groups):
            group_text = " ".join(group)
            tok_count = count_tokens(group_text)

            chunks.append(
                _build_chunk(
                    text=group_text,
                    chunk_type=ChunkType.SEMANTIC,
                    start_token=global_token_offset,
                    end_token=global_token_offset + tok_count,
                    token_count=tok_count,
                    source_file=source_file,
                    metadata={
                        "segmentation_method": "semantic",
                        "chunk_index": idx,
                        "similarity_threshold": similarity_threshold,
                        "sentence_count": len(group),
                    },
                )
            )
            global_token_offset += tok_count

        return chunks

    def _merge_small_groups(
        self,
        groups: List[List[str]],
        min_tokens: int,
    ) -> List[List[str]]:
        """Merge groups whose token count is below *min_tokens*.

        Small groups are merged with the *next* group when possible to keep
        related content together.  If the small group is the last one, it
        is merged with the *previous* group instead.

        Args:
            groups: List of sentence groups.
            min_tokens: Minimum token count for a standalone group.

        Returns:
            A (potentially shorter) list of merged groups.
        """
        if not groups:
            return groups

        # Compute token counts for each group.
        group_tokens = [count_tokens(" ".join(g)) for g in groups]

        merged: List[List[str]] = []
        i = 0
        while i < len(groups):
            if group_tokens[i] >= min_tokens or i == len(groups) - 1:
                # Group is large enough, or it's the last one.
                # If it's the last one and too small, merge with previous.
                if (
                    i == len(groups) - 1
                    and group_tokens[i] < min_tokens
                    and merged
                ):
                    merged[-1].extend(groups[i])
                else:
                    merged.append(groups[i])
                i += 1
            else:
                # Try to merge with the next group.
                if i + 1 < len(groups):
                    combined = groups[i] + groups[i + 1]
                    merged.append(combined)
                    # Update token count for the combined group if we need
                    # to check further merges.
                    if i + 2 < len(groups):
                        group_tokens[i + 2]  # noqa: B018 — just bounds check
                    i += 2
                else:
                    # No next group — merge with previous.
                    if merged:
                        merged[-1].extend(groups[i])
                    else:
                        merged.append(groups[i])
                    i += 1

        return merged

    # ------------------------------------------------------------------
    # 3. Structural segmentation
    # ------------------------------------------------------------------

    def segment_by_structure(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> List[TextChunk]:
        """Structure-aware segmentation using headers, paragraphs, and lists.

        The algorithm detects:

        - **Markdown headings** (``#``, ``##``, …, ``######``).
        - **Numbered list items** (Arabic & Western numerals).
        - **Bullet list items** (``-``, ``*``, ``•``, …).
        - **Paragraph boundaries** (double newlines).

        Each structural section is kept as a single chunk, with the heading
        (if present) included at the top of its section.  Chunks that
        exceed ``config.max_tokens`` are further sub-divided by paragraph
        boundaries.

        Args:
            text: Source document text (ideally Markdown or similarly
                structured content).
            source_file: Optional originating file name.

        Returns:
            List of :class:`TextChunk` instances with ``chunk_type=STRUCTURAL``.
        """
        lines = text.split("\n")
        sections: List[Dict[str, Any]] = []
        current_heading: Optional[str] = None
        current_lines: List[str] = []
        max_tokens = self.config.max_tokens

        def _flush() -> None:
            nonlocal current_heading, current_lines
            if current_lines:
                section_text = "\n".join(current_lines).strip()
                if section_text:
                    heading_prefix = f"{current_heading}\n" if current_heading else ""
                    sections.append({
                        "heading": current_heading,
                        "text": heading_prefix + section_text,
                    })
                current_lines = []
                current_heading = None

        for line in lines:
            stripped = line.strip()
            is_heading = bool(re.match(r"^#{1,6}\s+", stripped))
            is_heading |= bool(
                re.match(r"^[A-Z\u0621-\u064A][A-Z\u0621-\u064A\s\-_]{4,}$", stripped)
                and len(stripped) < 80
            )

            if is_heading:
                _flush()
                current_heading = stripped
            else:
                current_lines.append(line)

        _flush()

        # Build chunks — sub-divide large sections.
        chunks: List[TextChunk] = []
        global_token_offset = 0

        for idx, section in enumerate(sections):
            section_text = section["text"]
            section_tokens = count_tokens(section_text)

            if section_tokens <= max_tokens:
                chunks.append(
                    _build_chunk(
                        text=section_text,
                        chunk_type=ChunkType.STRUCTURAL,
                        start_token=global_token_offset,
                        end_token=global_token_offset + section_tokens,
                        token_count=section_tokens,
                        source_file=source_file,
                        metadata={
                            "segmentation_method": "structural",
                            "chunk_index": idx,
                            "heading": section["heading"],
                        },
                    )
                )
                global_token_offset += section_tokens
            else:
                # Sub-divide by paragraph.
                sub_chunks = self._subdivide_by_paragraphs(
                    section_text, max_tokens, global_token_offset, idx, source_file, section["heading"]
                )
                for sc in sub_chunks:
                    global_token_offset = sc.end_token
                chunks.extend(sub_chunks)

        return chunks

    def _subdivide_by_paragraphs(
        self,
        text: str,
        max_tokens: int,
        base_token_offset: int,
        base_index: int,
        source_file: Optional[str],
        heading: Optional[str],
    ) -> List[TextChunk]:
        """Split a large section into paragraph-based sub-chunks.

        Paragraphs (double-newline separated blocks) are grouped until
        the token limit is approached.

        Args:
            text: The full section text.
            max_tokens: Maximum tokens per sub-chunk.
            base_token_offset: Token offset of the section start.
            base_index: Chunk index for metadata.
            source_file: Optional originating file name.
            heading: Section heading for metadata.

        Returns:
            List of sub-chunks.
        """
        paragraphs = re.split(r"\n{2,}", text)
        chunks: List[TextChunk] = []
        current_paras: List[str] = []
        current_tokens = 0
        sub_idx = 0
        offset = base_token_offset

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_tokens = count_tokens(para)

            if current_tokens + para_tokens > max_tokens and current_paras:
                # Flush current group.
                group_text = "\n\n".join(current_paras)
                tc = count_tokens(group_text)
                chunks.append(
                    _build_chunk(
                        text=group_text,
                        chunk_type=ChunkType.STRUCTURAL,
                        start_token=offset,
                        end_token=offset + tc,
                        token_count=tc,
                        source_file=source_file,
                        metadata={
                            "segmentation_method": "structural",
                            "chunk_index": base_index,
                            "sub_index": sub_idx,
                            "heading": heading,
                        },
                    )
                )
                offset += tc
                sub_idx += 1
                current_paras = [para]
                current_tokens = para_tokens
            else:
                current_paras.append(para)
                current_tokens += para_tokens

        # Flush remaining.
        if current_paras:
            group_text = "\n\n".join(current_paras)
            tc = count_tokens(group_text)
            chunks.append(
                _build_chunk(
                    text=group_text,
                    chunk_type=ChunkType.STRUCTURAL,
                    start_token=offset,
                    end_token=offset + tc,
                    token_count=tc,
                    source_file=source_file,
                    metadata={
                        "segmentation_method": "structural",
                        "chunk_index": base_index,
                        "sub_index": sub_idx,
                        "heading": heading,
                    },
                )
            )

        return chunks

    # ------------------------------------------------------------------
    # 4. Hybrid segmentation
    # ------------------------------------------------------------------

    def segment_hybrid(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> List[TextChunk]:
        """Combine structural, size, and semantic segmentation for optimal results.

        The hybrid pipeline proceeds in three stages:

        1. **Structural pass** — Split by headings, lists, and paragraphs.
        2. **Size enforcement** — Any chunk exceeding ``config.max_tokens``
           is further split using size-based segmentation.
        3. **Semantic refinement** — Within the size-limited chunks, detect
           topic boundaries and split when consecutive segments have low
           similarity, provided the resulting sub-chunks still meet the
           minimum token threshold.

        This approach preserves the document's natural structure while
        ensuring all chunks respect the token budget.

        Args:
            text: Source document text.
            source_file: Optional originating file name.

        Returns:
            List of :class:`TextChunk` instances.
        """
        self._logger.info("Hybrid segmentation: starting structural pass")

        # Stage 1: Structural segmentation.
        chunks = self.segment_by_structure(text, source_file=source_file)

        # Stage 2: Size enforcement — split oversized chunks.
        max_tokens = self.config.max_tokens
        final_chunks: List[TextChunk] = []

        for chunk in chunks:
            if chunk.token_count > max_tokens:
                self._logger.debug(
                    "Hybrid: chunk %s exceeds %d tokens (%d) — sub-splitting",
                    chunk.id,
                    max_tokens,
                    chunk.token_count,
                )
                sub_chunks = self._hybrid_subsplit(chunk, max_tokens)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)

        # Stage 3: Semantic refinement on larger chunks.
        similarity_threshold = 0.75
        refined: List[TextChunk] = []

        for chunk in final_chunks:
            # Only apply semantic splitting to chunks that are large enough
            # to contain multiple sentences.
            if chunk.token_count > self.config.min_chunk_tokens * 3:
                semantic_chunks = self._semantic_refine(chunk, similarity_threshold)
                if len(semantic_chunks) > 1:
                    self._logger.debug(
                        "Hybrid: semantic refinement split chunk %s into %d parts",
                        chunk.id,
                        len(semantic_chunks),
                    )
                    refined.extend(semantic_chunks)
                else:
                    refined.append(chunk)
            else:
                refined.append(chunk)

        # Update metadata to reflect hybrid method.
        for idx, chunk in enumerate(refined):
            chunk.metadata["segmentation_method"] = "hybrid"
            chunk.metadata["chunk_index"] = idx

        return refined

    def _hybrid_subsplit(
        self,
        chunk: TextChunk,
        max_tokens: int,
    ) -> List[TextChunk]:
        """Sub-split an oversized chunk into size-based sub-chunks.

        Uses paragraph boundaries where possible, falling back to
        sentence boundaries, and finally to word boundaries.

        Args:
            chunk: The oversized chunk to split.
            max_tokens: Maximum tokens per sub-chunk.

        Returns:
            List of sub-chunks.
        """
        text = chunk.text

        # Try paragraph-level splitting first.
        paragraphs = re.split(r"\n{2,}", text)
        sub_chunks: List[TextChunk] = []
        current_paras: List[str] = []
        current_tokens = 0
        base_offset = chunk.start_token

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_tokens = count_tokens(para)

            if current_tokens + para_tokens > max_tokens and current_paras:
                group_text = "\n\n".join(current_paras)
                tc = count_tokens(group_text)
                sub_chunks.append(
                    _build_chunk(
                        text=group_text,
                        chunk_type=ChunkType.STRUCTURAL,
                        start_token=base_offset,
                        end_token=base_offset + tc,
                        token_count=tc,
                        source_file=chunk.source_file,
                        metadata={
                            **chunk.metadata,
                            "sub_split": True,
                        },
                    )
                )
                base_offset += tc
                current_paras = []
                current_tokens = 0

            # If a single paragraph exceeds max_tokens, split by sentences.
            if para_tokens > max_tokens:
                sentences = _split_sentences(para)
                sent_buffer: List[str] = []
                sent_tokens = 0

                for sent in sentences:
                    st = count_tokens(sent)
                    if sent_tokens + st > max_tokens and sent_buffer:
                        group_text = " ".join(sent_buffer)
                        tc = count_tokens(group_text)
                        sub_chunks.append(
                            _build_chunk(
                                text=group_text,
                                chunk_type=ChunkType.SIZE_BASED,
                                start_token=base_offset,
                                end_token=base_offset + tc,
                                token_count=tc,
                                source_file=chunk.source_file,
                                metadata={**chunk.metadata, "sub_split": True},
                            )
                        )
                        base_offset += tc
                        sent_buffer = []
                        sent_tokens = 0
                    sent_buffer.append(sent)
                    sent_tokens += st

                if sent_buffer:
                    group_text = " ".join(sent_buffer)
                    tc = count_tokens(group_text)
                    sub_chunks.append(
                        _build_chunk(
                            text=group_text,
                            chunk_type=ChunkType.SIZE_BASED,
                            start_token=base_offset,
                            end_token=base_offset + tc,
                            token_count=tc,
                            source_file=chunk.source_file,
                            metadata={**chunk.metadata, "sub_split": True},
                        )
                    )
                    base_offset += tc
            else:
                current_paras.append(para)
                current_tokens += para_tokens

        # Flush remaining paragraphs.
        if current_paras:
            group_text = "\n\n".join(current_paras)
            tc = count_tokens(group_text)
            sub_chunks.append(
                _build_chunk(
                    text=group_text,
                    chunk_type=ChunkType.STRUCTURAL,
                    start_token=base_offset,
                    end_token=base_offset + tc,
                    token_count=tc,
                    source_file=chunk.source_file,
                    metadata={**chunk.metadata, "sub_split": True},
                )
            )

        return sub_chunks

    def _semantic_refine(
        self,
        chunk: TextChunk,
        similarity_threshold: float,
    ) -> List[TextChunk]:
        """Apply semantic boundary detection within a single chunk.

        Splits the chunk at points where consecutive sentences have low
        similarity, but only if both resulting parts meet the minimum
        token threshold.

        Args:
            chunk: The chunk to refine.
            similarity_threshold: Cosine similarity threshold for grouping.

        Returns:
            Original chunk (if no split), or a list of refined sub-chunks.
        """
        sentences = _split_sentences(chunk.text)

        if len(sentences) < 3:
            return [chunk]

        # Find break points.
        breaks: List[int] = [0]
        for i in range(1, len(sentences)):
            sim = calculate_similarity(sentences[i - 1], sentences[i])
            if sim < similarity_threshold:
                breaks.append(i)
        breaks.append(len(sentences))

        # Build candidate groups.
        groups: List[List[str]] = []
        for i in range(len(breaks) - 1):
            group = sentences[breaks[i] : breaks[i + 1]]
            if group:
                groups.append(group)

        # Check that groups meet minimum token threshold.
        min_tokens = self.config.min_chunk_tokens
        valid_groups = self._merge_small_groups(groups, min_tokens)

        if len(valid_groups) <= 1:
            return [chunk]

        # Build sub-chunks.
        result: List[TextChunk] = []
        offset = chunk.start_token

        for group in valid_groups:
            group_text = " ".join(group)
            tc = count_tokens(group_text)
            result.append(
                _build_chunk(
                    text=group_text,
                    chunk_type=chunk.chunk_type,
                    start_token=offset,
                    end_token=offset + tc,
                    token_count=tc,
                    source_file=chunk.source_file,
                    metadata={
                        **chunk.metadata,
                        "semantic_refined": True,
                        "sentence_count": len(group),
                    },
                )
            )
            offset += tc

        return result