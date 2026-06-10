#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medical_context_protector.py
=============================
حماية السياق الطبي أثناء الدمج الدلالي.

يمنع دمج المصطلحات الطبية المتناقضة سريرياً حتى مع تشابه
متجهات عالٍ (>0.85). يحمي أربع فئات رئيسية:
  - laterality     : الجانب التشريحي
  - severity       : درجة الخطورة
  - fracture_type  : نوع الكسر
  - temporal       : الوصف الزمني

Medical context protector that prevents merging clinically contradictory
medical terms even with high vector similarity (>0.85).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "MedicalContextProtector",
    "MergeSafetyResult",
    "PROTECTED_ATTRIBUTES",
]

logger = logging.getLogger(__name__)

# ── فئات السمات المحمية / Protected attribute categories ────────────────
PROTECTED_ATTRIBUTES: dict[str, dict[str, Any]] = {
    "laterality": {
        "values": frozenset({
            # العربية
            "أيمن", "أيسر", "يمنى", "يسرى",
            "ثنائي", "أمامي", "خلفي", "جانبي",
            "إنسي", "وحشي",
            # الإنجليزية
            "right", "left", "bilateral", "anterior", "posterior",
            "lateral", "medial",
        }),
        "severity": "critical",
        "description": "الجانب التشريحي — خطأ في الجانب قد يُسبّب خطأً جراحياً",
    },
    "severity": {
        "values": frozenset({
            # العربية
            "حاد", "مزمن", "خفيف", "متوسط", "شديد",
            # الإنجليزية
            "acute", "chronic", "mild", "moderate", "severe",
        }),
        "severity": "high",
        "description": "درجة الخطورة — تؤثّر على خطة العلاج",
    },
    "fracture_type": {
        "values": frozenset({
            # العربية
            "مفتوح", "مغلق", "مضاعف", "شعري",
            # الإنجليزية
            "open", "closed", "comminuted", "hairline",
        }),
        "severity": "critical",
        "description": "نوع الكسر — يحدد العلاج الجراحي أو التحفظي",
    },
    "temporal": {
        "values": frozenset({
            # العربية
            "حديث", "قديم", "متكرر", "مستعصٍ",
            # الإنجليزية
            "recent", "old", "recurrent", "refractory",
        }),
        "severity": "medium",
        "description": "الوصف الزمني — يُحدد مرحلة المرض",
    },
}

# ── علامات الحماية / Protection markers ──────────────────────────────────
_MARKER_OPEN = "\x00PROT_OPEN\x00"
_MARKER_CLOSE = "\x00PROT_CLOSE\x00"


@dataclass(slots=True)
class MergeSafetyResult:
    """نتيجة فحص سلامة الدمج / Result of a merge-safety check."""

    safe: bool
    reason: str | None = None
    conflict_category: str | None = None
    conflict_severity: str | None = None
    chunk1_attributes: dict[str, list[str]] = field(default_factory=dict)
    chunk2_attributes: dict[str, list[str]] = field(default_factory=dict)


