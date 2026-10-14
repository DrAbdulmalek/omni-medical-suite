"""Text alignment between teacher OCR output and trusted text.

The aligned pairs feed OCR post-processing error-correction models
(sequence-to-sequence / LLM proofreaders) - the "Ground Truth Baseline"
strategy: ABBYY output is compared with a trusted transcription and the
differences become supervised correction examples.

Also provides CER (Character Error Rate) based on Levenshtein alignment.
"""

from __future__ import annotations

import difflib
import re
from typing import Iterable, Optional

from .models import CorrectionPair

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_for_alignment(text: str) -> str:
    """Normalise whitespace (but keep Arabic diacritics) for fair comparison."""
    return _WHITESPACE_RE.sub(" ", text or "").strip()


def levenshtein_distance(ref: str, hyp: str) -> int:
    """Classic edit distance with an O(len(ref)*len(hyp)) rolling row."""
    if ref == hyp:
        return 0
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i]
        for j, h in enumerate(hyp, start=1):
            cost = 0 if r == h else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate = edit_distance / len(reference), in [0, inf).

    Returns 0.0 when both strings are empty; returns 1.0 when the reference
    is empty but the hypothesis is not.
    """
    ref = normalize_for_alignment(reference)
    hyp = normalize_for_alignment(hypothesis)
    if not ref and not hyp:
        return 0.0
    if not ref:
        return 1.0
    return levenshtein_distance(ref, hyp) / len(ref)


def align_texts(ocr_text: str, truth_text: str) -> list[tuple[str, str, str]]:
    """Character-level alignment of two strings.

    Returns difflib opcodes as tuples ``(tag, ocr_chunk, truth_chunk)`` where
    ``tag`` is one of ``equal / replace / delete / insert``.
    """
    sm = difflib.SequenceMatcher(a=normalize_for_alignment(ocr_text), b=normalize_for_alignment(truth_text), autojunk=False)
    out: list[tuple[str, str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        out.append((tag, ocr_text_norm_slice(ocr_text, i1, i2), truth_text_norm_slice(truth_text, j1, j2)))
    return out


# Keep slices consistent with the normalised strings used inside SequenceMatcher.
def ocr_text_norm_slice(text: str, i1: int, i2: int) -> str:
    return normalize_for_alignment(text)[i1:i2]


def truth_text_norm_slice(text: str, j1: int, j2: int) -> str:
    return normalize_for_alignment(text)[j1:j2]


def build_correction_pair(
    ocr_text: str,
    truth_text: str,
    source_file: str = "",
    page_num: int = 1,
    level: str = "line",
    bbox: Optional[list[int]] = None,
    confidence: Optional[float] = None,
    language: str = "unknown",
    source_format: str = "",
) -> CorrectionPair:
    """Build one supervised correction pair; skips to a no-op via caller checks."""
    ocr_n = normalize_for_alignment(ocr_text)
    truth_n = normalize_for_alignment(truth_text)
    return CorrectionPair(
        ocr_text=ocr_n,
        corrected_text=truth_n,
        source_file=source_file,
        page_num=page_num,
        level=level,
        bbox=bbox,
        confidence=confidence,
        cer=round(cer(truth_n, ocr_n), 4),
        language=language if language != "unknown" else guess_language(truth_n),
        source_format=source_format,
    )


def line_pairs_from_trusted_text(
    annotation,  # PageAnnotation (avoid import cycle; duck-typed)
    trusted_text: str,
    source_file: str = "",
    min_similarity: float = 0.35,
) -> list[CorrectionPair]:
    """Align the page's recognised lines against a trusted transcription.

    The trusted text is split into lines; a SequenceMatcher over the *line
    sequences* pairs each recognised line with its most similar trusted line.
    Pairs below ``min_similarity`` (ratio) are dropped: they would most likely
    be mis-alignments rather than genuine correction examples.
    """
    ocr_lines = [normalize_for_alignment(l.text) for l in annotation.lines if l.text.strip()]
    truth_lines = [normalize_for_alignment(t) for t in trusted_text.splitlines() if t.strip()]

    sm = difflib.SequenceMatcher(a=ocr_lines, b=truth_lines, autojunk=False)
    pairs: list[CorrectionPair] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                pairs.append(
                    build_correction_pair(
                        ocr_lines[i1 + k],
                        truth_lines[j1 + k],
                        source_file=source_file,
                        page_num=1,
                        level="line",
                        confidence=annotation.lines[i1 + k].confidence if i1 + k < len(annotation.lines) else None,
                        source_format=annotation.source_format.value,
                    )
                )
        elif tag == "replace":
            for k in range(min(i2 - i1, j2 - j1)):
                o, t = ocr_lines[i1 + k], truth_lines[j1 + k]
                ratio = difflib.SequenceMatcher(a=o, b=t).ratio()
                if ratio >= min_similarity:
                    pairs.append(
                        build_correction_pair(
                            o,
                            t,
                            source_file=source_file,
                            level="line",
                            confidence=annotation.lines[i1 + k].confidence if i1 + k < len(annotation.lines) else None,
                            source_format=annotation.source_format.value,
                        )
                    )
        # delete/insert: no reliable line pairing - skipped on purpose
    return pairs


def guess_language(text: str) -> str:
    """Cheap heuristic matching the repo contract values:
    ``arabic | english | german | unknown``."""
    if not text:
        return "unknown"
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "unknown"
    arabic = sum(1 for c in letters if 0x0600 <= ord(c) < 0x0700)
    german_lower = sum(1 for c in text.lower() if c in ("ä", "ö", "ü", "ß"))
    if arabic / len(letters) > 0.3:
        return "arabic"
    if german_lower:
        return "german"
    ascii_letters = sum(1 for c in letters if c.isascii())
    if ascii_letters / len(letters) > 0.7:
        return "english"
    return "unknown"


def pairs_to_jsonl(pairs: Iterable[CorrectionPair]) -> list[str]:
    """Serialise correction pairs as JSONL lines (repo-compatible schema)."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    for p in pairs:
        import json

        lines.append(
            json.dumps(
                {
                    "ocr_text": p.ocr_text,
                    "corrected_text": p.corrected_text,
                    "language": p.language,
                    "source_file": p.source_file,
                    "page_num": p.page_num,
                    "confidence": p.confidence,
                    "created_at": p.created_at or now,
                    "level": p.level,
                    "bbox": p.bbox,
                    "cer": p.cer,
                    "source_format": p.source_format,
                },
                ensure_ascii=False,
            )
        )
    return lines
