"""
Arabic Text Normalizer
======================
Normalizes Arabic text for improved OCR accuracy and consistency.

Handles:
- Alef variant normalization (أ إ آ → ا)
- Taa marbuta normalization (ة → ه in final position, context-dependent)
- Alef maqsura normalization (ى → ي)
- Diacritics (tashkeel) removal
- Tatweel (kashida) removal
- Whitespace normalization
- Common encoding issue fixes
- RTL text handling utilities

Author: DrAbdulmalek
License: MIT
"""

import re

# Arabic Unicode ranges
ARABIC_RANGE = r"\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF"

# Arabic diacritics (tashkeel) Unicode range: 0x0610–0x061A, 0x064B–0x065F, 0x0670
DIACRITICS_RANGE = (
    r"\u0610\u0611\u0612\u0613\u0614\u0615\u0616\u0617\u0618\u0619\u061A"
    r"\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0653\u0654\u0655\u0656\u0657"
    r"\u0658\u0659\u065A\u065B\u065C\u065D\u065E\u065F\u0670"
)

# Tatweel (kashida) character
TATWEEL = "\u0640"

# Alef variants
ALEF_VARIANTS = {"أ": "ا", "إ": "ا", "آ": "ا"}

# Taa marbuta
TAA_MARBUTA = "ة"
HAA = "ه"

# Alef maqsura
ALEF_MAQSURA = "ى"
YAA = "ي"

# Common Western-Arabic encoding confusion patterns
ENCODING_FIXES = {
    "المعتويات": "المحتويات",
    "الجراحة العطمية": "الجراحة العظمية",
    "الهيكنية": "الهيكلية",
    "التصفع": "التصنع",
    "الأوزام": "الأورام",
    "العضنية": "العضلية",
    "السحانية": "السحائية",
    "القبنة": "القيلة",
    "الشثل": "الشلل",
    "شنل": "شلل",
    "شازكو": "شاركو",
    "القفدا": "القفداء",
    "انقدم": "القدم",
    "الخر": "الخرع",
    "Rickels": "Rickets",
}

# Regex pattern for matching diacritics
DIACRITICS_RE = re.compile(f"[{DIACRITICS_RANGE}]")
TATWEEL_RE = re.compile(TATWEEL)
MULTI_SPACE_RE = re.compile(r"\s{2,}")
LEADING_TRAILING_SPACE_RE = re.compile(r"^\s+|\s+$", re.MULTILINE)

# Regex for Western Arabic numeral to Eastern Arabic numeral conversion
WESTERN_DIGITS = "0123456789"
EASTERN_DIGITS = "٠١٢٣٤٥٦٧٨٩"
DIGIT_TRANSLATION_TABLE = str.maketrans(WESTERN_DIGITS, EASTERN_DIGITS)