class MedicalContextProtector:
    """
    طبقة حماية السياق الطبي لعملية الدمج الدلالي.

    Medical context protection layer for semantic deduplication.
    Prevents merging of text chunks that differ in clinically significant
    attribute values, even when their embedding vectors are very similar.

    Example
    -------
    >>> protector = MedicalContextProtector()
    >>> safe, reason = protector.check_merge_safety(
    ...     "كسر مفتوح في اليد اليمنى",
    ...     "كسر مغلق في اليد اليمنى",
    ... )
    >>> safe
    False
    >>> reason  # contains "fracture_type" conflict
    """

    def __init__(
        self,
        protected_attributes: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        Args:
            protected_attributes: قاموس مخصّص للسمات المحمية.
                يستخدم القاموس الافتراضي إن لم يُمرَّر.
                Custom protected-attributes dict. Falls back to the built-in
                ``PROTECTED_ATTRIBUTES`` if *None*.
        """
        self._attrs = protected_attributes or PROTECTED_ATTRIBUTES
        # بناء فهرس بحث سريع: مصطلح ← فئة
        self._term_to_category: dict[str, str] = {}
        self._all_terms: set[str] = set()
        for category, config in self._attrs.items():
            values: frozenset[str] = config["values"]
            for term in values:
                self._term_to_category[term] = category
                self._all_terms.add(term)

    # ── واجهة عامة / Public interface ────────────────────────────────────

    def check_merge_safety(
        self,
        chunk1: str,
        chunk2: str,
    ) -> tuple[bool, str | None]:
        """تحقق إن كان يمكن دمج القطعتين بأمان سريري.

        Args:
            chunk1: النص الأول / First text chunk.
            chunk2: النص الثاني / Second text chunk.

        Returns:
            (safe, reason) — ``safe`` is *False* when a clinically
            significant conflict is detected; ``reason`` explains why.
        """
        result = self.check_merge_safety_detailed(chunk1, chunk2)
        return result.safe, result.reason

    def check_merge_safety_detailed(
        self,
        chunk1: str,
        chunk2: str,
    ) -> MergeSafetyResult:
        """نسخة تفصيلية من فحص الدمج تتضمّن السمات المكتشفة.

        Detailed version of the merge-safety check that includes the
        extracted attribute maps for both chunks.
        """
        c1_lower = chunk1.lower()
        c2_lower = chunk2.lower()

        c1_attrs = self._extract_attributes(c1_lower)
        c2_attrs = self._extract_attributes(c2_lower)

        for category, config in self._attrs.items():
            v1 = set(c1_attrs.get(category, []))
            v2 = set(c2_attrs.get(category, []))
            if v1 and v2 and v1 != v2:
                # كشف تعارض: نفس الفئة لكن قيم مختلفة
                reason = (
                    f"تعارض في {category}: '{v1}' مقابل '{v2}' "
                    f"(الخطورة: {config['severity']})"
                )
                logger.warning(
                    "Medical merge blocked — %s conflict between chunks: %s",
                    category,
                    reason,
                )
                return MergeSafetyResult(
                    safe=False,
                    reason=reason,
                    conflict_category=category,
                    conflict_severity=config["severity"],
                    chunk1_attributes=c1_attrs,
                    chunk2_attributes=c2_attrs,
                )

        return MergeSafetyResult(
            safe=True,
            reason=None,
            chunk1_attributes=c1_attrs,
            chunk2_attributes=c2_attrs,
        )

    def protect_term(self, text: str) -> str:
        """لفّ المصطلحات المحمية بعلامات حماية.

        Wrap protected terms in the text with marker delimiters so that
        downstream processors (e.g., semantic dedup) can treat them as
        atomic tokens.

        Args:
            text: النص الأصلي / Original text.

        Returns:
            النص مع علامات الحماية / Text with protected terms wrapped.
        """
        if not text:
            return text

        # ترتيب المصطلحات حسب الطول (الأطول أولاً) لتجنّب التداخل
        sorted_terms = sorted(self._all_terms, key=len, reverse=True)

        protected_text = text
        for term in sorted_terms:
            # تجنب إعادة لفّ مصطلح محمي مسبقاً
            pattern = re.compile(
                rf"(?<!{re.escape(_MARKER_OPEN)})"  # not preceded by marker
                rf"\b{re.escape(term)}\b"
                rf"(?!{re.escape(_MARKER_CLOSE)})",  # not followed by marker
                re.IGNORECASE,
            )
            protected_text = pattern.sub(
                rf"{_MARKER_OPEN}\g<0>{_MARKER_CLOSE}",
                protected_text,
            )

        return protected_text

    def extract_protected_attributes(self, text: str) -> dict[str, list[str]]:
        """استخراج جميع السمات المحمية من النص.

        Extract all protected attribute values found in *text*,
        grouped by category.

        Args:
            text: النص المراد تحليله / Text to analyse.

        Returns:
            قاموس: فئة ← قائمة القيم الموجودة.
            ``{category: [value, ...]}``
        """
        return self._extract_attributes(text.lower())

    # ── داخلي / Internal ────────────────────────────────────────────────

    def _extract_attributes(self, text_lower: str) -> dict[str, list[str]]:
        """استخراج السمات من نص مُحوّل لحروف صغيرة."""
        found: dict[str, list[str]] = {}
        for term, category in self._term_to_category.items():
            if term in text_lower:
                found.setdefault(category, []).append(term)
        return found