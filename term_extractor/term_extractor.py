#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  BilingualExtractor - TermExtractor Module
  Medical Arabic-English Term Extraction Engine
==============================================================================

Description:
    Extracts bilingual medical terms from parallel Arabic-English textbooks.
    Uses pattern-based extraction with regex, morphological analysis, and
    statistical filtering to identify medical terminology pairs.

Author: BilingualExtractor Team
Version: 1.0.0
License: MIT
"""

import re
import json
import csv
import logging
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter, defaultdict
from difflib import SequenceMatcher

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# =============================================================================
# Logging Configuration
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("TermExtractor")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TermPair:
    """Represents a bilingual term pair (Arabic - English)."""
    arabic_term: str
    english_term: str
    frequency: int = 1
    confidence: float = 0.0
    source_page: int = -1
    category: str = "general"
    context_ar: str = ""
    context_en: str = ""
    variants_ar: List[str] = field(default_factory=list)
    variants_en: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ExtractionConfig:
    """Configuration for the term extraction process."""
    min_term_length_ar: int = 2
    min_term_length_en: int = 2
    max_term_length_ar: int = 6
    max_term_length_en: int = 5
    min_frequency: int = 1
    min_confidence: float = 0.3
    regex_patterns: bool = True
    morphological_analysis: bool = True
    statistical_filtering: bool = True
    deduplication_threshold: float = 0.85
    arabic_dialects: List[str] = field(default_factory=lambda: [
        "modern_standard", "egyptian", "levantine", "gulf"
    ])
    medical_domains: List[str] = field(default_factory=lambda: [
        "orthopedics", "internal_medicine", "surgery", "cardiology",
        "neurology", "pediatrics", "radiology", "pathology"
    ])
    include_context: bool = True
    max_context_length: int = 200

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ExtractionStats:
    """Statistics from the extraction process."""
    total_pages_processed: int = 0
    total_arabic_terms_found: int = 0
    total_english_terms_found: int = 0
    total_pairs_extracted: int = 0
    high_confidence_pairs: int = 0
    medium_confidence_pairs: int = 0
    low_confidence_pairs: int = 0
    processing_time_seconds: float = 0.0
    unique_arabic_terms: int = 0
    unique_english_terms: int = 0
    categories_found: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["categories_found"] = list(self.categories_found)
        return data


# =============================================================================
# Medical Terminology Resources
# =============================================================================

class MedicalTermResources:
    """Pre-loaded medical terminology resources and dictionaries."""

    # Medical prefixes and suffixes in Arabic
    ARABIC_MEDICAL_PREFIXES = [
        "التهاب", "تصلب", "انزلاق", "ارتخاء", "انسداد",
        "انفتاح", "انقلاب", "انتفاخ", "انحلال", "انقباض",
        "تشوه", "تضخم", "تليف", "تنكس", "تصلب"
    ]

    ARABIC_MEDICAL_SUFFIXES = [
        "itis", "osis", "oma", "ectomy", "otomy", "ostomy",
        "plasty", "scopy", "pexy", "rrhaphy", "centesis"
    ]

    ENGLISH_MEDICAL_PREFIXES = [
        "hyper", "hypo", "brady", "tachy", "macro", "micro",
        "mega", "poly", "mono", "bi", "tri", "multi", "neo",
        "dys", "a", "an", "anti", "contra", "co", "counter"
    ]

    ENGLISH_MEDICAL_SUFFIXES = [
        "itis", "osis", "oma", "ectomy", "otomy", "ostomy",
        "plasty", "scopy", "pexy", "rrhaphy", "centesis",
        "algia", "dynia", "penia", "emia", "uria", "logy",
        "genic", "pathy", "stomy", "tomy"
    ]

    # Arabic-English synonym mapping for dialectal variations
    DIALECT_MAPPINGS = {
        # Fracture variants
        "الكُسر": ["الكَسر", "الانكسار", "الكسر"],
        "الشلل": ["الفالج", "الرعاش", "الخدر"],
        # Inflammation variants
        "التهاب": ["ورم", "احتقان"],
        # Blood pressure
        "ضغط الدم": ["ضغط الدم", "الضغط الشرياني"],
        # Joint variants
        "المفصل": ["الرّكبة", "الملتف", "الوصلة"],
        # Pain variants
        "الألم": ["وجع", "ألم"],
        # Swelling variants
        "الورم": ["انتفاخ", "تورم", "سُلّاق"],
    }

    # Historical terminology evolution
    TERMINOLOGY_EVOLUTION = {
        "الفالج": "الشلل (Paralysis)",
        "النواصير": "الناسور (Fistula)",
        "ال بثور": "الحويصلات (Vesicles)",
        "الاستسقاء": "الوذمة (Edema)",
        "اليرقان": "اليرقان/الصفراء (Jaundice)",
        "السل": "السل/الدرن (Tuberculosis)",
        "الحصبة": "الحصبة (Measles)",
        "الطاعون": "الطاعون (Plague)",
    }

    # Category-specific medical terms
    MEDICAL_CATEGORIES = {
        "anatomy": [
            "عظم", "مفصل", "عضلة", "وتر", "غضروف", "أربطة", "نسيج",
            "عمود فقري", "فقرات", "جمجمة", "حوض", "كتف", "كوع", "رسغ"
        ],
        "orthopedics": [
            "كسر", "خلع", "تهتك", "انزلاق غضروفي", "التهاب مفاصل",
            "روماتيزم", "هشاشة عظام", "تقوس", "استقامة", "جبيرة",
            "طوق عنقي", "بدلة طبية", "مسامير", "ألواح معدنية"
        ],
        "cardiology": [
            "قلب", "شريان", "وريد", "صمام", "نظم قلبي", "جلطة",
            "احتشاء", "قصور", "توسع", "تضيق", "رعاش", "خفقان"
        ],
        "neurology": [
            "عصب", "دماغ", "حبل شوكي", "شلل", "تشنج", "صرع",
            "تصلب متعدد", "شلل رعاش", "صداع", "شقيقة", "خدر"
        ],
        "surgery": [
            "عملية جراحية", "شق", "خياطة", "تنظير", "استئصال",
            "ترقيع", "زراعة", "عقيم", "مخدر", "تخدير", "مضاد حيوي"
        ],
        "internal_medicine": [
            "التهاب", "عدوى", "بكتيريا", "فيروس", "فطريات",
            "مناعة", "حساسية", "أورام", "سرطان", "ورم حميد",
            "تمثيل غذائي", "غدد صماء", "هرمون", "سكري"
        ],
        "radiology": [
            "أشعة سينية", "رنين مغناطيسي", "موجات فوق صوتية",
            "تصوير مقطعي", "صورة طبقية", "مادة ظليلة", "تبويض"
        ],
        "pathology": [
            "خلايا", "أنسجة", "فحص مجهري", "تلون", "عينة",
            "خزعة", "تليف", "تنكس", "تكاثر", "تموت"
        ],
    }

    # Common medical stop words (terms to exclude)
    MEDICAL_STOP_WORDS = {
        "في", "من", "إلى", "على", "عن", "مع", "هو", "هي", "هم",
        "كان", "يكون", "قد", "ذلك", "هذا", "هذه", "التي", "الذي",
        "the", "a", "an", "is", "are", "was", "were", "in", "on",
        "at", "to", "from", "with", "by", "for", "of", "and", "or",
        "but", "not", "can", "may", "will", "shall", "should",
    }


# =============================================================================
# Text Preprocessor
# =============================================================================

class TextPreprocessor:
    """Preprocesses Arabic and English text for term extraction."""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self._arabic_char_ranges = self._build_arabic_char_set()

    def _build_arabic_char_set(self) -> Set[str]:
        """Build the set of Arabic Unicode characters."""
        arabic_chars = set()
        for code in range(0x0600, 0x06FF + 1):
            arabic_chars.add(chr(code))
        # Include Arabic extended ranges
        for code in range(0x0750, 0x077F + 1):
            arabic_chars.add(chr(code))
        for code in range(0x08A0, 0x08FF + 1):
            arabic_chars.add(chr(code))
        return arabic_chars

    def normalize_arabic(self, text: str) -> str:
        """Normalize Arabic text for consistent matching."""
        if not text:
            return ""
        # Remove tatweel (kashida)
        text = text.replace("\u0640", "")
        # Normalize alef variants
        text = text.replace("ﺁ", "آ").replace("ﺄ", "أ").replace("ﺇ", "إ")
        # Normalize alef maqsura to ya
        text = text.replace("ﻯ", "ى")
        # Normalize taa marbuta to haa
        text = text.replace("ة", "ه")
        # Normalize waw with hamza
        text = text.replace("ﺆ", "ؤ")
        # Normalize yaa with hamza
        text = text.replace("ﺉ", "ئ")
        # Remove diacritics (tashkeel)
        diacritics = re.compile(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]')
        text = diacritics.sub('', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def normalize_english(self, text: str) -> str:
        """Normalize English text for consistent matching."""
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove special characters except hyphens in medical terms
        text = re.sub(r'[^a-z0-9\s\-]', '', text)
        return text

    def clean_ocr_errors(self, text: str) -> str:
        """Fix common OCR errors in bilingual medical texts."""
        if not text:
            return ""
        # Common OCR substitutions in Arabic
        ocr_corrections = {
            "ﻻ": "لا", "ﻼ": "لا",
            "ـ": "",  # Remove stray tatweel
            "۰": "0", "۱": "1", "۲": "2", "۳": "3",
            "۴": "4", "۵": "5", "۶": "6", "۷": "7",
            "۸": "8", "۹": "9",
        }
        for wrong, correct in ocr_corrections.items():
            text = text.replace(wrong, correct)

        # Fix spacing issues around Arabic parentheses
        text = re.sub(r'\(\s+', '(', text)
        text = re.sub(r'\s+\)', ')', text)

        # Fix mixed-script spacing
        text = re.sub(r'([a-zA-Z])\s+([\u0600-\u06FF])', r'\1\2', text)
        text = re.sub(r'([\u0600-\u06FF])\s+([a-zA-Z])', r'\1\2', text)

        return text.strip()

    def detect_language(self, text: str) -> str:
        """Detect whether text is Arabic, English, or mixed."""
        if not text:
            return "unknown"
        arabic_count = sum(1 for c in text if c in self._arabic_char_ranges)
        latin_count = sum(1 for c in text if c.isascii() and c.isalpha())
        total = arabic_count + latin_count
        if total == 0:
            return "unknown"
        ar_ratio = arabic_count / total
        en_ratio = latin_count / total
        if ar_ratio > 0.7:
            return "arabic"
        elif en_ratio > 0.7:
            return "english"
        else:
            return "mixed"

    def split_bilingual_text(self, text: str) -> Tuple[str, str]:
        """Split a bilingual text into Arabic and English parts."""
        if not text:
            return "", ""
        # Try common delimiter patterns
        delimiters = [
            r'\s*[-–—]\s*',  # Dash-based
            r'\s*[:：]\s*',   # Colon-based
            r'\s*[/]\s*',     # Slash-based
            r'\s*\(\s*',      # Parentheses-based
            r'\n',             # Newline-based
        ]

        for pattern in delimiters:
            parts = re.split(pattern, text, maxsplit=1)
            if len(parts) == 2:
                ar, en = parts
                if self.detect_language(ar) == "arabic" and self.detect_language(en) == "english":
                    return ar.strip(), en.strip()
                elif self.detect_language(en) == "arabic" and self.detect_language(ar) == "english":
                    return en.strip(), ar.strip()

        # Fallback: split by script
        ar_chars = []
        en_chars = []
        for char in text:
            if char in self._arabic_char_ranges:
                ar_chars.append(char)
            elif char.isascii() and (char.isalpha() or char == ' '):
                en_chars.append(char)

        return ''.join(ar_chars).strip(), ''.join(en_chars).strip()


# =============================================================================
# Pattern-Based Term Extractor
# =============================================================================

class PatternExtractor:
    """Extracts medical terms using regex patterns and structural rules."""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self.preprocessor = TextPreprocessor(config)
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile all regex patterns for term extraction."""
        # Arabic medical term patterns
        self.arabic_patterns = [
            # Arabic "الـ" definite article + term + optional modifier
            re.compile(
                r'(?:ال|لل)\s*[\u0600-\u06FF]{2,15}'
                r'(?:\s+[\u0600-\u06FF]{2,10})*'
            ),
            # Medical compound terms with "و" conjunction
            re.compile(
                r'[\u0600-\u06FF]{2,15}'
                r'(?:\s+و\s+[\u0600-\u06FF]{2,15})+'
            ),
            # Terms with "التهاب" prefix
            re.compile(
                r'التهاب\s+[\u0600-\u06FF]{2,15}'
                r'(?:\s+[\u0600-\u06FF]{2,10})*'
            ),
            # Terms with number prefix
            re.compile(
                r'(?:العاشر|الحادي|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع)'
                r'\s+[\u0600-\u06FF]{2,15}'
            ),
            # Generic medical terms (3-20 Arabic chars)
            re.compile(
                r'(?:ال|لل)\s*[\u0600-\u06FF]{3,20}'
                r'(?:\s+(?:ال|لل)?[\u0600-\u06FF]{2,15}){0,4}'
            ),
        ]

        # English medical term patterns
        self.english_patterns = [
            # Latin/Greek medical terms
            re.compile(
                r'[a-zA-Z]{2,}'
                r'(?:\s+[a-zA-Z]{2,}){0,3}'
                r'(?:\s+\([a-zA-Z\s]+\))?'
            ),
            # Terms with hyphens (compound medical terms)
            re.compile(
                r'[a-zA-Z]{2,}(?:-[a-zA-Z]+){1,3}'
            ),
            # Terms in parentheses
            re.compile(
                r'\(([a-zA-Z][a-zA-Z\s\-]{2,40})\)'
            ),
            # Terms followed by abbreviation in parentheses
            re.compile(
                r'([a-zA-Z][a-zA-Z\s]{2,30})\s*\(([A-Z]{2,5})\)'
            ),
        ]

        # Bilingual pair patterns (Arabic term - English term)
        self.bilingual_pair_patterns = [
            # "Arabic (English)" pattern
            re.compile(
                r'([\u0600-\u06FF][\u0600-\u06FF\s]{2,30})'
                r'\s*[-–—:：\(\[]\s*'
                r'([A-Za-z][A-Za-z\s\-]{2,30})'
            ),
            # "Arabic: English" pattern
            re.compile(
                r'([\u0600-\u06FF][\u0600-\u06FF\s]{2,30})'
                r'\s*[:]\s*'
                r'([A-Za-z][A-Za-z\s\-]{2,30})'
            ),
            # "English (Arabic)" reversed pattern
            re.compile(
                r'([A-Za-z][A-Za-z\s\-]{2,30})'
                r'\s*[-–—:：\[\(]\s*'
                r'([\u0600-\u06FF][\u0600-\u06FF\s]{2,30})'
            ),
        ]

    def extract_arabic_terms(self, text: str) -> List[str]:
        """Extract Arabic medical terms from text."""
        text = self.preprocessor.clean_ocr_errors(text)
        terms = set()
        for pattern in self.arabic_patterns:
            for match in pattern.finditer(text):
                term = match.group().strip()
                if self.config.min_term_length_ar <= len(term) <= self.config.max_term_length_ar:
                    normalized = self.preprocessor.normalize_arabic(term)
                    if normalized and normalized not in MedicalTermResources.MEDICAL_STOP_WORDS:
                        terms.add(normalized)
        return list(terms)

    def extract_english_terms(self, text: str) -> List[str]:
        """Extract English medical terms from text."""
        terms = set()
        for pattern in self.english_patterns:
            for match in pattern.finditer(text):
                term = match.group().strip()
                if self.config.min_term_length_en <= len(term) <= self.config.max_term_length_en:
                    normalized = self.preprocessor.normalize_english(term)
                    if normalized and normalized not in MedicalTermResources.MEDICAL_STOP_WORDS:
                        terms.add(normalized)
        return list(terms)

    def extract_bilingual_pairs(self, text: str) -> List[Tuple[str, str]]:
        """Extract bilingual term pairs from parallel text."""
        text = self.preprocessor.clean_ocr_errors(text)
        pairs = []
        seen = set()

        for pattern in self.bilingual_pair_patterns:
            for match in pattern.finditer(text):
                ar_term = match.group(1).strip()
                en_term = match.group(2).strip()

                # Normalize
                ar_norm = self.preprocessor.normalize_arabic(ar_term)
                en_norm = self.preprocessor.normalize_english(en_term)

                # Validate
                if (ar_norm and en_norm and
                    len(ar_norm) >= self.config.min_term_length_ar and
                    len(en_norm) >= self.config.min_term_length_en and
                    (ar_norm, en_norm) not in seen):

                    seen.add((ar_norm, en_norm))
                    pairs.append((ar_norm, en_norm))

        return pairs


