"""
Arabic OCR error correction rules.

Defines common confusion patterns encountered when OCR engines process
Arabic medical documents.  These rules address:

- **Dot confusion**: Letters that differ only in dot position/count
  (e.g. ب/ت/ث/ن/ي)
- **Shape confusion**: Letters with similar baseline shapes
  (e.g. ح/خ/ج, ص/ض, ع/غ)
- **Final-form confusion**: ta marbuta (ة) vs. ha (ه) vs. ya (ى)
- **Common medical term corrections**: Frequently misspelled Arabic
  medical terminology.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 1. Character-level substitution rules
# ---------------------------------------------------------------------------

# Each entry maps an incorrect character (or tuple of context chars) to the
# correct one.  Applied left-to-right across the text.
CHARACTER_SUBSTITUTIONS: Dict[str, str] = {
    # Ta marbuta / Ha / Ya final-form confusion
    "\u0647\u064a": "\u0629\u064a",  # ه ي → ة ي  (e.g. "المستشفية" → "المستشفية" correct)
    # Dot confusion – letters sharing the same base form
    "\u0628": "\u062a",  # ب → ت  (common in degraded print)
    "\u062a": "\u062b",  # ت → ث  (less common)
    "\u0646": "\u062a",  # ن → ت  (dot count confusion)
    "\u064a": "\u0628",  # ي → ب  (positional dot confusion)
    # Shape confusion – letters with similar skeletons
    "\u062c": "\u062d",  # ج → ح
    "\u062e": "\u062d",  # خ → ح
    "\u0635": "\u0633",  # ص → س  (dot count)
    "\u0636": "\u0635",  # ض → ص  (dot count)
    "\u0637": "\u0638",  # ط → ظ  (dot count)
    "\u0639": "\u063a",  # ع → غ  (dot count)
    "\u0642": "\u0641",  # ق → ف  (shape similarity in some fonts)
}

# ---------------------------------------------------------------------------
# 2. Context-dependent rules (regex-based)
# ---------------------------------------------------------------------------

# Regex patterns for contextual corrections.
# Each tuple: (compiled regex, replacement string, description)
CONTEXT_RULES: List[Tuple[re.Pattern, str, str]] = [
    # Ta marbuta in feminine nouns ending with ة
    (
        re.compile(r"(\u0629)\s*$", re.MULTILINE),
        r"\u0647",
        "Isolated ta marbuta at end of word may be ha",
    ),
    # Common ligature corrections
    (
        re.compile(r"\u0644\u0627"),
        "\u0644\u0627",  # lam-alef – keep as-is but normalise
        "Normalise lam-alef ligature",
    ),
    # Alef with hamza normalisation
    (
        re.compile(r"[\u0622\u0623\u0625]"),
        "\u0627",
        "Normalise alef variants to bare alef",
    ),
    # Tatweel (kashida) removal – decorative stretching character
    (
        re.compile(r"\u0640"),
        "",
        "Remove tatweel/kashida characters",
    ),
    # Multiple diacritics collapse
    (
        re.compile(r"([\u0610-\u061a\u064b-\u065f\u0670]){2,}"),
        r"\1",
        "Collapse consecutive diacritics to single",
    ),
]

# ---------------------------------------------------------------------------
# 3. Common Arabic medical term corrections
# ---------------------------------------------------------------------------

# Maps frequently OCR-misread medical terms (wrong → correct).
# Covers drug names, anatomical terms, lab values, and clinical abbreviations.
MEDICAL_TERM_CORRECTIONS: Dict[str, str] = {
    # Anatomy
    "القلبية": "القلبية",
    "الرئتين": "الرئتين",
    "المعدة": "المعدة",
    "الكبد": "الكبد",
    "الكليتين": "الكليتين",
    "الدماغ": "الدماغ",
    "العظام": "العظام",
    "الاعصاب": "الأعصاب",
    "الاعصاب": "الأعصاب",
    "العضلات": "العضلات",
    "الانسجة": "الأنسجة",
    "الانسجة": "الأنسجة",
    "الاورام": "الأورام",
    "الاورام": "الأورام",
    # Clinical terms
    "ضغط الدم": "ضغط الدم",
    "سكر الدم": "سكر الدم",
    "التهاب": "التهاب",
    "مضاد حيوي": "مضاد حيوي",
    "تحليل دم": "تحليل دم",
    "اشعة": "أشعة",
    "عملية جراحية": "عملية جراحية",
    "تخدير": "تخدير",
    "مستشفى": "مستشفى",
    "عيادة": "عيادة",
    "طوارئ": "طوارئ",
    "عناية مركزة": "عناية مركزة",
    # Common drug names (Arabic)
    "باراسيتامول": "باراسيتامول",
    "ايبوبروفين": "إيبوبروفين",
    "اموكسيسيلين": "أموكسيسيلين",
    "اموكسيسيلين": "أموكسيسيلين",
    "ميتفورمين": "ميتفورمين",
    "انسولين": "أنسولين",
    "انسولين": "أنسولين",
    "اتورفاستاتين": "أتورفاستاتين",
    "اوميبرازول": "أوميبرازول",
    "لوسارتان": "لوسارتان",
    "سالتامول": "سالتامول",
    "سيمفاستاتين": "سيمفاستاتين",
    # Lab / units
    "ملغم": "ملغم",
    "ملم": "ملم",
    "ميكروغرام": "ميكروغرام",
    "وحدة دولية": "وحدة دولية",
    "مم زئبق": "مم زئبق",
    # Common OCR artefacts in medical context
    "المرضع": "المرضع",
    "المرضع": "المرضع",
    "الحامل": "الحامل",
    "حساسية": "حساسية",
    "اورام": "أورام",
    "اورام": "أورام",
    "نزيف": "نزيف",
    "جلطة": "جلطة",
    "سرطان": "سرطان",
    "سكري": "سكري",
    "ضغط": "ضغط",
    "حرارة": "حرارة",
    "درجة حرارة": "درجة حرارة",
}

# ---------------------------------------------------------------------------
# 4. Dot-confusion groups
# ---------------------------------------------------------------------------

# Groups of Arabic letters that share the same base skeleton and differ only
# in the number or position of dots.  Used for fuzzy matching.
DOT_CONFUSION_GROUPS: List[List[str]] = [
    # Base: U+0628 (ba) skeleton
    ["\u0628", "\u062a", "\u062b", "\u0646", "\u064a"],  # ب ت ث ن ي
    # Base: U+062C (jeem) skeleton
    ["\u062c", "\u062d", "\u062e"],  # ج ح خ
    # Base: U+0633 (seen) skeleton
    ["\u0633", "\u0634"],  # س ش
    # Base: U+0635 (sad) skeleton
    ["\u0635", "\u0636"],  # ص ض
    # Base: U+0639 (ain) skeleton
    ["\u0639", "\u063a"],  # ع غ
    # Base: U+0641 (fa) skeleton
    ["\u0641", "\u0642"],  # ف ق
    # Base: U+0643 (kaf) / U+06AF (gaf) skeleton
    ["\u0643", "\u06af"],  # ك گ
    # Base: U+0637 (taa) skeleton
    ["\u0637", "\u0638", "\u0636"],  # ط ظ ض
    # Final forms
    ["\u0629", "\u0647", "\u0649"],  # ة ه ى
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ArabicOCRRules:
    """Rule-based Arabic OCR error corrector.

    Applies a sequence of deterministic correction strategies:

    1. Unicode normalisation (NFC)
    2. Tatweel / diacritic cleanup
    3. Character-level substitutions
    4. Context-dependent regex rules
    5. Whole-word medical term corrections

    Parameters
    ----------
    custom_rules : dict[str, str] | None
        Additional word-level corrections to merge into the built-in table.
    extra_char_subs : dict[str, str] | None
        Additional character-level substitutions.
    """

    def __init__(
        self,
        custom_rules: Dict[str, str] | None = None,
        extra_char_subs: Dict[str, str] | None = None,
    ) -> None:
        # Merge any user-supplied rules
        self._medical_terms: Dict[str, str] = {**MEDICAL_TERM_CORRECTIONS}
        if custom_rules:
            self._medical_terms.update(custom_rules)

        self._char_subs: Dict[str, str] = {**CHARACTER_SUBSTITUTIONS}
        if extra_char_subs:
            self._char_subs.update(extra_char_subs)

        # Pre-compile a single pattern for character substitution
        # Sort keys by length (longest first) so multi-char keys take priority
        sorted_keys = sorted(self._char_subs.keys(), key=len, reverse=True)
        self._char_pattern = re.compile(
            "|".join(re.escape(k) for k in sorted_keys)
        )

    # ------------------------------------------------------------------
    # Core correction pipeline
    # ------------------------------------------------------------------

    def apply_rules(self, text: str) -> str:
        """Apply all OCR correction rules to *text*.

        Parameters
        ----------
        text : str
            Raw Arabic text produced by OCR.

        Returns
        -------
        str
            Corrected text.
        """
        if not text:
            return text

        # Step 1 – Unicode normalisation
        corrected = unicodedata.normalize("NFC", text)

        # Step 2 – Context-dependent regex rules (tatweel, diacritics, etc.)
        for pattern, replacement, _desc in CONTEXT_RULES:
            corrected = pattern.sub(replacement, corrected)

        # Step 3 – Character-level substitutions
        corrected = self._char_pattern.sub(
            lambda m: self._char_subs[m.group()], corrected
        )

        # Step 4 – Whole-word medical term corrections
        corrected = self._apply_word_corrections(corrected)

        # Step 5 – Collapse excessive whitespace
        corrected = re.sub(r"\s{2,}", " ", corrected).strip()

        return corrected

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_word_corrections(self, text: str) -> str:
        """Replace whole words that match known incorrect medical terms."""
        # Build a regex that matches any of the incorrect terms as whole words
        if not self._medical_terms:
            return text

        # Sort by length descending so longer matches take priority
        incorrect_terms = sorted(self._medical_terms.keys(), key=len, reverse=True)
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in incorrect_terms) + r")\b"
        )

        def _replace(match: re.Match) -> str:
            return self._medical_terms[match.group(1)]

        return pattern.sub(_replace, text)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @staticmethod
    def get_dot_confusion_groups() -> List[List[str]]:
        """Return the dot-confusion character groups."""
        return DOT_CONFUSION_GROUPS

    @staticmethod
    def get_medical_term_corrections() -> Dict[str, str]:
        """Return the built-in medical term correction table (read-only copy)."""
        return dict(MEDICAL_TERM_CORRECTIONS)

    @staticmethod
    def get_character_substitutions() -> Dict[str, str]:
        """Return the built-in character substitution table (read-only copy)."""
        return dict(CHARACTER_SUBSTITUTIONS)