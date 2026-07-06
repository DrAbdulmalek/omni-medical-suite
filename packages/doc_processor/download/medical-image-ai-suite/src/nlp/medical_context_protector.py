# -*- coding: utf-8 -*-
"""Medical context protection for the OmniMedical Suite.

When OCR results from different engines or document pages are merged,
there is a risk that clinically contradictory attributes (laterality,
severity, temporality, fracture type) are silently combined — for
example, merging "fracture of the right femur" with "left tibia" could
produce an ambiguous composite finding.

This module detects such conflicts in both Arabic and English medical
text and provides tools to flag, report, or sanitize the affected
segments before downstream consumption.

Typical usage::

    from nlp.medical_context_protector import MedicalContextProtector

    protector = MedicalContextProtector()
    safe, report = protector.protect_text(
        "Fracture of the right femur.  Left tibia is intact."
    )
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConflictDescriptor:
    """Describes a single detected conflict between two text spans.

    Attributes:
        category:    One of ``"laterality"``, ``"severity"``,
                     ``"temporal"``, ``"fracture_type"``.
        text1:       The first (earlier) text fragment that contributed.
        text2:       The second (later) text fragment that contributed.
        matched_ar:  Arabic term pair that triggered the conflict, or
                     ``None``.
        matched_en:  English term pair that triggered the conflict, or
                     ``None``.
        description: Human-readable explanation of the conflict.
    """

    category: str
    text1: str
    text2: str
    matched_ar: Optional[Tuple[str, str]] = None
    matched_en: Optional[Tuple[str, str]] = None
    description: str = ""


@dataclass
class SafetyAssessment:
    """Result of a merge-safety check between two text segments.

    Attributes:
        is_safe:          ``True`` when no conflicts are detected.
        conflicts:        List of :class:`ConflictDescriptor` objects.
        overall_risk:     Aggregate risk score in ``[0, 1]``.
        recommendation:   Short human-readable recommendation.
    """

    is_safe: bool = True
    conflicts: List[ConflictDescriptor] = field(default_factory=list)
    overall_risk: float = 0.0
    recommendation: str = "Safe to merge."


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MedicalContextProtector:
    """Detect and mitigate clinically contradictory attribute merges in
    bilingual (Arabic / English) medical text.

    On construction the protector compiles a set of conflict rules that
    map each semantic category to mutually exclusive term pairs.  These
    rules are then applied by the public API methods.

    Parameters:
        custom_rules: Optional dictionary of additional conflict rules.
            Keys are category names, values are lists of ``(term_a, term_b)``
            pairs.  Both Arabic and English terms are accepted.
    """

    def __init__(
        self,
        custom_rules: Optional[Dict[str, List[Tuple[str, str]]]] = None,
    ) -> None:
        # ---- laterality: right / left / bilateral ----
        self._laterality_pairs: Set[Tuple[str, str]] = {
            # Arabic pairs
            ("يمين", "أيسر"),
            ("يمين", "يسار"),
            ("أيمن", "أيسر"),
            ("أيمن", "يسار"),
            # English pairs
            ("right", "left"),
            ("right", "bilateral"),
            ("left", "bilateral"),
        }

        # ---- severity: acute / chronic ----
        self._severity_pairs: Set[Tuple[str, str]] = {
            # Arabic
            ("حاد", "مزمن"),
            ("حاد", "تحت الحاد"),
            # English
            ("acute", "chronic"),
            ("acute", "subacute"),
            ("subacute", "chronic"),
        }

        # ---- temporal: new / old ----
        self._temporal_pairs: Set[Tuple[str, str]] = {
            # Arabic
            ("حديث", "قديم"),
            ("طارئ", "قديم"),
            # English
            ("new", "old"),
            ("recent", "old"),
            ("acute", "chronic"),  # also carries temporal sense
        }

        # ---- fracture type: open / closed ----
        self._fracture_type_pairs: Set[Tuple[str, str]] = {
            # Arabic
            ("مفتوح", "مغلق"),
            ("مركب", "بسيط"),
            # English
            ("open", "closed"),
            ("compound", "simple"),
            ("comminuted", "simple"),
        }

        # Merge in any caller-supplied rules.
        if custom_rules:
            for category, pairs in custom_rules.items():
                pair_set = {tuple(p) for p in pairs}
                attr = f"_{category}_pairs"
                existing: Set[Tuple[str, str]] = getattr(self, attr, set())
                existing.update(pair_set)
                setattr(self, attr, existing)

        # Precompile regex patterns for each pair (word-boundary search).
        self._lat_patterns = self._compile_patterns(self._laterality_pairs)
        self._sev_patterns = self._compile_patterns(self._severity_pairs)
        self._tmp_patterns = self._compile_patterns(self._temporal_pairs)
        self._fx_patterns = self._compile_patterns(self._fracture_type_pairs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_merge_safety(
        self,
        text1: str,
        text2: str,
    ) -> SafetyAssessment:
        """Determine whether *text1* and *text2* can be safely merged
        without introducing clinically contradictory information.

        Each category of conflict (laterality, severity, temporal,
        fracture type) is checked independently.  The overall risk
        score is the maximum per-category risk.

        Args:
            text1: First text segment.
            text2: Second text segment.

        Returns:
            A :class:`SafetyAssessment` with detailed conflict info.
        """
        conflicts: List[ConflictDescriptor] = []

        conflicts.extend(self._check_laterality(text1, text2))
        conflicts.extend(self._check_severity(text1, text2))
        conflicts.extend(self._check_temporal(text1, text2))
        conflicts.extend(self._check_fracture_type(text1, text2))

        is_safe = len(conflicts) == 0

        # Overall risk: more categories affected → higher risk.
        affected_categories = len({c.category for c in conflicts})
        overall_risk = min(affected_categories * 0.3, 1.0)

        recommendation = "Safe to merge."
        if conflicts:
            categories = sorted({c.category for c in conflicts})
            recommendation = (
                f"Conflicts detected in: {', '.join(categories)}. "
                "Review recommended before merging."
            )

        return SafetyAssessment(
            is_safe=is_safe,
            conflicts=conflicts,
            overall_risk=overall_risk,
            recommendation=recommendation,
        )

    def protect_text(
        self,
        text: str,
        mode: str = "flag",
    ) -> Tuple[str, List[ConflictDescriptor]]:
        """Sanitise text by detecting and handling conflicting segments.

        The input text is split into sentences, and every unique pair of
        sentences is checked for conflicts.  Depending on *mode*:

        * ``"flag"``  — Conflicting sentences are wrapped in Unicode
          bracket markers (``«`` … ``»``) so that downstream consumers
          can identify them visually.
        * ``"remove"`` — The sentence that appears later in the text
          and conflicts with an earlier one is removed entirely.

        Args:
            text: The full text to sanitise.
            mode: ``"flag"`` or ``"remove"``.

        Returns:
            A 2-tuple ``(sanitised_text, conflicts)``.
        """
        # Split into sentences.
        sentences = re.split(r'(?<=[.!?。\n])\s*', text)
        flagged_indices: Set[int] = set()
        removed_indices: Set[int] = set()
        all_conflicts: List[ConflictDescriptor] = []

        for i in range(len(sentences)):
            for j in range(i + 1, len(sentences)):
                assessment = self.check_merge_safety(
                    sentences[i], sentences[j]
                )
                if not assessment.is_safe:
                    all_conflicts.extend(assessment.conflicts)
                    flagged_indices.add(i)
                    flagged_indices.add(j)
                    if mode == "remove":
                        removed_indices.add(j)

        # Build output.
        if mode == "remove":
            result_sentences = [
                s for idx, s in enumerate(sentences)
                if idx not in removed_indices
            ]
        else:
            result_sentences = [
                f"\u00AB{s}\u00BB" if idx in flagged_indices else s
                for idx, s in enumerate(sentences)
            ]

        sanitised = " ".join(result_sentences)
        return sanitised, all_conflicts

    def get_conflict_report(
        self,
        text1: str,
        text2: str,
    ) -> str:
        """Return a detailed, human-readable conflict report.

        Args:
            text1: First text segment.
            text2: Second text segment.

        Returns:
            Multi-line string suitable for logging or display.
        """
        assessment = self.check_merge_safety(text1, text2)

        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("  MEDICAL CONTEXT CONFLICT REPORT")
        lines.append("=" * 60)
        lines.append(f"Overall safe to merge: {assessment.is_safe}")
        lines.append(f"Overall risk score:    {assessment.overall_risk:.2f}")
        lines.append(f"Recommendation:        {assessment.recommendation}")
        lines.append("")

        if not assessment.conflicts:
            lines.append("No conflicts detected.")
        else:
            lines.append(f"Conflicts found ({len(assessment.conflicts)}):")
            lines.append("-" * 40)
            for idx, conflict in enumerate(assessment.conflicts, 1):
                lines.append(f"  [{idx}] Category: {conflict.category}")
                lines.append(f"      Text 1:  {conflict.text1!r}")
                lines.append(f"      Text 2:  {conflict.text2!r}")
                if conflict.matched_ar:
                    lines.append(
                        f"      Arabic:  {conflict.matched_ar[0]} ↔ "
                        f"{conflict.matched_ar[1]}"
                    )
                if conflict.matched_en:
                    lines.append(
                        f"      English: {conflict.matched_en[0]} ↔ "
                        f"{conflict.matched_en[1]}"
                    )
                lines.append(f"      Info:    {conflict.description}")
                lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Category-specific checkers
    # ------------------------------------------------------------------

    def _check_laterality(
        self, text1: str, text2: str
    ) -> List[ConflictDescriptor]:
        """Detect right/left/bilateral laterality conflicts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            List of conflict descriptors.
        """
        return self._check_category(
            "laterality", text1, text2, self._lat_patterns,
            description="Laterality conflict: opposing sides detected.",
        )

    def _check_severity(
        self, text1: str, text2: str
    ) -> List[ConflictDescriptor]:
        """Detect acute/chronic/subacute severity conflicts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            List of conflict descriptors.
        """
        return self._check_category(
            "severity", text1, text2, self._sev_patterns,
            description="Severity conflict: contradictory acuity levels.",
        )

    def _check_temporal(
        self, text1: str, text2: str
    ) -> List[ConflictDescriptor]:
        """Detect new/old/recent temporal conflicts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            List of conflict descriptors.
        """
        return self._check_category(
            "temporal", text1, text2, self._tmp_patterns,
            description="Temporal conflict: contradictory timing markers.",
        )

    def _check_fracture_type(
        self, text1: str, text2: str
    ) -> List[ConflictDescriptor]:
        """Detect open/closed/compound fracture-type conflicts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            List of conflict descriptors.
        """
        return self._check_category(
            "fracture_type", text1, text2, self._fx_patterns,
            description="Fracture-type conflict: contradictory classifications.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_category(
        self,
        category: str,
        text1: str,
        text2: str,
        patterns: List[Tuple[re.Pattern[str], re.Pattern[str], str, str]],
        description: str,
    ) -> List[ConflictDescriptor]:
        """Generic category checker.

        Iterates over compiled pattern pairs.  For each pair, if
        *pattern_a* matches *text1* and *pattern_b* matches *text2*
        (or vice versa), a conflict is recorded.

        Args:
            category:    Category name for the descriptor.
            text1:       First text.
            text2:       Second text.
            patterns:    List of ``(pat_a, pat_b, term_a, term_b)``
                         tuples from :meth:`_compile_patterns`.
            description: Human-readable description template.

        Returns:
            List of :class:`ConflictDescriptor` instances.
        """
        conflicts: List[ConflictDescriptor] = []

        for pat_a, pat_b, term_a, term_b in patterns:
            a_in_1 = bool(pat_a.search(text1))
            b_in_2 = bool(pat_b.search(text2))
            a_in_2 = bool(pat_a.search(text2))
            b_in_1 = bool(pat_b.search(text1))

            if (a_in_1 and b_in_2) or (a_in_2 and b_in_1):
                is_arabic = any(
                    '\u0600' <= ch <= '\u06FF'
                    for ch in term_a + term_b
                )
                conflicts.append(ConflictDescriptor(
                    category=category,
                    text1=text1,
                    text2=text2,
                    matched_ar=(term_a, term_b) if is_arabic else None,
                    matched_en=(term_a, term_b) if not is_arabic else None,
                    description=f"{description} ({term_a} ↔ {term_b})",
                ))

        return conflicts

    @staticmethod
    def _compile_patterns(
        pairs: Set[Tuple[str, str]],
    ) -> List[Tuple[re.Pattern[str], re.Pattern[str], str, str]]:
        """Compile term pairs into case-insensitive regex patterns with
        word-boundary anchors.

        Arabic terms do not use ``\\b`` because it does not work reliably
        with RTL scripts; instead a lookaround-free pattern is used.

        Args:
            pairs: Set of ``(term_a, term_b)`` tuples.

        Returns:
            List of ``(compiled_a, compiled_b, term_a, term_b)`` tuples.
        """
        compiled: List[Tuple[re.Pattern[str], re.Pattern[str], str, str]] = []

        for term_a, term_b in pairs:
            flags = re.IGNORECASE | re.UNICODE

            def _make_pat(term: str) -> re.Pattern[str]:
                if any('\u0600' <= ch <= '\u06FF' for ch in term):
                    return re.compile(re.escape(term), flags)
                return re.compile(r'\b' + re.escape(term) + r'\b', flags)

            compiled.append((
                _make_pat(term_a),
                _make_pat(term_b),
                term_a,
                term_b,
            ))

        return compiled