# =============================================================================
# Morphological Analyzer
# =============================================================================

class MorphologicalAnalyzer:
    """Lightweight morphological analysis for Arabic medical terms."""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self.prefixes = MedicalTermResources.ARABIC_MEDICAL_PREFIXES
        self.categories = MedicalTermResources.MEDICAL_CATEGORIES

    def categorize_term(self, term: str) -> str:
        """Categorize a medical term into its domain."""
        term_lower = term.lower() if term else ""

        # Check category lists
        for category, terms in self.categories.items():
            for cat_term in terms:
                if cat_term in term or term in cat_term:
                    return category

        # Check prefix-based categories
        if any(term.startswith(prefix) for prefix in self.prefixes):
            if "التهاب" in term:
                return "pathology"
            elif "تصلب" in term:
                return "orthopedics"
            elif "انسداد" in term:
                return "cardiology"
            elif "تضخم" in term:
                return "internal_medicine"

        # Check English suffixes
        for suffix in MedicalTermResources.ENGLISH_MEDICAL_SUFFIXES:
            if term_lower.endswith(suffix):
                return "general_medical"

        return "general"

    def extract_stem(self, arabic_term: str) -> str:
        """Extract the root stem of an Arabic medical term."""
        if not arabic_term:
            return ""
        # Remove definite article
        stem = re.sub(r'^(ال|لل)\s*', '', arabic_term)
        # Remove common suffixes
        stem = re.sub(r'(ية|ي)$', '', stem)
        stem = re.sub(r'(ية|ي)\s*$', '', stem)
        return stem.strip()

    def find_dialect_variants(self, term: str) -> List[str]:
        """Find dialectal variants of a term."""
        variants = []
        for standard, dialect_list in MedicalTermResources.DIALECT_MAPPINGS.items():
            if term in standard or standard in term:
                variants.extend(dialect_list)
        return list(set(variants))

    def check_historical_evolution(self, term: str) -> Optional[str]:
        """Check if a term has a historical evolution/modern equivalent."""
        for old_term, new_term in MedicalTermResources.TERMINOLOGY_EVOLUTION.items():
            if term in old_term or old_term in term:
                return new_term
        return None


