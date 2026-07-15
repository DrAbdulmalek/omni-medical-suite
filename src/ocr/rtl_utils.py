"""Utilities for fixing Arabic RTL OCR output.

This module focuses on the EasyOCR failure mode discovered during the July 2026
validation pass: Arabic spans may be emitted visually left-to-right, with each
Arabic token reversed.  The fixer keeps the API intentionally lightweight so it
can be used both in batch evaluation scripts and in runtime OCR pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from packages.nlp.arabic_rtl import ARABIC_NORMALIZATION_MAP

# Bridge: delegate to the canonical contract in text_reconstructor.
# Both modules now agree on what "canonical Arabic" means.
try:
    from packages.vision.text_reconstructor import canonicalize_arabic as _canonicalize
except ImportError:  # pragma: no cover — fallback to local impl
    _canonicalize = None

ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
ARABIC_TOKEN_RE = re.compile(r"^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+$")
PRESENTATION_FORM_RE = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
TOKEN_SPLIT_RE = re.compile(r"\s+")
COMMON_ARABIC_HINTS = (
    "ال",
    "اسم",
    "الم",
    "مريض",
    "تاريخ",
    "رقم",
    "تشخيص",
    "دواء",
    "عبد",
    "بن",
    "ية",
    "ات",
)


@dataclass(slots=True)
class RTLFixStats:
    """Diagnostics returned by :class:`ArabicRTLFixer`."""

    reversal_ratio: float
    had_presentation_forms: bool
    changed: bool


class ArabicRTLFixer:
    """Fix reversed Arabic OCR lines while leaving non-Arabic tokens intact."""

    def __init__(self, reversal_threshold: float = 0.30) -> None:
        self.reversal_threshold = reversal_threshold

    @staticmethod
    def contains_arabic(text: str) -> bool:
        return bool(text and ARABIC_CHAR_RE.search(text))

    @staticmethod
    def normalize_presentation_forms(text: str) -> str:
        """Normalize Arabic text to canonical Unicode (delegates to canonicalize_arabic)."""
        if _canonicalize is not None:
            return _canonicalize(text)
        # Local fallback (identical logic) when text_reconstructor is not importable
        if not text:
            return ""
        normalized = unicodedata.normalize("NFKC", text)
        return "".join(ARABIC_NORMALIZATION_MAP.get(ch, ch) for ch in normalized)

    @staticmethod
    def _arabic_tokens(text: str) -> list[str]:
        return [token for token in TOKEN_SPLIT_RE.split(text.strip()) if ARABIC_TOKEN_RE.match(token)]

    @staticmethod
    def _arabic_hint_score(token: str) -> int:
        if not token:
            return 0
        score = 0
        if token.startswith("ال"):
            score += 2
        for hint in COMMON_ARABIC_HINTS:
            if hint in token:
                score += 1
        return score

    def reversal_ratio(self, text: str) -> float:
        """Estimate how strongly the text looks like visually reversed Arabic.

        Heuristic: if reversing a token yields more common Arabic prefixes and
        substrings than the token in its current form, that token votes for a
        reversal fix.
        """

        tokens = self._arabic_tokens(self.normalize_presentation_forms(text))
        long_tokens = [token for token in tokens if len(token) >= 3]
        if not long_tokens:
            return 0.0

        reversed_votes = 0
        for token in long_tokens:
            current_score = self._arabic_hint_score(token)
            reversed_score = self._arabic_hint_score(token[::-1])
            if reversed_score > current_score:
                reversed_votes += 1
        return reversed_votes / len(long_tokens)

    def should_fix(self, text: str) -> bool:
        if not self.contains_arabic(text):
            return False
        normalized = self.normalize_presentation_forms(text)
        if PRESENTATION_FORM_RE.search(text):
            return True
        return self.reversal_ratio(normalized) >= self.reversal_threshold

    @staticmethod
    def _reverse_arabic_token(token: str) -> str:
        return token[::-1]

    def _fix_line(self, line: str) -> str:
        tokens = [token for token in TOKEN_SPLIT_RE.split(line.strip()) if token]
        if not tokens:
            return ""

        normalized = [self.normalize_presentation_forms(token) for token in tokens]
        converted = [
            self._reverse_arabic_token(token) if ARABIC_TOKEN_RE.match(token) else token
            for token in normalized
        ]

        arabic_positions = [idx for idx, token in enumerate(normalized) if ARABIC_TOKEN_RE.match(token)]
        if len(arabic_positions) > 1:
            reversed_arabic = [converted[idx] for idx in arabic_positions][::-1]
            for idx, new_token in zip(arabic_positions, reversed_arabic, strict=False):
                converted[idx] = new_token
        return " ".join(converted)

    def fix_text(self, text: str, *, force: bool = False) -> str:
        if not text:
            return ""
        normalized = self.normalize_presentation_forms(text)
        if not force and not self.should_fix(normalized):
            return normalized
        lines = [self._fix_line(line) for line in normalized.splitlines()]
        return "\n".join(lines).strip()

    def analyze_and_fix(self, text: str, *, force: bool = False) -> tuple[str, RTLFixStats]:
        normalized = self.normalize_presentation_forms(text)
        ratio = self.reversal_ratio(normalized)
        changed = force or self.should_fix(normalized)
        fixed = self.fix_text(normalized, force=force)
        return fixed, RTLFixStats(
            reversal_ratio=ratio,
            had_presentation_forms=bool(PRESENTATION_FORM_RE.search(text or "")),
            changed=changed and fixed != normalized,
        )
