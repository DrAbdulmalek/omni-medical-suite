"""
Medical Text Cleaner
======================
Cleans and structures OCR output from Arabic medical documents.

Capabilities:
- Clean OCR artifacts (extra whitespace, page numbers, headers/footers)
- Extract structured medical data (medication names, dosages, dates)
- Format output as structured JSON or clean text
- Handle table structures from medical forms

Author: DrAbdulmalek
License: MIT
"""

import json
import re
from pathlib import Path
from typing import Any

from src.postprocessing.text_normalizer import ArabicTextNormalizer

# Patterns for detecting and removing OCR artifacts
PAGE_NUMBER_PATTERNS = [
    re.compile(r"^\s*-\s*\d{1,4}\s*-\s*$", re.MULTILINE),           # - 123 -
    re.compile(r"^\s*صفحة\s*\d{1,4}\s*$", re.MULTILINE),              # صفحة 123
    re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE),                     # standalone number
    re.compile(r"^\s*-\d{3}-\s*$", re.MULTILINE),                     # -593-
]

HEADER_FOOTER_PATTERNS = [
    re.compile(r"جدول المحتويات", re.IGNORECASE),
    re.compile(r"فهرس", re.IGNORECASE),
    re.compile(r"الفصل\s+\d+", re.IGNORECASE),
    re.compile(r"الباب\s+\d+", re.IGNORECASE),
    re.compile(r"الجزء\s+\d+", re.IGNORECASE),
]

# Patterns for extracting medical data
# Medication: name followed by dosage info
MEDICATION_PATTERNS = [
    # Pattern: drug name (mg/ml/unit) x frequency
    re.compile(
        r"([\u0600-\u06FF\s]+?)\s*"
        r"(\d+(?:\.\d+)?)\s*(?:mg|ملغ|مل|وحدة|حبة|كبسولة|amp|أمبولة)\s*"
        r"(?:×|×|مرات|مرة|يومياً|يوميا|أسبوعياً|شهرياً)?\s*"
        r"(\d+)?\s*(?:مرات|مرة|يومياً|يوميا|أسبوعياً|شهرياً)?",
        re.IGNORECASE,
    ),
    # Simpler pattern: word + number + unit
    re.compile(
        r"([\u0600-\u06FF]{2,}?)\s+(\d+(?:\.\d+)?)\s*(mg|ملغ|مل|وحدة|حبة|كبسولة|أمبولة)",
        re.IGNORECASE,
    ),
]

# Date patterns (Arabic and Western formats)
DATE_PATTERNS = [
    re.compile(r"\d{1,4}[/-]\d{1,2}[/-]\d{1,4}"),         # 2025/01/15 or 15-01-2025
    re.compile(r"\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+\d{4}"),
]

# Table cell separator patterns (from OCR table structures)
TABLE_SEPARATOR_PATTERNS = [
    re.compile(r"\t+"),
    re.compile(r"\s{4,}"),
    re.compile(r"\|"),
]