# =============================================================================
# Statistical Filter
# =============================================================================

class StatisticalFilter:
    """Statistical methods for filtering and ranking extracted terms."""

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()

    def calculate_confidence(self, ar_term: str, en_term: str,
                             ar_freq: int, en_freq: int,
                             co_occurrence: int) -> float:
        """Calculate confidence score for a term pair."""
        confidence = 0.0

        # Frequency component (0-0.3)
        freq_score = min(co_occurrence / 5.0, 1.0) * 0.3
        confidence += freq_score

        # Length balance component (0-0.2)
        ar_len = len(ar_term)
        en_len = len(en_term)
        if ar_len > 0 and en_len > 0:
            length_ratio = min(ar_len, en_len) / max(ar_len, en_len)
            confidence += length_ratio * 0.2

        # Co-occurrence strength (0-0.3)
        if ar_freq > 0 and en_freq > 0:
            pmi = co_occurrence / (ar_freq * en_freq)
            pmi_score = min(pmi * 10, 1.0) * 0.3
            confidence += pmi_score

        # Medical domain bonus (0-0.2)
        medical_keywords = {
            "itis", "osis", "oma", "ectomy", "otomy",
            "التهاب", "كسر", "مفصل", "عظم", "عملية"
        }
        has_medical = any(kw in ar_term.lower() or kw in en_term.lower()
                         for kw in medical_keywords)
        if has_medical:
            confidence += 0.2

        return round(min(confidence, 1.0), 4)

    def deduplicate_terms(self, terms: List[TermPair]) -> List[TermPair]:
        """Remove duplicate terms using fuzzy matching."""
        unique_terms = []
        seen_normalized = {}

        for term in terms:
            ar_norm = term.arabic_term.strip().lower()
            en_norm = term.english_term.strip().lower()

            # Check for near-duplicates
            is_dup = False
            for seen_ar, seen_en in seen_normalized.keys():
                ar_sim = SequenceMatcher(None, ar_norm, seen_ar).ratio()
                en_sim = SequenceMatcher(None, en_norm, seen_en).ratio()
                if ar_sim >= self.config.deduplication_threshold and \
                   en_sim >= self.config.deduplication_threshold:
                    # Keep the one with higher confidence
                    if term.confidence > seen_normalized[(seen_ar, seen_en)].confidence:
                        idx = unique_terms.index(seen_normalized[(seen_ar, seen_en)])
                        unique_terms[idx] = term
                    is_dup = True
                    break

            if not is_dup:
                seen_normalized[(ar_norm, en_norm)] = term
                unique_terms.append(term)

        return unique_terms

    def rank_by_frequency(self, terms: List[TermPair]) -> List[TermPair]:
        """Rank terms by frequency."""
        return sorted(terms, key=lambda t: t.frequency, reverse=True)

    def rank_by_confidence(self, terms: List[TermPair]) -> List[TermPair]:
        """Rank terms by confidence score."""
        return sorted(terms, key=lambda t: t.confidence, reverse=True)


