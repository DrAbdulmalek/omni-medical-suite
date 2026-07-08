"""Evaluation metrics for Arabic medical OCR."""

from __future__ import annotations

import re
from typing import List


def normalize_arabic(text: str) -> str:
    """Remove tashkeel and collapse whitespace for fair comparison."""
    text = re.sub(r"[\u064B-\u0652\u0670]", "", text)  # diacritics
    text = re.sub(r"\s+", " ", text.strip())
    return text


def compute_cer(reference: str, prediction: str) -> float:
    """Character Error Rate.

    Uses a simple edit-distance implementation that avoids
    depending on ``jiwer`` at runtime (falls back to it
    when available for accuracy).
    """
    ref = normalize_arabic(reference)
    pred = normalize_arabic(prediction)

    if not ref:
        return 1.0 if pred else 0.0

    try:
        from jiwer import cer as _cer

        return _cer(ref, pred)
    except ImportError:
        return _edit_distance_char(ref, pred) / max(len(ref), 1)


def compute_wer(reference: str, prediction: str) -> float:
    """Word Error Rate."""
    ref = normalize_arabic(reference)
    pred = normalize_arabic(prediction)

    ref_words = ref.split()
    pred_words = pred.split()

    if not ref_words:
        return 1.0 if pred_words else 0.0

    try:
        from jiwer import wer as _wer

        return _wer(ref, pred)
    except ImportError:
        return _edit_distance_words(ref_words, pred_words) / len(ref_words)


def evaluate_batch(
    predictions: List[str], references: List[str]
) -> dict:
    """Evaluate a batch of predictions against references.

    Returns a dict with per-sample and average CER/WER.
    """
    cer_scores: list[float] = []
    wer_scores: list[float] = []

    for pred, ref in zip(predictions, references):
        cer_scores.append(compute_cer(ref, pred))
        wer_scores.append(compute_wer(ref, pred))

    return {
        "cer": cer_scores,
        "wer": wer_scores,
        "avg_cer": sum(cer_scores) / len(cer_scores) if cer_scores else 0.0,
        "avg_wer": sum(wer_scores) / len(wer_scores) if wer_scores else 0.0,
        "num_samples": len(cer_scores),
    }


# ---------------------------------------------------------------------------
# Minimal fallback implementations (no external deps)
# ---------------------------------------------------------------------------

def _edit_distance_char(s1: str, s2: str) -> int:
    """Levenshtein distance at the character level."""
    if len(s1) < len(s2):
        return _edit_distance_char(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(
                min(
                    curr[j] + 1,       # insertion
                    prev[j + 1] + 1,   # deletion
                    prev[j] + cost,    # substitution
                )
            )
        prev = curr
    return prev[-1]


def _edit_distance_words(w1: list[str], w2: list[str]) -> int:
    """Levenshtein distance at the word level."""
    return _edit_distance_char(" ".join(w1), " ".join(w2))