class MedicalTextCleaner:
    """
    Cleans and structures OCR output from Arabic medical documents.

    Combines text normalization, artifact removal, and medical data
    extraction to produce clean, structured output.
    """

    def __init__(
        self,
        dict_path: str | None = None,
        remove_page_numbers: bool = True,
        remove_headers_footers: bool = True,
        normalize: bool = True,
        keep_table_structure: bool = False,
    ) -> None:
        """
        Initialize the medical text cleaner.

        Args:
            dict_path: Path to the Arabic medical dictionary JSON file.
            remove_page_numbers: Whether to remove detected page numbers.
            remove_headers_footers: Whether to remove common headers/footers.
            normalize: Whether to apply Arabic text normalization.
            keep_table_structure: Whether to preserve table structures.
        """
        self.remove_page_numbers = remove_page_numbers
        self.remove_headers_footers = remove_headers_footers
        self.normalize = normalize
        self.keep_table_structure = keep_table_structure

        # Initialize the Arabic text normalizer
        self.normalizer = ArabicTextNormalizer(
            remove_diacritics=True,
            remove_tatweel=True,
            normalize_alef=True,
            normalize_alef_maqsura=True,
            fix_encoding=True,
        )

        # Load dictionary corrections
        self._corrections: dict[str, str] = {}
        self._phrases: dict[str, str] = {}
        self._regex_patterns: list[dict[str, str]] = []
        if dict_path:
            self._load_dictionary(dict_path)
        else:
            # Try default path
            default_path = Path(__file__).resolve().parent.parent.parent / "data" / "arabic_medical_dict.json"
            if default_path.exists():
                self._load_dictionary(str(default_path))

    def _load_dictionary(self, path: str) -> None:
        """
        Load correction dictionary from a JSON file.

        Args:
            path: Path to the dictionary JSON file.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._corrections = data.get("corrections", {})
            self._phrases = data.get("phrases", {})
            self._regex_patterns = data.get("regex_patterns", [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def clean(self, text: str) -> str:
        """
        Clean OCR text by removing artifacts and applying corrections.

        Applies the following steps in order:
        1. Remove page numbers
        2. Remove headers/footers
        3. Apply dictionary corrections (phrases first, then words, then regex)
        4. Normalize Arabic text
        5. Clean up whitespace

        Args:
            text: Raw OCR output text.

        Returns:
            Cleaned text string.
        """
        if not text:
            return text

        result = text

        # Remove page numbers
        if self.remove_page_numbers:
            result = self._remove_page_numbers(result)

        # Remove headers and footers
        if self.remove_headers_footers:
            result = self._remove_headers_footers(result)

        # Apply phrase-level corrections (longer matches first)
        result = self._apply_phrase_corrections(result)

        # Apply word-level corrections
        result = self._apply_word_corrections(result)

        # Apply regex pattern corrections
        result = self._apply_regex_corrections(result)

        # Normalize Arabic text
        if self.normalize:
            result = self.normalizer.normalize(result)

        # Final whitespace cleanup
        result = self.normalizer._normalize_whitespace(result)

        return result

    def _remove_page_numbers(self, text: str) -> str:
        """
        Remove detected page numbers from the text.

        Args:
            text: Input text.

        Returns:
            Text with page numbers removed.
        """
        result = text
        for pattern in PAGE_NUMBER_PATTERNS:
            result = pattern.sub("", result)
        return result

    def _remove_headers_footers(self, text: str) -> str:
        """
        Remove common header/footer text from the document.

        Args:
            text: Input text.

        Returns:
            Text with headers/footers removed.
        """
        result = text
        for pattern in HEADER_FOOTER_PATTERNS:
            result = pattern.sub("", result)
        return result

    def _apply_phrase_corrections(self, text: str) -> str:
        """
        Apply phrase-level dictionary corrections.

        Phrases are applied before word-level corrections to ensure
        longer, more specific matches take priority.

        Args:
            text: Input text.

        Returns:
            Text with phrase corrections applied.
        """
        result = text
        # Sort phrases by length (longest first) to match longer phrases first
        sorted_phrases = sorted(self._phrases.items(), key=lambda x: len(x[0]), reverse=True)
        for phrase, correction in sorted_phrases:
            result = result.replace(phrase, correction)
        return result

    def _apply_word_corrections(self, text: str) -> str:
        """
        Apply word-level dictionary corrections.

        Only corrects entries where the correction differs from the original.

        Args:
            text: Input text.

        Returns:
            Text with word corrections applied.
        """
        result = text
        for wrong, correct in self._corrections.items():
            if wrong != correct:
                result = result.replace(wrong, correct)
        return result

    def _apply_regex_corrections(self, text: str) -> str:
        """
        Apply regex-based correction patterns from the dictionary.

        Args:
            text: Input text.

        Returns:
            Text with regex corrections applied.
        """
        result = text
        for entry in self._regex_patterns:
            pattern = entry.get("pattern", "")
            replacement = entry.get("replacement", "")
            if pattern:
                try:
                    result = re.sub(pattern, replacement, result)
                except re.error:
                    continue
        return result

    def extract_medications(self, text: str) -> list[dict[str, Any]]:
        """
        Extract medication information from medical text.

        Attempts to find drug names, dosages, and frequencies using
        predefined patterns.

        Args:
            text: Medical text (cleaned or raw).

        Returns:
            List of dictionaries, each containing:
            - 'name': Medication name
            - 'dosage': Dosage string
            - 'frequency': Frequency (if detected)
            - 'raw': Raw matched text
        """
        medications: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for pattern in MEDICATION_PATTERNS:
            for match in pattern.finditer(text):
                groups = match.groups()
                name = groups[0].strip() if len(groups) > 0 else ""
                dosage = f"{groups[1]} {groups[2]}" if len(groups) > 2 else (groups[1] if len(groups) > 1 else "")
                frequency = groups[3] if len(groups) > 3 else ""

                if name and name not in seen_names:
                    seen_names.add(name)
                    medications.append({
                        "name": name,
                        "dosage": dosage.strip(),
                        "frequency": frequency.strip(),
                        "raw": match.group(0).strip(),
                    })

        return medications

    def extract_dates(self, text: str) -> list[str]:
        """
        Extract dates from the text.

        Args:
            text: Input text.

        Returns:
            List of date strings found in the text.
        """
        dates: list[str] = []
        for pattern in DATE_PATTERNS:
            dates.extend(pattern.findall(text))
        return dates

    def to_structured(self, text: str) -> dict[str, Any]:
        """
        Convert OCR text into a structured medical record.

        Extracts medications, dates, and segments the text into
        a structured dictionary format.

        Args:
            text: Raw or cleaned OCR text.

        Returns:
            Dictionary with structured medical data:
            - 'raw_text': Original text
            - 'cleaned_text': Cleaned version
            - 'medications': List of extracted medication dicts
            - 'dates': List of extracted date strings
            - 'sections': Text segmented by double newlines
            - 'word_count': Total word count
            - 'has_arabic': Whether Arabic text was detected
        """
        cleaned = self.clean(text)
        sections = [s.strip() for s in cleaned.split("\n\n") if s.strip()]

        return {
            "raw_text": text,
            "cleaned_text": cleaned,
            "medications": self.extract_medications(cleaned),
            "dates": self.extract_dates(cleaned),
            "sections": sections,
            "word_count": len(cleaned.split()),
            "has_arabic": self.normalizer.has_arabic(cleaned),
        }

    def parse_table(self, text: str) -> list[list[str]]:
        """
        Parse tabular data from OCR text.

        Attempts to detect and parse table structures using common
        separator patterns.

        Args:
            text: OCR text containing tabular data.

        Returns:
            List of rows, where each row is a list of cell strings.
        """
        lines = text.strip().split("\n")
        rows: list[list[str]] = []

        for line in lines:
            # Try each separator pattern
            for sep_pattern in TABLE_SEPARATOR_PATTERNS:
                cells = sep_pattern.split(line.strip())
                cells = [c.strip() for c in cells if c.strip()]
                if len(cells) >= 2:
                    rows.append(cells)
                    break
            else:
                # If no separator matched, treat the whole line as one cell
                stripped = line.strip()
                if stripped:
                    rows.append([stripped])

        return rows

    def format_as_json(self, text: str, indent: int = 2) -> str:
        """
        Format cleaned text as a JSON string with structured data.

        Args:
            text: Input OCR text.
            indent: JSON indentation level.

        Returns:
            JSON string with structured medical data.
        """
        structured = self.to_structured(text)
        return json.dumps(structured, ensure_ascii=False, indent=indent)