# =============================================================================
# Main TermExtractor Class
# =============================================================================

class TermExtractor:
    """
    Main class for extracting bilingual medical terms from parallel text.

    Usage:
        >>> extractor = TermExtractor()
        >>> extractor.load_text_file("textbook_page.txt")
        >>> terms = extractor.extract_terms()
        >>> extractor.export_to_csv("output/terms.csv")
    """

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self.preprocessor = TextPreprocessor(config)
        self.pattern_extractor = PatternExtractor(config)
        self.morph_analyzer = MorphologicalAnalyzer(config)
        self.stat_filter = StatisticalFilter(config)
        self.stats = ExtractionStats()

        # Internal storage
        self._raw_text: str = ""
        self._pages: Dict[int, str] = {}
        self._term_pairs: Dict[Tuple[str, str], TermPair] = {}
        self._arabic_term_freq: Counter = Counter()
        self._english_term_freq: Counter = Counter()

    def load_text(self, text: str) -> 'TermExtractor':
        """Load text for extraction."""
        self._raw_text = text
        logger.info(f"Loaded {len(text)} characters of text")
        return self

    def load_text_file(self, file_path: str, encoding: str = 'utf-8') -> 'TermExtractor':
        """Load text from a file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, 'r', encoding=encoding) as f:
            self._raw_text = f.read()

        logger.info(f"Loaded {len(self._raw_text)} characters from {file_path}")
        return self

    def load_directory(self, dir_path: str, extensions: List[str] = None,
                      encoding: str = 'utf-8') -> 'TermExtractor':
        """Load all text files from a directory."""
        if extensions is None:
            extensions = ['.txt', '.text', '.md']

        path = Path(dir_path)
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        all_text = []
        for ext in extensions:
            for file in path.rglob(f'*{ext}'):
                with open(file, 'r', encoding=encoding) as f:
                    all_text.append(f.read())
                logger.info(f"Loaded file: {file.name}")

        self._raw_text = '\n\n'.join(all_text)
        logger.info(f"Loaded {len(all_text)} files, total {len(self._raw_text)} characters")
        return self

    def load_parallel_files(self, ar_file: str, en_file: str,
                           encoding: str = 'utf-8') -> 'TermExtractor':
        """Load parallel Arabic and English files."""
        with open(ar_file, 'r', encoding=encoding) as f:
            ar_text = f.read()
        with open(en_file, 'r', encoding=encoding) as f:
            en_text = f.read()

        # Combine with delimiters for parallel processing
        self._raw_text = f"{ar_text}\n---SEPARATOR---\n{en_text}"
        logger.info("Loaded parallel files")
        return self

    def extract_terms(self) -> List[TermPair]:
        """
        Main extraction method. Extracts bilingual term pairs from loaded text.

        Returns:
            List of TermPair objects sorted by confidence.
        """
        import time
        start_time = time.time()

        if not self._raw_text:
            logger.warning("No text loaded. Call load_text() or load_text_file() first.")
            return []

        logger.info("Starting term extraction...")

        # Step 1: Extract bilingual pairs using patterns
        if self.config.regex_patterns:
            pairs = self.pattern_extractor.extract_bilingual_pairs(self._raw_text)
            logger.info(f"Pattern extraction found {len(pairs)} candidate pairs")

            for ar_term, en_term in pairs:
                self._add_term_pair(ar_term, en_term)

        # Step 2: Extract individual terms for frequency counting
        ar_terms = self.pattern_extractor.extract_arabic_terms(self._raw_text)
        en_terms = self.pattern_extractor.extract_english_terms(self._raw_text)

        self._arabic_term_freq.update(ar_terms)
        self._english_term_freq.update(en_terms)

        self.stats.total_arabic_terms_found = sum(self._arabic_term_freq.values())
        self.stats.total_english_terms_found = sum(self._english_term_freq.values())
        self.stats.unique_arabic_terms = len(self._arabic_term_freq)
        self.stats.unique_english_terms = len(self._english_term_freq)

        # Step 3: Categorize and enrich terms
        if self.config.morphological_analysis:
            for key, pair in list(self._term_pairs.items()):
                pair.category = self.morph_analyzer.categorize_term(pair.arabic_term)
                pair.variants_ar = self.morph_analyzer.find_dialect_variants(pair.arabic_term)
                historical = self.morph_analyzer.check_historical_evolution(pair.arabic_term)
                if historical:
                    pair.variants_ar.append(historical)
                self.stats.categories_found.add(pair.category)

        # Step 4: Calculate confidence scores
        for key, pair in self._term_pairs.items():
            ar_freq = self._arabic_term_freq.get(pair.arabic_term, 0)
            en_freq = self._english_term_freq.get(pair.english_term, 0)
            pair.confidence = self.stat_filter.calculate_confidence(
                pair.arabic_term, pair.english_term,
                ar_freq, en_freq, pair.frequency
            )

        # Step 5: Filter and deduplicate
        all_pairs = list(self._term_pairs.values())
        if self.config.statistical_filtering:
            all_pairs = self.stat_filter.deduplicate_terms(all_pairs)
            all_pairs = [p for p in all_pairs if p.confidence >= self.config.min_confidence]

        # Step 6: Sort by confidence
        all_pairs = self.stat_filter.rank_by_confidence(all_pairs)

        # Update statistics
        self.stats.total_pairs_extracted = len(all_pairs)
        self.stats.high_confidence_pairs = sum(1 for p in all_pairs if p.confidence >= 0.7)
        self.stats.medium_confidence_pairs = sum(1 for p in all_pairs if 0.4 <= p.confidence < 0.7)
        self.stats.low_confidence_pairs = sum(1 for p in all_pairs if p.confidence < 0.4)
        self.stats.processing_time_seconds = round(time.time() - start_time, 2)

        logger.info(f"Extraction complete: {self.stats.total_pairs_extracted} pairs "
                    f"in {self.stats.processing_time_seconds}s")
        logger.info(f"  High confidence: {self.stats.high_confidence_pairs}")
        logger.info(f"  Medium confidence: {self.stats.medium_confidence_pairs}")
        logger.info(f"  Low confidence: {self.stats.low_confidence_pairs}")

        return all_pairs

    def _add_term_pair(self, ar_term: str, en_term: str) -> None:
        """Add or update a term pair."""
        key = (ar_term, en_term)
        if key in self._term_pairs:
            self._term_pairs[key].frequency += 1
        else:
            self._term_pairs[key] = TermPair(
                arabic_term=ar_term,
                english_term=en_term,
                frequency=1,
                confidence=0.0,
                category="general"
            )

    def get_stats(self) -> Dict:
        """Get extraction statistics."""
        return self.stats.to_dict()

    def get_terms_by_category(self, category: str) -> List[TermPair]:
        """Get terms filtered by category."""
        return [t for t in self._term_pairs.values() if t.category == category]

    def get_high_confidence_terms(self, threshold: float = 0.7) -> List[TermPair]:
        """Get high-confidence term pairs."""
        return [t for t in self._term_pairs.values() if t.confidence >= threshold]

    # =========================================================================
    # Export Methods
    # =========================================================================

    def export_to_csv(self, output_path: str,
                      include_variants: bool = False) -> str:
        """
        Export term pairs to CSV format.

        Args:
            output_path: Path to save the CSV file
            include_variants: Whether to include dialectal variants

        Returns:
            Path to the saved file
        """
        terms = self.stat_filter.rank_by_confidence(list(self._term_pairs.values()))

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            headers = ["Arabic Term", "English Term", "Frequency",
                       "Confidence", "Category"]
            if include_variants:
                headers.extend(["Arabic Variants", "English Variants", "Context (AR)", "Context (EN)"])
            writer.writerow(headers)

            for term in terms:
                row = [
                    term.arabic_term,
                    term.english_term,
                    term.frequency,
                    term.confidence,
                    term.category
                ]
                if include_variants:
                    row.extend([
                        " | ".join(term.variants_ar) if term.variants_ar else "",
                        " | ".join(term.variants_en) if term.variants_en else "",
                        term.context_ar,
                        term.context_en
                    ])
                writer.writerow(row)

        logger.info(f"Exported {len(terms)} terms to CSV: {output_path}")
        return str(path)

    def export_to_tsv(self, output_path: str) -> str:
        """Export term pairs to TSV format."""
        terms = self.stat_filter.rank_by_confidence(list(self._term_pairs.values()))

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(["Arabic", "English", "Frequency", "Confidence", "Category"])
            for term in terms:
                writer.writerow([
                    term.arabic_term, term.english_term,
                    term.frequency, term.confidence, term.category
                ])

        logger.info(f"Exported {len(terms)} terms to TSV: {output_path}")
        return str(path)

    def export_to_json(self, output_path: str) -> str:
        """Export term pairs and statistics to JSON format."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "statistics": self.stats.to_dict(),
            "config": self.config.to_dict(),
            "terms": [t.to_dict() for t in
                     self.stat_filter.rank_by_confidence(list(self._term_pairs.values()))]
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(data['terms'])} terms to JSON: {output_path}")
        return str(path)

    def export_to_excel(self, output_path: str) -> str:
        """Export term pairs to Excel format (requires pandas)."""
        if not PANDAS_AVAILABLE:
            logger.warning("pandas not available. Install with: pip install pandas openpyxl")
            return self.export_to_csv(output_path.replace('.xlsx', '.csv'))

        terms = self.stat_filter.rank_by_confidence(list(self._term_pairs.values()))
        data = [{
            "Arabic Term": t.arabic_term,
            "English Term": t.english_term,
            "Frequency": t.frequency,
            "Confidence": t.confidence,
            "Category": t.category,
            "Arabic Variants": " | ".join(t.variants_ar) if t.variants_ar else "",
            "English Variants": " | ".join(t.variants_en) if t.variants_en else "",
        } for t in terms]

        df = pd.DataFrame(data)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(path, index=False, engine='openpyxl')

        logger.info(f"Exported {len(terms)} terms to Excel: {output_path}")
        return str(path)


