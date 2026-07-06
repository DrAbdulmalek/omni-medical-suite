"""
AI Fuel Engine - Keyword Router Module

Fast keyword-based classification — Layer 1 of the hierarchical classifier.
Uses an inverted keyword index with weighted voting to produce high-confidence
classifications in under 1 ms per text chunk.

The KeywordRouter supports Arabic and English medical terminology with a
comprehensive built-in taxonomy covering 20+ medical categories.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import unicodedata
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.schemas import ClassificationMethod, ClassificationResult

logger = logging.getLogger(__name__)


class KeywordRouter:
    """Fast keyword-based classification — Layer 1 of hierarchical classifier.

    Builds an inverted index mapping each keyword to its category and uses
    weighted voting to produce a :class:`ClassificationResult` with a confidence
    score.  If the top-score exceeds the configured ``threshold`` the result is
    returned immediately; otherwise ``None`` is returned so that downstream
    classifiers (semantic, LLM) can attempt classification.

    Features:
        - Multi-language support (Arabic + English).
        - Regex and substring matching for compound terms.
        - Inverted index with keyword weighting for speed.
        - Configurable confidence threshold.

    Args:
        taxonomy_path: Path to a JSON taxonomy file.  When ``None`` the
            built-in medical taxonomy is used.
        threshold: Minimum confidence score to accept a keyword match
            (default ``0.85``).
    """

    # ── Defaults ─────────────────────────────────────────────────────
    _DEFAULT_TAXONOMY_PATH: str = os.path.join(
        os.path.dirname(__file__), "medical_taxonomy.json"
    )
    _DEFAULT_THRESHOLD: float = 0.85

    # ── Arabic normalisation patterns ───────────────────────────────────
    _ARABIC_NORMALIZATION_MAP: Dict[str, str] = {
        "\u0623": "\u0627",  # Hamza on Alef → Alef
        "\u0625": "\u0627",  # Hamza below Alef → Alef
        "\u0624": "\u0627",  # Hamza on Waw → Alef
        "\u0626": "\u0627",  # Hamza on Ya → Alef
        "\u0649": "\u064a",  # Alef Maqsura → Ya
    }
    _ARABIC_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")

    def __init__(
        self,
        taxonomy_path: Optional[str] = None,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        self.threshold: float = threshold

        # ── Keyword index structures ───────────────────────────────────
        # inverted_index[word] → list of (category_id, weight)
        self._inverted_index: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        # category_keywords[category_id] → set of all keywords for that category
        self._category_keywords: Dict[str, Set[str]] = defaultdict(set)
        # category_names[category_id] → (name_en, name_ar)
        self._category_names: Dict[str, Tuple[str, str]] = {}
        # category_descriptions[category_id] → (desc_en, desc_ar)
        self._category_descriptions: Dict[str, Tuple[str, str]] = {}
        # Total keyword count per category (for confidence normalisation)
        self._category_keyword_counts: Dict[str, int] = {}

        self._taxonomy_path = taxonomy_path or self._DEFAULT_TAXONOMY_PATH
        self._load_taxonomy()

        logger.info(
            "KeywordRouter initialised with %d categories and %d indexed keywords",
            len(self._category_names),
            sum(len(kw) for kw in self._category_keywords.values()),
        )

    # ── Taxonomy loading ──────────────────────────────────────────────

    def _load_taxonomy(self) -> None:
        """Load taxonomy from JSON file or fall back to built-in defaults."""
        path = Path(self._taxonomy_path)
        if path.exists():
            logger.info("Loading taxonomy from %s", path)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self._build_index_from_taxonomy(data)
                return
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "Failed to parse taxonomy JSON at %s: %s — falling back to defaults",
                    path,
                    exc,
                )

        logger.info("Using built-in default taxonomy")
        self._build_index_from_taxonomy(self._build_default_taxonomy())

    def _build_index_from_taxonomy(self, data: Dict) -> None:
        """Build the inverted keyword index from taxonomy data."""
        categories = data.get("categories", [])
        if not categories:
            raise ValueError("Taxonomy contains no categories")

        for cat in categories:
            cat_id: str = cat["id"]
            self._category_names[cat_id] = (cat.get("name_en", cat_id), cat.get("name_ar", ""))
            self._category_descriptions[cat_id] = (
                cat.get("description_en", ""),
                cat.get("description_ar", ""),
            )

            # ── English keywords ────────────────────────────────────────
            en_keywords: List[str] = cat.get("keywords_en", [])
            self._index_keywords(cat_id, en_keywords, lang="en")

            # ── Arabic keywords ───────────────────────────────────────
            ar_keywords: List[str] = cat.get("keywords_ar", [])
            self._index_keywords(cat_id, ar_keywords, lang="ar")

            self._category_keyword_counts[cat_id] = len(
                self._category_keywords[cat_id]
            )

    def _index_keywords(self, cat_id: str, keywords: List[str], lang: str = "en") -> None:
        """Index a list of keywords into the inverted index."""
        for keyword in keywords:
            if not keyword or not keyword.strip():
                continue

            kw = keyword.strip().lower()

            # Arabic normalisation
            if lang == "ar":
                kw = self._normalize_arabic(kw)

            self._category_keywords[cat_id].add(kw)

            # Weight: longer phrases are more specific → higher weight
            weight = min(1.0, 0.5 + len(kw.split()) * 0.25)
            if lang == "ar":
                # Slight boost for Arabic matches (medical Arabic is very specific)
                weight = min(1.0, weight * 1.05)

            self._inverted_index[kw].append((cat_id, weight))

    # ── Classification ────────────────────────────────────────────────

    def classify(self, text: str, chunk_id: str = "unknown") -> Optional[ClassificationResult]:
        """Classify text using keyword matching.

        Tokenises the input text, looks up matching keywords in the inverted
        index, and uses weighted voting to determine the best category.

        Args:
            text: The text to classify.
            chunk_id: Identifier for the text chunk (used in the result).

        Returns:
            A :class:`ClassificationResult` if confidence >= ``threshold``,
            otherwise ``None``.
        """
        start = time.perf_counter()

        if not text or not text.strip():
            return None

        # ── Score accumulation ────────────────────────────────────────
        scores: Dict[str, float] = defaultdict(float)
        match_counts: Dict[str, int] = defaultdict(int)
        matched_keywords: Dict[str, Set[str]] = defaultdict(set)

        # Tokenise input text into overlapping n-grams for matching
        tokens = self._tokenize(text)

        for token in tokens:
            # Direct lookup in inverted index
            for cat_id, weight in self._inverted_index.get(token, []):
                scores[cat_id] += weight
                match_counts[cat_id] += 1
                matched_keywords[cat_id].add(token)

            # Also try substring matching for multi-word keywords
            # (e.g., "acute kidney injury" should match text containing it)
            # This is handled via n-gram tokenisation already.

        if not scores:
            logger.debug("No keyword matches found for chunk %s", chunk_id)
            return None

        # ── Normalise scores ────────────────────────────────────────────
        # Use a combination of absolute match strength and relative dominance:
        #   1. Match density — how concentrated the keyword hits are (log-scaled)
        #   2. Relative score — share of total matched weight (dominance)
        #   3. Specificity boost — longer / multi-word matches add confidence
        total_raw_score = sum(scores.values()) or 1.0

        results: List[Tuple[str, float]] = []
        for cat_id, raw_score in scores.items():
            n_matches = match_counts[cat_id]

            # (a) Match density: log-scaled count relative to category size
            total_keywords = self._category_keyword_counts.get(cat_id, 1)
            log_density = min(1.0, math.log1p(n_matches) / math.log1p(total_keywords))

            # (b) Relative dominance: this category's share of all matched weight
            relative_score = raw_score / total_raw_score

            # (c) Specificity: average weight per match (longer phrases score higher)
            avg_weight = raw_score / max(n_matches, 1)

            # Combine: density provides floor, dominance provides ceiling
            confidence = min(
                1.0,
                (log_density * 0.40 + relative_score * 0.40 + avg_weight * 0.20) * 2.0,
            )
            results.append((cat_id, confidence))

        # Sort by confidence descending
        results.sort(key=lambda x: x[1], reverse=True)

        best_cat_id, best_confidence = results[0]

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if best_confidence < self.threshold:
            logger.debug(
                "Best keyword score %.3f < threshold %.3f for chunk %s",
                best_confidence,
                self.threshold,
                chunk_id,
            )
            return None

        # ── Build alternatives ─────────────────────────────────────────
        alternatives = [
            {"category": cat_id, "confidence": conf}
            for cat_id, conf in results[1:6]  # top 5 alternatives
        ]

        name_en, name_ar = self._category_names.get(best_cat_id, (best_cat_id, ""))

        result = ClassificationResult(
            chunk_id=chunk_id,
            category=best_cat_id,
            subcategory=name_ar if name_ar else None,
            confidence=round(best_confidence, 4),
            method=ClassificationMethod.KEYWORD,
            alternatives=alternatives,
            processing_time_ms=round(elapsed_ms, 2),
        )

        logger.info(
            "Keyword classification: chunk=%s category=%s confidence=%.3f (%.1fms)",
            chunk_id,
            best_cat_id,
            best_confidence,
            elapsed_ms,
        )
        return result

    # ── Tokenisation ───────────────────────────────────────────────────

    def _tokenize(self, text: str) -> List[str]:
        """Tokenise text into normalised tokens including Arabic normalisation.

        Generates unigrams and bigrams (and trigrams for short texts) to
        capture multi-word keyword matches.

        Args:
            text: The raw input text.

        Returns:
            A list of normalised token strings.
        """
        # Normalise whitespace
        text = re.sub(r"\s+", " ", text.strip())

        # Detect Arabic content and normalise
        has_arabic = any(
            "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F"
            for ch in text
        )

        if has_arabic:
            text = self._normalize_arabic(text)

        # Lowercase for English
        text = text.lower()

        # Extract unigrams
        unigrams = text.split()

        # Generate bigrams for multi-word keyword matching
        bigrams = [f"{unigrams[i]} {unigrams[i+1]}" for i in range(len(unigrams) - 1)]

        # Generate trigrams for short texts
        trigrams = []
        if len(unigrams) <= 20:
            trigrams = [f"{unigrams[i]} {unigrams[i+1]} {unigrams[i+2]}" for i in range(len(unigrams) - 2)]

        # Merge all tokens (unigrams + bigrams + trigrams)
        all_tokens = unigrams + bigrams + trigrams

        # Deduplicate while preserving order
        seen: Set[str] = set()
        unique_tokens: List[str] = []
        for token in all_tokens:
            if token not in seen:
                seen.add(token)
                unique_tokens.append(token)

        return unique_tokens

    # ── Arabic text handling ───────────────────────────────────────────

    @classmethod
    def _normalize_arabic(cls, text: str) -> str:
        """Normalise Arabic text by removing diacritics and standardising letters.

        Converts Alef variants (Hamza, Alef Maqsura) to plain Alef and
        strips all tashkeel (diacritical marks).

        Args:
            text: Raw Arabic text.

        Returns:
            Normalised Arabic string.
        """
        # Strip diacritics (tashkeel)
        text = cls._ARABIC_DIACRITICS_RE.sub("", text)

        # Normalise letter forms
        for src, dst in cls._ARABIC_NORMALIZATION_MAP.items():
            text = text.replace(src, dst)

        return text

    # ── Default taxonomy ──────────────────────────────────────────────

    @staticmethod
    def _build_default_taxonomy() -> Dict:
        """Built-in medical taxonomy with Arabic and English keywords.

        This serves as a fallback when no external taxonomy file is available.

        Returns:
            A taxonomy dictionary matching the JSON schema.
        """
        return {
            "version": "1.0.0",
            "description": "Built-in fallback medical taxonomy for the AI Fuel Engine.",
            "categories": [
                {
                    "id": "orthopedics",
                    "name_en": "Orthopedics",
                    "name_ar": "جراحة العظام",
                    "keywords_en": [
                        "orthopedic", "orthopaedic", "fracture", "bone", "joint",
                        "spine", "spinal", "vertebra", "disc", "herniation",
                        "scoliosis", "arthritis", "osteoarthritis", "osteoporosis",
                        "femur", "tibia", "humerus", "pelvis", "acl", "meniscus",
                        "ligament", "tendon", "rotator cuff", "arthroscopy",
                        "replacement", "implant", "fixation", "casting", "splint",
                    ],
                    "keywords_ar": [
                        "جراحة العظام", "عظام", "كسر", "مفصل", "عمود فقري",
                        "فقرات", "فتق", "جنف", "التهاب مفاصل", "هشاشة العظام",
                        "فخذ", "قصبة", "حوض", "رباط", "وتر", "جبيرة",
                        "طبيب عظام", "كسر مغلق", "كسر مفتوح", "خشونة المفاصل",
                    ],
                },
                {
                    "id": "cardiology",
                    "name_en": "Cardiology",
                    "name_ar": "أمراض القلب",
                    "keywords_en": [
                        "cardiology", "cardiac", "heart", "coronary", "myocardial",
                        "infarction", "angina", "atherosclerosis", "ischemia",
                        "heart failure", "arrhythmia", "fibrillation", "valve",
                        "stent", "bypass", "ecg", "ekg", "echocardiogram",
                        "hypertension", "cholesterol", "troponin", "cardiomyopathy",
                    ],
                    "keywords_ar": [
                        "أمراض القلب", "قلب", "نوبة قلبية", "ذبحة صدرية",
                        "تصلب الشرايين", "فشل القلب", "اضطراب نظم القلب",
                        "صمام القلب", "ارتفاع ضغط الدم", "تخطيط القلب",
                        "إيكو القلب", "جلطة قلبية", "كوليسترول", "طبيب قلب",
                    ],
                },
                {
                    "id": "neurology",
                    "name_en": "Neurology",
                    "name_ar": "الأعصاب",
                    "keywords_en": [
                        "neurology", "neurological", "brain", "cerebral",
                        "stroke", "seizure", "epilepsy", "parkinson",
                        "dementia", "alzheimer", "multiple sclerosis",
                        "migraine", "neuropathy", "neuron", "synapse",
                        "meningitis", "encephalitis", "eeg", "csf",
                    ],
                    "keywords_ar": [
                        "الأعصاب", "الجهاز العصبي", "دماغ", "سكتة دماغية",
                        "صرع", "نوبة صرعية", "باركنسون", "خرف", "زهايمر",
                        "تصلب متعدد", "صداع نصفي", "اعتلال الأعصاب",
                        "التهاب السحايا", "طبيب أعصاب", "شلل", "تنميل",
                    ],
                },
                {
                    "id": "internal_medicine",
                    "name_en": "Internal Medicine",
                    "name_ar": "الطب الباطني",
                    "keywords_en": [
                        "internal medicine", "internist", "diabetes", "thyroid",
                        "anemia", "infection", "sepsis", "pneumonia", "copd",
                        "hepatitis", "cirrhosis", "kidney disease", "electrolyte",
                        "autoimmune", "lupus", "cbc", "metabolic",
                    ],
                    "keywords_ar": [
                        "الطب الباطني", "طبيب باطني", "سكري", "الغدة الدرقية",
                        "فقر الدم", "عدوى", "تسمم الدم", "التهاب رئوي",
                        "التهاب الكبد", "تليف الكبد", "فشل كلوي", "الذئبة",
                    ],
                },
                {
                    "id": "general_surgery",
                    "name_en": "General Surgery",
                    "name_ar": "الجراحة العامة",
                    "keywords_en": [
                        "surgery", "surgical", "surgeon", "laparoscopy",
                        "appendectomy", "cholecystectomy", "hernia",
                        "bowel resection", "anastomosis", "wound", "drain",
                        "biopsy", "incision", "hemorrhage", "trauma surgery",
                    ],
                    "keywords_ar": [
                        "الجراحة العامة", "جراح", "منظار البطن",
                        "استئصال الزائدة", "استئصال المرارة", "فتق",
                        "عملية جراحية", "جرح", "خزعة", "نزيف", "تخدير",
                    ],
                },
                {
                    "id": "pharmacology",
                    "name_en": "Pharmacology",
                    "name_ar": "علم الأدوية",
                    "keywords_en": [
                        "pharmacology", "drug", "medication", "antibiotic",
                        "dosage", "side effect", "contraindication",
                        "pharmacokinetic", "bioavailability", "prescription",
                        "statin", "ace inhibitor", "warfarin", "metformin",
                    ],
                    "keywords_ar": [
                        "علم الأدوية", "دواء", "أدوية", "مضاد حيوي",
                        "جرعة", "وصفة طبية", "آثار جانبية", "كريم",
                        "قرص", "كبسولة", "حقنة", "شراب",
                    ],
                },
                {
                    "id": "radiology",
                    "name_en": "Radiology",
                    "name_ar": "الأشعة",
                    "keywords_en": [
                        "radiology", "x-ray", "ct scan", "mri", "ultrasound",
                        "mammography", "fluoroscopy", "angiography",
                        "contrast", "radiation dose", "pacs", "dicom",
                    ],
                    "keywords_ar": [
                        "الأشعة", "أشعة سينية", "تصوير مقطعي", "رنين مغناطيسي",
                        "موجات فوق صوتية", "تصوير الثدي", "نتيجة الأشعة",
                    ],
                },
                {
                    "id": "pathology",
                    "name_en": "Pathology",
                    "name_ar": "علم الأمراض",
                    "keywords_en": [
                        "pathology", "biopsy", "histology", "histopathology",
                        "malignant", "benign", "carcinoma", "sarcoma",
                        "tumor grading", "metastasis", "necrosis", "fibrosis",
                    ],
                    "keywords_ar": [
                        "علم الأمراض", "خزعة", "علم الأنسجة", "خبيث",
                        "حميد", "سرطانة", "ورم", "نخر", "تليف", "مجهري",
                    ],
                },
            ],
        }

    # ── Utility / introspection ────────────────────────────────────────

    def get_category_names(self) -> Dict[str, str]:
        """Return a mapping of category IDs to their English names.

        Returns:
            ``{category_id: name_en}`` dictionary.
        """
        return {cid: names[0] for cid, names in self._category_names.items()}

    def get_keyword_count(self) -> int:
        """Return the total number of indexed keywords across all categories."""
        return sum(len(kw) for kw in self._category_keywords.values())

    def get_category_count(self) -> int:
        """Return the number of categories in the taxonomy."""
        return len(self._category_names)
