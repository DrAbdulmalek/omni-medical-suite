"""
alignment.py
Aligns text output from multiple OCR sources (ABBYY, Readiris, your own
engines) word-by-word using sequence alignment, to find agreement and
disagreement points.

This is the core of the ground-truth generation logic: when sources agree,
confidence is high (auto-accept). When they disagree, the word is flagged
for human review or treated as a hard training example.
"""

import re
import difflib
from typing import List, Dict, Any
from collections import Counter


def tokenize(text: str) -> List[str]:
    """
    Splits text into words, preserving Arabic and Latin scripts.
    Strips punctuation-only tokens but keeps words with internal punctuation
    (e.g. "Dr.", numbers with decimals).

    Args:
        text: Raw text string

    Returns:
        List of word tokens
    """
    # Split on whitespace, then strip leading/trailing punctuation per token
    raw_tokens = text.split()
    tokens = []
    for t in raw_tokens:
        cleaned = t.strip(".,;:!?()[]{}«»\"'-–—")
        if cleaned:
            tokens.append(cleaned)
    return tokens


def align_two_sources(tokens_a: List[str], tokens_b: List[str]) -> List[Dict[str, Any]]:
    """
    Aligns two token sequences using difflib's SequenceMatcher
    (same algorithm family used for computing WER/diff).

    Args:
        tokens_a: Tokens from source A (e.g. ABBYY)
        tokens_b: Tokens from source B (e.g. Readiris)

    Returns:
        List of aligned segments:
            {
                "type": "equal" | "replace" | "delete" | "insert",
                "a": list of tokens from A in this segment,
                "b": list of tokens from B in this segment,
            }
    """
    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b, autojunk=False)
    segments = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        segments.append({
            "type": tag,  # "equal", "replace", "delete", "insert"
            "a": tokens_a[i1:i2],
            "b": tokens_b[j1:j2],
        })

    return segments


def merge_multi_source(
    sources: Dict[str, str],
    primary_source: str = None
) -> Dict[str, Any]:
    """
    Merges 2+ OCR text sources into a single ground-truth candidate.

    Strategy:
    - Tokenize each source
    - Align all sources pairwise against a reference (first source, or
      primary_source if given)
    - For each word position: if all sources agree -> high confidence
    - If sources disagree -> majority vote, flagged for review
    - If only 2 sources and they disagree -> both kept, flagged "conflict"

    Args:
        sources: dict of {source_name: text}, e.g.
            {"abbyy": "...", "readiris": "...", "tesseract": "..."}
        primary_source: which source to use as the alignment reference
            (defaults to the first key in `sources`)

    Returns:
        {
            "merged_text": str,           # best-guess reconstructed text
            "word_results": [             # per-word details
                {
                    "word": str,
                    "agreement": "full" | "majority" | "conflict",
                    "sources_agreeing": list[str],
                    "variants": dict,     # what each source said, if different
                    "confidence": float,  # 0.0 - 1.0
                },
                ...
            ],
            "stats": {
                "total_words": int,
                "full_agreement": int,
                "majority_agreement": int,
                "conflicts": int,
                "agreement_rate": float,
            }
        }
    """
    if not sources:
        raise ValueError("At least one source is required")

    source_names = list(sources.keys())
    ref_name = primary_source or source_names[0]
    ref_tokens = tokenize(sources[ref_name])

    other_names = [n for n in source_names if n != ref_name]

    # Build per-position votes by aligning each other source to the reference
    # position_votes[i] = {source_name: word_or_None}
    position_votes = [{ref_name: w} for w in ref_tokens]

    for other_name in other_names:
        other_tokens = tokenize(sources[other_name])
        segments = align_two_sources(ref_tokens, other_tokens)

        ref_idx = 0
        for seg in segments:
            if seg["type"] == "equal":
                for w in seg["a"]:
                    position_votes[ref_idx][other_name] = w
                    ref_idx += 1
            elif seg["type"] == "replace":
                # Best-effort: align position-by-position within the replace block
                a_len = len(seg["a"])
                b_len = len(seg["b"])
                for k in range(a_len):
                    if k < b_len:
                        position_votes[ref_idx][other_name] = seg["b"][k]
                    else:
                        position_votes[ref_idx][other_name] = None
                    ref_idx += 1
            elif seg["type"] == "delete":
                # Reference has words the other source doesn't
                for _ in seg["a"]:
                    position_votes[ref_idx][other_name] = None
                    ref_idx += 1
            elif seg["type"] == "insert":
                # Other source has extra words not in reference — skip
                # (could optionally be tracked separately as "extra_words")
                pass

    # Now build word_results from position_votes
    word_results = []
    full_agreement = 0
    majority_agreement = 0
    conflicts = 0

    for votes in position_votes:
        values = [v for v in votes.values() if v is not None]
        if not values:
            continue

        counter = Counter(values)
        most_common_word, most_common_count = counter.most_common(1)[0]
        n_sources_with_value = len(values)
        n_total_sources = len(source_names)

        if most_common_count == n_sources_with_value and n_sources_with_value == n_total_sources:
            # Every source that had a value, and every source overall, agrees
            agreement = "full"
            full_agreement += 1
            confidence = 1.0
        elif most_common_count > n_sources_with_value / 2:
            # Strict majority (e.g. 2-out-of-3). A 1-vs-1 tie does NOT qualify.
            agreement = "majority"
            majority_agreement += 1
            confidence = most_common_count / n_total_sources
        else:
            # Tie or no clear majority (e.g. 1-vs-1, or 1-vs-1-vs-1)
            agreement = "conflict"
            conflicts += 1
            confidence = most_common_count / n_total_sources

        sources_agreeing = [s for s, w in votes.items() if w == most_common_word]

        word_results.append({
            "word": most_common_word,
            "agreement": agreement,
            "sources_agreeing": sources_agreeing,
            "variants": {s: w for s, w in votes.items() if w != most_common_word and w is not None},
            "confidence": round(confidence, 3),
        })

    total_words = len(word_results)
    merged_text = " ".join(w["word"] for w in word_results)

    return {
        "merged_text": merged_text,
        "word_results": word_results,
        "stats": {
            "total_words": total_words,
            "full_agreement": full_agreement,
            "majority_agreement": majority_agreement,
            "conflicts": conflicts,
            "agreement_rate": round(full_agreement / total_words, 3) if total_words else 0.0,
        },
    }


def compute_similarity_ratio(text_a: str, text_b: str) -> float:
    """
    Quick similarity score between two texts (0.0 - 1.0).
    Useful for a fast pre-check before full alignment.

    Args:
        text_a: First text
        text_b: Second text

    Returns:
        Similarity ratio (1.0 = identical)
    """
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b, autojunk=False)
    return round(matcher.ratio(), 3)