class ArabicTextNormalizer:
    """
    Comprehensive Arabic text normalizer for OCR postprocessing.

    Provides methods for character normalization, diacritics removal,
    whitespace cleanup, and encoding issue correction.
    """

    def __init__(
        self,
        remove_diacritics: bool = True,
        remove_tatweel: bool = True,
        normalize_alef: bool = True,
        normalize_taa_marbuta: bool = False,
        normalize_alef_maqsura: bool = True,
        normalize_whitespace: bool = True,
        fix_encoding: bool = True,
        convert_numerals: bool = False,
    ) -> None:
        """
        Initialize the normalizer with configurable options.

        Args:
            remove_diacritics: Remove Arabic diacritics (harakat/tashkeel).
            remove_tatweel: Remove tatweel (kashida) characters.
            normalize_alef: Normalize alef variants (أ إ آ) to bare alef (ا).
            normalize_taa_marbuta: Normalize taa marbuta (ة) to haa (ه).
                Disabled by default as it changes meaning in Arabic.
            normalize_alef_maqsura: Normalize alef maqsura (ى) to yaa (ي).
            normalize_whitespace: Collapse multiple whitespace to single space.
            fix_encoding: Apply known OCR encoding fixes.
            convert_numerals: Convert Western Arabic digits to Eastern Arabic digits.
        """
        self.remove_diacritics = remove_diacritics
        self.remove_tatweel = remove_tatweel
        self.normalize_alef = normalize_alef
        self.normalize_taa_marbuta = normalize_taa_marbuta
        self.normalize_alef_maqsura = normalize_alef_maqsura
        self.normalize_whitespace = normalize_whitespace
        self.fix_encoding = fix_encoding
        self.convert_numerals = convert_numerals

        # Compile the alef normalization mapping
        self._alef_map = str.maketrans(ALEF_VARIANTS) if normalize_alef else {}

    def normalize(self, text: str) -> str:
        """
        Apply all enabled normalizations to the input text.

        Args:
            text: Input Arabic text to normalize.

        Returns:
            Normalized text string.
        """
        if not text:
            return text

        result = text

        # Apply encoding fixes first (before character-level normalization)
        if self.fix_encoding:
            result = self._fix_encoding_issues(result)

        # Remove diacritics
        if self.remove_diacritics:
            result = DIACRITICS_RE.sub("", result)

        # Remove tatweel
        if self.remove_tatweel:
            result = TATWEEL_RE.sub("", result)

        # Normalize alef variants
        if self.normalize_alef and self._alef_map:
            result = result.translate(self._alef_map)

        # Normalize taa marbuta
        if self.normalize_taa_marbuta:
            result = result.replace(TAA_MARBUTA, HAA)

        # Normalize alef maqsura
        if self.normalize_alef_maqsura:
            result = result.replace(ALEF_MAQSURA, YAA)

        # Convert Western digits to Eastern Arabic digits
        if self.convert_numerals:
            result = result.translate(DIGIT_TRANSLATION_TABLE)

        # Normalize whitespace
        if self.normalize_whitespace:
            result = self._normalize_whitespace(result)

        return result

    def _fix_encoding_issues(self, text: str) -> str:
        """
        Fix common OCR encoding confusion patterns.

        Args:
            text: Input text with potential encoding issues.

        Returns:
            Text with known encoding issues fixed.
        """
        result = text
        for wrong, correct in ENCODING_FIXES.items():
            result = result.replace(wrong, correct)
        return result

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """
        Normalize whitespace in text.

        Collapses multiple spaces/tabs/newlines to single spaces,
        trims leading/trailing whitespace per line.

        Args:
            text: Input text.

        Returns:
            Text with normalized whitespace.
        """
        result = MULTI_SPACE_RE.sub(" ", text)
        result = LEADING_TRAILING_SPACE_RE.sub("", result)
        return result.strip()

    @staticmethod
    def has_arabic(text: str) -> bool:
        """
        Check if text contains Arabic characters.

        Args:
            text: Input text.

        Returns:
            True if Arabic characters are present.
        """
        arabic_re = re.compile(f"[{ARABIC_RANGE}]")
        return bool(arabic_re.search(text))

    @staticmethod
    def arabic_ratio(text: str) -> float:
        """
        Calculate the ratio of Arabic characters in the text.

        Args:
            text: Input text.

        Returns:
            Float between 0.0 and 1.0 representing the proportion of
            Arabic characters.
        """
        if not text:
            return 0.0
        arabic_re = re.compile(f"[{ARABIC_RANGE}]")
        arabic_chars = len(arabic_re.findall(text))
        return arabic_chars / len(text)

    @staticmethod
    def get_rtl_markers(text: str) -> str:
        """
        Wrap text with RTL markers for proper display in mixed content.

        Args:
            text: Input text (should be RTL Arabic).

        Returns:
            Text wrapped with RTL/LTR embedding markers.
        """
        rle = "\u202B"  # Right-to-Left Embedding
        pdf = "\u202C"  # Pop Directional Formatting
        return f"{rle}{text}{pdf}"

    @staticmethod
    def remove_non_arabic(text: str, keep_digits: bool = True, keep_punctuation: bool = True) -> str:
        """
        Remove non-Arabic characters from text.

        Args:
            text: Input text.
            keep_digits: Whether to keep Arabic and Western digits.
            keep_punctuation: Whether to keep common punctuation.

        Returns:
            Filtered text containing only Arabic characters (and optionally digits/punctuation).
        """
        if keep_digits and keep_punctuation:
            # Keep Arabic chars, digits, common punctuation, whitespace
            pattern = f"[^{ARABIC_RANGE}0-9\\s.,;:!?\\-\\(\\)\\[\\]\\{{\\}}]"
        elif keep_digits:
            pattern = f"[^{ARABIC_RANGE}0-9\\s]"
        elif keep_punctuation:
            pattern = f"[^{ARABIC_RANGE}\\s.,;:!?\\-\\(\\)\\[\\]\\{{\\}}]"
        else:
            pattern = f"[^{ARABIC_RANGE}\\s]"

        return re.sub(pattern, "", text)