# =============================================================================
# Demo / Test Function
# =============================================================================

def demo_extraction():
    """Run a demonstration of the term extraction on sample medical text."""
    sample_text = """
    الكتاب المرجعي في جراحة العظام والكسور
    Orthopedic Surgery Reference Book

    الفصل الأول: مقدمة في جراحة العظام
    Chapter 1: Introduction to Orthopedic Surgery

    الكسر (Fracture) هو انقطاع في استمرارية العظم الناتج عن إصابة أو مرض.
    A fracture is a discontinuity in bone continuity resulting from injury or disease.

    أنواع الكسور (Types of Fractures):
    1. الكسر البسيط (Simple Fracture) - كسر لا يخترق الجلد
    2. الكسر المركب (Compound Fracture) - كسر يخترق الجلد
    3. كسر ملتوي (Spiral Fracture) - ناتج عن قوة التواء
    4. كسر مضغوط (Compression Fracture) - ناتج عن ضغط مباشر
    5. الكسر المفصلي (Articular Fracture) - يمتد إلى سطح المفصل

    التهاب المفاصل (Arthritis) هو التهاب يصيب المفاصل causing pain and stiffness.
    أنواع التهاب المفاصل تشمل:
    - التهاب المفاصل الروماتويدي (Rheumatoid Arthritis)
    - التهاب المفاصل التنكسي (Osteoarthritis)
    - التهاب المفاصل النقرسي (Gouty Arthritis)

    الانزلاق الغضروفي (Herniated Disc) يحدث عندما ينتفخ النواة اللبية
    للقرص الفقري (Spinal Disc) ويضغط على الأعصاب.

    هشاشة العظام (Osteoporosis) هي حالة ضعف العظام التي تزيد من خطر الكسر.
    Bone density test is used to diagnose osteoporosis.

    عملية استئصال الغدة الدرقية (Thyroidectomy) involve removal of thyroid gland.
    The surgeon performs thyroidectomy under general anesthesia.

    شلل الأطفال (Poliomyelitis) كان يسمى قديما بالفالج.
    Paralysis can affect one side (hemiplegia) or both sides (paraplegia).

    الفحص بالأشعة السينية (X-ray Examination) هو أول خطوة في تشخيص الكسور.
    التصوير بالرنين المغناطيسي (MRI) gives detailed images of soft tissues.
    """

    print("=" * 70)
    print("  BilingualExtractor - TermExtractor Demo")
    print("=" * 70)
    print()

    # Create extractor with default config
    extractor = TermExtractor()
    extractor.load_text(sample_text)

    # Run extraction
    terms = extractor.extract_terms()

    # Display results
    print(f"\n📊 Extraction Results:")
    print(f"   Total pairs found: {len(terms)}")
    print()

    print(f"{'#':<4} {'Arabic Term':<30} {'English Term':<30} {'Conf':<8} {'Cat':<15}")
    print("-" * 90)
    for i, term in enumerate(terms[:20], 1):
        print(f"{i:<4} {term.arabic_term:<30} {term.english_term:<30} "
              f"{term.confidence:<8.3f} {term.category:<15}")

    # Print statistics
    stats = extractor.get_stats()
    print(f"\n📈 Statistics:")
    print(f"   Processing time: {stats['processing_time_seconds']}s")
    print(f"   High confidence pairs: {stats['high_confidence_pairs']}")
    print(f"   Categories found: {stats['categories_found']}")

    # Export to CSV
    output_dir = Path("/home/z/my-project/download/bilingual-extractor/output")
    csv_path = extractor.export_to_csv(str(output_dir / "demo_terms.csv"))
    json_path = extractor.export_to_json(str(output_dir / "demo_terms.json"))

    print(f"\n📁 Exported files:")
    print(f"   CSV: {csv_path}")
    print(f"   JSON: {json_path}")

    return extractor, terms


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="BilingualExtractor - Extract Arabic-English Medical Terms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python term_extractor.py --file textbook.txt --output terms.csv
  python term_extractor.py --dir ./books/ --output all_terms.csv
  python term_extractor.py --demo
  python term_extractor.py --file textbook.txt --format json --output terms.json
        """
    )

    parser.add_argument('--file', '-f', type=str, help='Input text file path')
    parser.add_argument('--dir', '-d', type=str, help='Input directory path')
    parser.add_argument('--ar-file', type=str, help='Arabic parallel file')
    parser.add_argument('--en-file', type=str, help='English parallel file')
    parser.add_argument('--output', '-o', type=str, default='output/terms.csv',
                        help='Output file path')
    parser.add_argument('--format', type=str, default='csv',
                        choices=['csv', 'tsv', 'json', 'excel'],
                        help='Output format')
    parser.add_argument('--demo', action='store_true',
                        help='Run demonstration with sample text')
    parser.add_argument('--min-confidence', type=float, default=0.3,
                        help='Minimum confidence threshold')
    parser.add_argument('--min-frequency', type=int, default=1,
                        help='Minimum frequency threshold')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.demo:
        demo_extraction()
    elif args.file:
        config = ExtractionConfig(
            min_confidence=args.min_confidence,
            min_frequency=args.min_frequency
        )
        extractor = TermExtractor(config)
        extractor.load_text_file(args.file)
        terms = extractor.extract_terms()

        if args.format == 'csv':
            extractor.export_to_csv(args.output)
        elif args.format == 'tsv':
            extractor.export_to_tsv(args.output)
        elif args.format == 'json':
            extractor.export_to_json(args.output)
        elif args.format == 'excel':
            extractor.export_to_excel(args.output)

        print(f"Extracted {len(terms)} term pairs -> {args.output}")
    elif args.dir:
        config = ExtractionConfig(
            min_confidence=args.min_confidence,
            min_frequency=args.min_frequency
        )
        extractor = TermExtractor(config)
        extractor.load_directory(args.dir)
        terms = extractor.extract_terms()

        if args.format == 'csv':
            extractor.export_to_csv(args.output)
        elif args.format == 'tsv':
            extractor.export_to_tsv(args.output)
        elif args.format == 'json':
            extractor.export_to_json(args.output)
        elif args.format == 'excel':
            extractor.export_to_excel(args.output)

        print(f"Extracted {len(terms)} term pairs -> {args.output}")
    elif args.ar_file and args.en_file:
        config = ExtractionConfig(
            min_confidence=args.min_confidence,
            min_frequency=args.min_frequency
        )
        extractor = TermExtractor(config)
        extractor.load_parallel_files(args.ar_file, args.en_file)
        terms = extractor.extract_terms()

        if args.format == 'csv':
            extractor.export_to_csv(args.output)
        elif args.format == 'tsv':
            extractor.export_to_tsv(args.output)
        elif args.format == 'json':
            extractor.export_to_json(args.output)
        elif args.format == 'excel':
            extractor.export_to_excel(args.output)

        print(f"Extracted {len(terms)} term pairs -> {args.output}")
    else:
        parser.print_help()
