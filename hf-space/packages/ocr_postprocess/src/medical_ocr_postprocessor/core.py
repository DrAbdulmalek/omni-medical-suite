"""
Core post-processing engine for medical OCR results.
محرك المعالجة الأساسي لنتائج OCR الطبية.

This module provides the PostProcessor class with methods for:
- Arabic text normalization (alef, yaa, taa marbuta forms)
- Medical term dictionary validation
- Confidence-based filtering
- Single-word and batch correction
"""

from __future__ import annotations

import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process


class CorrectionSource(Enum):
    """Source of a correction suggestion."""
    ARABIC_NORM = "arabic_normalization"
    MEDICAL_DICT = "medical_dictionary"
    FUZZY_MATCH = "fuzzy_match"
    CONFIDENCE_FILTER = "confidence_filter"
    MANUAL = "manual"


@dataclass
class CorrectionResult:
    """Result of correcting a single word.
    نتيجة تصحيح كلمة واحدة."""

    original: str
    corrected: str
    confidence: float
    source: CorrectionSource
    is_modified: bool = False
    medical_term_matched: Optional[str] = None
    alternatives: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.original != self.corrected:
            self.is_modified = True

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "corrected": self.corrected,
            "confidence": round(self.confidence, 4),
            "source": self.source.value,
            "is_modified": self.is_modified,
            "medical_term_matched": self.medical_term_matched,
            "alternatives": self.alternatives,
        }


