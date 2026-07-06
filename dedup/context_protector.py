"""
AI Fuel Engine - Medical Context Protector

Prevents critical medical information from being discarded during
deduplication.  Drug dosages, vital signs, lab values, diagnostic criteria,
procedural steps, and specific patient measurements are protected even
if their surrounding text appears semantically redundant.

This module is especially important for healthcare corpora where precision
in numerical values can be clinically significant.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from unicodedata import normalize

logger = logging.getLogger(__name__)


class MedicalContextProtector:
    """Protects important medical context from being removed during dedup.

    The protector uses a library of curated regex patterns to identify
    segments of text that carry clinically significant information.  When
    a chunk marked for deduplication contains protected segments, the
    :class:`DeduplicationEngine` should preserve it.

    Attributes:
        protected_patterns: Compiled list of pattern dictionaries, each
            containing ``name``, ``regex`` (compiled), ``description``,
            and ``priority`` (higher = more important).
    """

    # Default Arabic-friendly regex flags
    _FLAGS = re.UNICODE | re.IGNORECASE

    def __init__(self) -> None:
        """Build the library of protected medical patterns."""
        self.protected_patterns: List[Dict] = self._build_protected_patterns()
        logger.info(
            "MedicalContextProtector initialised with %d patterns.",
            len(self.protected_patterns),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_protected_context(self, text: str) -> bool:
        """Check whether *text* contains protected medical information.

        Args:
            text: The chunk text to scan.

        Returns:
            ``True`` if at least one protected pattern matches.
        """
        if not text or not text.strip():
            return False

        # Normalise unicode (NFC) for reliable matching of Arabic diacritics
        normalised = normalize("NFC", text)

        for pattern in self.protected_patterns:
            if pattern["regex"].search(normalised):
                return True

        return False

    def get_protected_segments(self, text: str) -> List[Dict]:
        """Extract protected segments from *text*.

        Returns all non-overlapping matches for each protected pattern,
        ordered by their position in the text.

        Args:
            text: The chunk text to scan.

        Returns:
            A list of dictionaries, each with:
            - ``pattern_name`` – human-readable pattern label.
            - ``value`` – the matched substring.
            - ``start`` – character offset of the match start.
            - ``end`` – character offset of the match end.
            - ``priority`` – the pattern's importance priority.
        """
        segments: List[Dict] = []

        if not text or not text.strip():
            return segments

        normalised = normalize("NFC", text)

        for pattern in self.protected_patterns:
            for match in pattern["regex"].finditer(normalised):
                segments.append(
                    {
                        "pattern_name": pattern["name"],
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                        "priority": pattern["priority"],
                    }
                )

        # Sort by position in text
        segments.sort(key=lambda s: s["start"])
        return segments

    def protection_score(self, text: str) -> float:
        """Return a numeric protection score for *text*.

        Higher scores indicate more clinically important content.  The
        score is the sum of matched pattern priorities, normalised to
        [0, 1].

        Args:
            text: The chunk text to evaluate.

        Returns:
            A float in [0, 1].
        """
        segments = self.get_protected_segments(text)
        if not segments:
            return 0.0

        max_possible = sum(p["priority"] for p in self.protected_patterns)
        if max_possible == 0:
            return 0.0

        total_priority = sum(s["priority"] for s in segments)
        return min(total_priority / max_possible, 1.0)

    def get_stats(self) -> Dict:
        """Return information about the loaded patterns.

        Returns:
            Dictionary with ``pattern_count`` and a summary of pattern
            names.
        """
        return {
            "pattern_count": len(self.protected_patterns),
            "patterns": [
                {"name": p["name"], "description": p["description"]}
                for p in self.protected_patterns
            ],
        }

    # ------------------------------------------------------------------
    # Pattern builder
    # ------------------------------------------------------------------

    def _build_protected_patterns(self) -> List[Dict]:
        """Build regex patterns for protected medical content.

        Patterns cover:
        - Drug dosages (mg, ml, units, etc.) with numeric values
        - Vital signs (BP, HR, RR, SpO2, Temp)
        - Lab values (with reference ranges)
        - Diagnostic criteria (DSM, ICD, scores)
        - Procedural/surgical steps
        - Specific measurements (weight, height, BMI, BSA)
        - Arabic dosage expressions

        Returns:
            A list of pattern dictionaries.
        """
        raw_patterns: List[Dict[str, any]] = [
            # ── Drug dosages ─────────────────────────────────────────────
            {
                "name": "drug_dosage_metric",
                "regex": re.compile(
                    r"\b\d+(?:\.\d+)?\s*(?:mg|ml|units?|IU|mcg|g|µg|mEq|mmol|L)\b",
                    self._FLAGS,
                ),
                "description": "Drug dosage with metric unit (e.g. 500mg, 10ml).",
                "priority": 5,
            },
            {
                "name": "drug_dosage_arabic",
                "regex": re.compile(
                    r"[\u0600-\u06FF]+\s+\d+(?:\.\d+)?\s*(?:ملغ|مل|وحدة|وحدات)",
                    self._FLAGS,
                ),
                "description": "Arabic drug dosage expression.",
                "priority": 5,
            },
            {
                "name": "dosage_frequency",
                "regex": re.compile(
                    r"\b(?:once|twice|tid|qid|q[0-9]h|qd|qod|prn|as needed|stat|BID|TID|QID)\b",
                    re.IGNORECASE,
                ),
                "description": "Dosage frequency (Latin abbreviations).",
                "priority": 4,
            },
            {
                "name": "dosage_frequency_arabic",
                "regex": re.compile(
                    r"(?:يومياً|مرتين|ثلاث|أربع|كل)\s+(?:يوم|ساعة)",
                    self._FLAGS,
                ),
                "description": "Arabic dosage frequency.",
                "priority": 4,
            },
            # ── Vital signs ──────────────────────────────────────────────
            {
                "name": "blood_pressure",
                "regex": re.compile(
                    r"\b\d{2,3}/\d{2,3}\s*(?:mmHg|mm\s*Hg)?\b",
                    re.IGNORECASE,
                ),
                "description": "Blood pressure reading (e.g. 120/80 mmHg).",
                "priority": 6,
            },
            {
                "name": "heart_rate",
                "regex": re.compile(
                    r"\b(?:HR|heart\s*rate|pulse|نفس|نبض)\s*[:\s=]?\s*\d{1,3}\s*(?:bpm|beats?/min)?\b",
                    self._FLAGS,
                ),
                "description": "Heart rate / pulse measurement.",
                "priority": 5,
            },
            {
                "name": "oxygen_saturation",
                "regex": re.compile(
                    r"\b(?:SpO2|O2\s*sat|إشباع\s*الأكسجين)\s*[:\s=]?\s*\d{1,3}\s*(?:%|نسبة)?\b",
                    self._FLAGS,
                ),
                "description": "Oxygen saturation reading.",
                "priority": 6,
            },
            {
                "name": "temperature",
                "regex": re.compile(
                    r"\b(?:Temp|درجة\s*الحرارة|حرارة)\s*[:\s=]?\s*\d{2,3}(?:\.\d+)?\s*°?[CF]?\b",
                    self._FLAGS,
                ),
                "description": "Body temperature reading.",
                "priority": 5,
            },
            {
                "name": "respiratory_rate",
                "regex": re.compile(
                    r"\b(?:RR|respiratory\s*rate|معدل\s*التنفس)\s*[:\s=]?\s*\d{1,3}\s*(?:breaths?/min)?\b",
                    self._FLAGS,
                ),
                "description": "Respiratory rate.",
                "priority": 5,
            },
            # ── Lab values ────────────────────────────────────────────────
            {
                "name": "lab_value_range",
                "regex": re.compile(
                    r"\b[A-Za-z\u0600-\u06FF]{1,5}\s*[:\s]\s*\d+(?:\.\d+)?\s*(?:-\s*\d+(?:\.\d+)?)?\s*(?:mg/dL|mmol/L|g/L|U/L|ng/mL|pg/mL|IU/L|µg/L|%)\b",
                    self._FLAGS,
                ),
                "description": "Lab value with unit and optional reference range.",
                "priority": 5,
            },
            {
                "name": "gfr_value",
                "regex": re.compile(
                    r"\b(?:GFR|eGFR|معدل\s*الترشيح)\s*[:\s=]?\s*\d{1,3}\s*(?:ml/min/1.73m²)?\b",
                    self._FLAGS,
                ),
                "description": "GFR / eGFR renal function value.",
                "priority": 6,
            },
            # ── Diagnostic criteria ──────────────────────────────────────
            {
                "name": "diagnostic_score",
                "regex": re.compile(
                    r"\b(?:APACHE|SOFA|GCS|NEWS|CHARLSON|CURB-65|CHA2DS2|PADUA|Wells|D-dimer)\s*[:\s]\s*\d+(?:\.\d+)?\b",
                    re.IGNORECASE,
                ),
                "description": "Clinical diagnostic or risk score.",
                "priority": 6,
            },
            {
                "name": "icd_code",
                "regex": re.compile(
                    r"\b[A-Z]\d{2}(?:\.\d{1,4})?(?:\s*-\s*[A-Z]\d{2}(?:\.\d{1,4})?)?\b",
                    re.IGNORECASE,
                ),
                "description": "ICD diagnostic code.",
                "priority": 4,
            },
            # ── Patient measurements ──────────────────────────────────────
            {
                "name": "body_measurement",
                "regex": re.compile(
                    r"\b(?:weight|الوزن|height|الطول|BMI|BSA)\s*[:\s=]?\s*\d+(?:\.\d+)?\s*(?:kg|cm|lb|m|kg/m²)?\b",
                    self._FLAGS,
                ),
                "description": "Body weight, height, BMI, or BSA.",
                "priority": 5,
            },
            # ── Procedural steps ─────────────────────────────────────────
            {
                "name": "procedural_step",
                "regex": re.compile(
                    r"(?:Step\s+\d|الخطوة\s+\d|(?:1|2|3|4|5|6|7|8|9)\.\s+[A-Z\u0600-\u06FF])",
                    self._FLAGS,
                ),
                "description": "Numbered procedural or surgical step.",
                "priority": 3,
            },
            {
                "name": "critical_instruction",
                "regex": re.compile(
                    r"\b(?:warning|caution|contraindicated|do\s+not|avoid|dangerous|تحذير|ممنوع|خطر)\b",
                    self._FLAGS,
                ),
                "description": "Critical safety instruction or contraindication.",
                "priority": 7,
            },
        ]

        # Validate that all patterns compiled successfully
        valid_patterns: List[Dict] = []
        for p in raw_patterns:
            if p["regex"] is not None:
                valid_patterns.append(p)
            else:
                logger.warning(
                    "Pattern '%s' failed to compile and was skipped.", p["name"]
                )

        return valid_patterns

    def __repr__(self) -> str:
        return f"MedicalContextProtector(patterns={len(self.protected_patterns)})"
