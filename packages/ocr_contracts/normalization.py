"""Non-destructive text contracts for OCR/evaluation boundaries.

Raw OCR and human reference text are immutable source values. Normalization is
an explicitly derived matching/evaluation view and must never overwrite either
source value.
"""
from __future__ import annotations

from packages.evaluation.arabic_normalize import normalize_v1


def preserve_reference(text: str | None) -> str:
    """Return reference text verbatim; this is intentionally an identity function."""
    return "" if text is None else text


def normalize_for_matching(text: str | None, *, fold_hamza: bool = False) -> tuple[str, dict]:
    """Create a derived comparison view without mutating the source text."""
    return normalize_v1(text, fold_hamza=fold_hamza)