class PostProcessor:
    """Core post-processing engine for medical OCR output.

    محرك المعالجة الأساسي لمخرجات OCR الطبية.

    Provides Arabic text normalization, medical term validation,
    confidence-based filtering, and both interactive and batch modes.

    Parameters
    ----------
    confidence_threshold : float
        Minimum confidence (0-1) to auto-accept a correction. Default: 0.85.
    medical_terms : list[str] | None
        Custom medical terms dictionary. If None, built-in dictionary is used.
    language : str
        Primary language code. Default: "ar" (Arabic).
    """

    # Arabic character normalization mappings
    ALEF_FORMS = "\u0622\u0623\u0625\u0627"  # ء أ إ ا
    ALEF_TARGET = "\u0627"  # ا

    YAA_FORMS = "\u064a\u0649"  # ي ى
    YAA_TARGET = "\u064a"  # ي

    TAA_MARBUTA = "\u0629"  # ة
    HAA = "\u0647"  # ه

    # Common OCR confusions in Arabic medical text
    ARABIC_OCR_CONFUSIONS: dict[str, str] = {
        "\u062a\u0629": "\u0629",  # تة → ة
        "\u0647\u0627": "\u0629",  # ها → ة (context-dependent)
        "\u0644\u0627": "\u0644\u0627",  # keep لا
    }

    # Built-in medical terms dictionary (Arabic + Latin)
    DEFAULT_MEDICAL_TERMS: dict[str, list[str]] = {
        "ar": [
            # Diagnoses / التشخيصات
            "سكري", "السكري", "ضغط", "ضغط الدم", "ارتفاع الضغط",
            "قلب", "قصور القلب", "ذبحة", "جلطة", "سرطان",
            "التهاب", "حساسية", "ربو", "الربو",
            # Medications / الأدوية
            "ميتفورمين", "أملوديبين", "لوسارتان", "أسيبروبرول",
            "أتورفاستاتين", "أوميبرازول", "باراسيتامول", "إيبوبروفين",
            "إنسولين", "هيبارين", "وارفارين", "أسبرين",
            # Body parts / أجزاء الجسم
            "رأس", "صدر", "بطن", "ظهر", "كتف", "ركبة", "قدم", "يد",
            "كبد", "كلية", "رئة", "معدة", "أمعاء", "أمعاء",
            # Lab values / القيم المخبرية
            "هيموغلوبين", "صفيحات", "كريات", "بيضاء", "حمراء",
            "جلوكوز", "كوليسترول", "كرياتينين", "يوريا",
            # Procedures / الإجراءات
            "عملية", "جراحة", "تنظير", "أشعة", "تصوير", "تحليل",
            "فحص", "تشخيص", "علاج", "متابعة", "مراجعة",
            # Units / الوحدات
            "ملغ", "مليغرام", "جرام", "مل", "مليمتر", "وحدة",
            "ملم/ساعة", "مم زئبق", "درجة",
        ],
        "en": [
            "diabetes", "hypertension", "heart", "failure", "cancer",
            "infection", "allergy", "asthma", "fracture", "surgery",
            "metformin", "amlodipine", "losartan", "atorvastatin",
            "insulin", "aspirin", "ibuprofen", "paracetamol",
            "hemoglobin", "platelets", "glucose", "cholesterol",
            "creatinine", "blood", "pressure", "MRI", "CT", "X-ray",
            "mg", "ml", "mmHg", "unit", "dose",
        ],
    }

    def __init__(
        self,
        confidence_threshold: float = 0.85,
        medical_terms: Optional[list[str]] = None,
        language: str = "ar",
        max_correction_log: int = 10000,
    ):
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(f"confidence_threshold must be 0-1, got {confidence_threshold}")

        self.confidence_threshold = confidence_threshold
        self.language = language
        self._max_correction_log = max_correction_log
        self._correction_log: deque[CorrectionResult] = deque(maxlen=max_correction_log)

        # Build medical terms lookup
        self._medical_terms: set[str] = set()
        if medical_terms is not None:
            self._medical_terms = {t.strip() for t in medical_terms if t.strip()}
        else:
            for lang_terms in self.DEFAULT_MEDICAL_TERMS.values():
                self._medical_terms.update(lang_terms)

    @property
    def correction_log(self) -> list[CorrectionResult]:
        """History of all corrections made during this session."""
        return list(self._correction_log)

    def normalize_arabic(self, text: str) -> str:
        """Normalize Arabic text by unifying character forms.

        توحيد أشكال الحروف العربية:
        - All alef variants → ا (bare alef)
        - All yaa variants → ي (dot below)
        - Remove tatweel (kashida) ـ

        Parameters
        ----------
        text : str
            Input Arabic text.

        Returns
        -------
        str
            Normalized text.
        """
        # Unicode normalization (NFC)
        text = unicodedata.normalize("NFC", text)

        # Remove tatweel / kashida
        text = text.replace("\u0640", "")

        # Normalize alef forms: آ أ إ → ا
        for alef in self.ALEF_FORMS[:-1]:  # skip ا itself (last char)
            text = text.replace(alef, self.ALEF_TARGET)

        # Normalize yaa forms: ى → ي
        text = text.replace("\u0649", self.YAA_TARGET)

        # Normalize taa marbuta in certain contexts
        # ة at end of word is kept; medial ه→ة handled by medical dict

        # Remove diacritics (tashkeel)
        arabic_diacritics = re.compile(
            r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]"
        )
        text = arabic_diacritics.sub("", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def correct_word(
        self,
        word: str,
        ocr_confidence: float = 0.5,
        context: Optional[str] = None,
    ) -> CorrectionResult:
        """Correct a single OCR word using multiple strategies.

        تصحيح كلمة واحدة باستخدام استراتيجيات متعددة:
        1. Arabic normalization
        2. Medical dictionary lookup
        3. Fuzzy matching against known terms

        Parameters
        ----------
        word : str
            The OCR output word to correct.
        ocr_confidence : float
            Confidence score from OCR engine (0-1). Default: 0.5.
        context : str | None
            Surrounding text for context-aware corrections.

        Returns
        -------
        CorrectionResult
            Correction result with original, corrected, and metadata.
        """
        if not word or not word.strip():
            return CorrectionResult(
                original=word,
                corrected=word,
                confidence=ocr_confidence,
                source=CorrectionSource.CONFIDENCE_FILTER,
            )

        word = word.strip()
        corrected = word
        source = CorrectionSource.CONFIDENCE_FILTER
        best_score = ocr_confidence
        medical_match = None
        alternatives: list[str] = []

        # Strategy 1: Arabic normalization
        normalized = self.normalize_arabic(word)
        if normalized != word:
            corrected = normalized
            source = CorrectionSource.ARABIC_NORM
            best_score = max(best_score, 0.7)

        # Strategy 2: Exact medical dictionary match
        if corrected in self._medical_terms:
            medical_match = corrected
            best_score = max(best_score, 0.95)
            source = CorrectionSource.MEDICAL_DICT
        elif normalized in self._medical_terms:
            corrected = normalized
            medical_match = normalized
            best_score = max(best_score, 0.95)
            source = CorrectionSource.MEDICAL_DICT

        # Strategy 3: Fuzzy match against medical dictionary
        if medical_match is None:
            matches = process.extract(
                corrected,
                list(self._medical_terms),
                limit=3,
                scorer=fuzz.ratio,
            )
            if matches and matches[0][1] >= 75:
                fuzzy_score = matches[0][1] / 100.0
                if fuzzy_score > best_score * 0.9:
                    alternatives = [m[0] for m in matches if m[1] >= 65]
                    if fuzzy_score >= self.confidence_threshold:
                        corrected = matches[0][0]
                        medical_match = matches[0][0]
                        best_score = fuzzy_score
                        source = CorrectionSource.FUZZY_MATCH

        result = CorrectionResult(
            original=word,
            corrected=corrected,
            confidence=best_score,
            source=source,
            medical_term_matched=medical_match,
            alternatives=alternatives,
        )

        self._correction_log.append(result)
        return result

    def batch_correct(
        self,
        words: list[str],
        confidences: Optional[list[float]] = None,
        skip_log: bool = False,
    ) -> list[CorrectionResult]:
        """Correct a list of words in batch.

        تصحيح مجموعة كلمات دفعة واحدة.

        Parameters
        ----------
        words : list[str]
            List of OCR output words.
        confidences : list[float] | None
            Per-word confidence scores. If None, 0.5 is used for all.

        Returns
        -------
        list[CorrectionResult]
            List of correction results.
        """
        if confidences is None:
            confidences = [0.5] * len(words)

        if len(confidences) != len(words):
            raise ValueError(
                f"confidences length ({len(confidences)}) must match "
                f"words length ({len(words)})"
            )

        results = []
        for word, conf in zip(words, confidences):
            if skip_log:
                # Direct correction without logging for high-throughput mode
                result = self._correct_word_no_log(word, ocr_confidence=conf)
            else:
                result = self.correct_word(word, ocr_confidence=conf)
            results.append(result)

        return results

    def _correct_word_no_log(
        self,
        word: str,
        ocr_confidence: float = 0.5,
    ) -> CorrectionResult:
        """Correct a single word without appending to the correction log.

        Used in no-review (high-throughput) mode to avoid per-word logging overhead.
        """
        if not word or not word.strip():
            return CorrectionResult(
                original=word,
                corrected=word,
                confidence=ocr_confidence,
                source=CorrectionSource.CONFIDENCE_FILTER,
            )

        word = word.strip()
        corrected = word
        source = CorrectionSource.CONFIDENCE_FILTER
        best_score = ocr_confidence
        medical_match = None
        alternatives: list[str] = []

        # Strategy 1: Arabic normalization
        normalized = self.normalize_arabic(word)
        if normalized != word:
            corrected = normalized
            source = CorrectionSource.ARABIC_NORM
            best_score = max(best_score, 0.7)

        # Strategy 2: Exact medical dictionary match
        if corrected in self._medical_terms:
            medical_match = corrected
            best_score = max(best_score, 0.95)
            source = CorrectionSource.MEDICAL_DICT
        elif normalized in self._medical_terms:
            corrected = normalized
            medical_match = normalized
            best_score = max(best_score, 0.95)
            source = CorrectionSource.MEDICAL_DICT

        # Strategy 3: Fuzzy match against medical dictionary
        if medical_match is None:
            matches = process.extract(
                corrected,
                list(self._medical_terms),
                limit=3,
                scorer=fuzz.ratio,
            )
            if matches and matches[0][1] >= 75:
                fuzzy_score = matches[0][1] / 100.0
                if fuzzy_score > best_score * 0.9:
                    alternatives = [m[0] for m in matches if m[1] >= 65]
                    if fuzzy_score >= self.confidence_threshold:
                        corrected = matches[0][0]
                        medical_match = matches[0][0]
                        best_score = fuzzy_score
                        source = CorrectionSource.FUZZY_MATCH

        return CorrectionResult(
            original=word,
            corrected=corrected,
            confidence=best_score,
            source=source,
            medical_term_matched=medical_match,
            alternatives=alternatives,
        )

    def validate_arabic(self, text: str) -> dict:
        """Validate Arabic text for OCR artifacts and issues.

        التحقق من النص العربي من حيث عيوب OCR.

        Checks for:
        - Non-Arabic characters
        - Suspicious patterns (isolated diacritics, mixed LTR/RTL)
        - Common OCR artifacts
        - Character quality metrics

        Parameters
        ----------
        text : str
            Arabic text to validate.

        Returns
        -------
        dict
            Validation report with keys:
            - is_valid (bool): Overall validity
            - issues (list[dict]): List of found issues
            - metrics (dict): Character statistics
            - normalized_text (str): Normalized version
        """
        issues: list[dict] = []
        arabic_pattern = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

        # Check for non-Arabic/non-common characters
        non_arabic_chars = set()
        for char in text:
            if not (char.isascii() or arabic_pattern.match(char) or char.isspace() or char in ".,;:!?()-/0123456789"):
                non_arabic_chars.add(char)

        if non_arabic_chars:
            issues.append({
                "type": "non_arabic_chars",
                "severity": "warning",
                "message": f"Non-Arabic characters found: {non_arabic_chars}",
                "chars": list(non_arabic_chars),
            })

        # Check for isolated diacritics (common OCR artifact)
        isolated_diacritics = re.findall(
            r"(?:^|\s)[\u064B-\u065F\u0670](?:\s|$)", text
        )
        if isolated_diacritics:
            issues.append({
                "type": "isolated_diacritics",
                "severity": "warning",
                "message": f"Found {len(isolated_diacritics)} isolated diacritic(s)",
            })

        # Check for very short segments (likely OCR noise)
        segments = text.split()
        short_segments = [s for s in segments if len(s.strip()) == 1 and not s.strip().isdigit()]
        if len(short_segments) > len(segments) * 0.3:
            issues.append({
                "type": "excessive_short_segments",
                "severity": "error",
                "message": f"{len(short_segments)}/{len(segments)} segments are single characters",
            })

        # Check for repeated characters (OCR stutter)
        repeated = re.findall(r"(.)\1{3,}", text)
        if repeated:
            issues.append({
                "type": "repeated_chars",
                "severity": "warning",
                "message": f"Found repeated character sequences: {repeated}",
            })

        # Character metrics
        total_chars = len(text)
        arabic_chars = sum(1 for c in text if arabic_pattern.match(c))
        digit_chars = sum(1 for c in text if c.isdigit())
        space_chars = sum(1 for c in text if c.isspace())

        metrics = {
            "total_chars": total_chars,
            "arabic_chars": arabic_chars,
            "arabic_ratio": arabic_chars / total_chars if total_chars > 0 else 0,
            "digit_chars": digit_chars,
            "space_chars": space_chars,
            "word_count": len(segments),
        }

        is_valid = not any(i["severity"] == "error" for i in issues)

        return {
            "is_valid": is_valid,
            "issues": issues,
            "metrics": metrics,
            "normalized_text": self.normalize_arabic(text),
        }

    def validate_medical_terms(self, text: str) -> dict:
        """Validate medical terms found in OCR text.

        التحقق من المصطلحات الطبية في نص OCR.

        Parameters
        ----------
        text : str
            OCR output text to scan for medical terms.

        Returns
        -------
        dict
            Report with keys:
            - found_terms (list[str]): Matched medical terms
            - unmatched_segments (list[str]): Text segments not in dictionary
            - coverage (float): Percentage of text covered by known terms
            - suggestions (list[dict]): Fuzzy match suggestions for unmatched segments
        """
        words = re.findall(r"[\w\u0600-\u06FF]+", text)
        found_terms: list[str] = []
        unmatched: list[str] = []
        suggestions: list[dict] = []

        for word in words:
            normalized = self.normalize_arabic(word)
            if normalized in self._medical_terms:
                found_terms.append(normalized)
            elif word in self._medical_terms:
                found_terms.append(word)
            else:
                unmatched.append(word)
                # Try fuzzy match
                matches = process.extract(
                    normalized,
                    list(self._medical_terms),
                    limit=2,
                    scorer=fuzz.ratio,
                )
                if matches and matches[0][1] >= 60:
                    suggestions.append({
                        "original": word,
                        "suggestion": matches[0][0],
                        "score": matches[0][1],
                    })

        coverage = len(found_terms) / len(words) if words else 0.0

        return {
            "found_terms": found_terms,
            "unmatched_segments": unmatched,
            "coverage": round(coverage, 4),
            "suggestions": suggestions,
            "total_words": len(words),
        }

    def add_medical_terms(self, terms: list[str]) -> int:
        """Add custom medical terms to the dictionary.

        إضافة مصطلحات طبية مخصصة للقاموس.

        Parameters
        ----------
        terms : list[str]
            Terms to add.

        Returns
        -------
        int
            Number of new terms added (duplicates skipped).
        """
        existing_count = len(self._medical_terms)
        for term in terms:
            if isinstance(term, str) and term.strip():
                self._medical_terms.add(term.strip())
        return len(self._medical_terms) - existing_count

    def load_medical_terms_from_file(self, filepath: str | Path) -> int:
        """Load medical terms from a text file (one term per line).

        تحميل مصطلحات طبية من ملف نصي.

        Parameters
        ----------
        filepath : str | Path
            Path to text file with one term per line.

        Returns
        -------
        int
            Number of terms loaded.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Medical terms file not found: {filepath}")

        terms = path.read_text(encoding="utf-8").splitlines()
        terms = [t.strip() for t in terms if t.strip() and not t.startswith("#")]
        return self.add_medical_terms(terms)

    def clear_correction_log(self) -> None:
        """Clear the correction history."""
        self._correction_log.clear()

    def get_stats(self) -> dict:
        """Get statistics about corrections made in this session.

        Returns
        -------
        dict
            Statistics including total corrections, modification rate, etc.
        """
        total = len(self._correction_log)
        modified = sum(1 for r in self._correction_log if r.is_modified)
        medical_matches = sum(1 for r in self._correction_log if r.medical_term_matched)
        avg_confidence = (
            sum(r.confidence for r in self._correction_log) / total
            if total > 0
            else 0.0
        )

        source_counts: dict[str, int] = {}
        for r in self._correction_log:
            key = r.source.value
            source_counts[key] = source_counts.get(key, 0) + 1

        return {
            "total_processed": total,
            "total_modified": modified,
            "modification_rate": round(modified / total, 4) if total > 0 else 0.0,
            "medical_term_matches": medical_matches,
            "average_confidence": round(avg_confidence, 4),
            "sources": source_counts,
        }
