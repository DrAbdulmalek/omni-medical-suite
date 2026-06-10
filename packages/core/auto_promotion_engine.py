#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_promotion_engine.py
========================
محرك الترقية التلقائية للتصحيحات.

يراقب ذاكرة التصحيحات ويرقّي التصحيحات الموثوقة من قائمة
المراجعة إلى ذاكرة التخزين المؤقت النشطة وفق معايير جودة قابلة
للتهيئة.

Auto-promotion engine for corrections. Monitors ``correction_memory``
and promotes reliable corrections from the review queue to the active
cache based on configurable quality criteria:

  - min_frequency        ≥ 3   (seen in ≥ 3 different files)
  - min_confidence_gain  ≥ 0.05
  - max_age_days         ≤ 30
  - no_medical_conflict  (no protected-attribute clash)
  - require_cross_context ≥ 2 distinct contexts
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "AutoPromotionEngine",
    "PromotionCriteria",
    "PromotionResult",
    "PromotionStats",
]

logger = logging.getLogger(__name__)

# ── الجدول الافتراضي / Default table DDL ─────────────────────────────────
_CORRECTIONS_DDL = """
CREATE TABLE IF NOT EXISTS corrections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original        TEXT    NOT NULL,
    corrected       TEXT    NOT NULL,
    frequency       INTEGER NOT NULL DEFAULT 1,
    confidence_gain REAL    NOT NULL DEFAULT 0.0,
    confidence_after REAL  NOT NULL DEFAULT 0.0,
    context         TEXT    NOT NULL DEFAULT '',
    first_seen      TEXT    NOT NULL,
    last_seen       TEXT    NOT NULL,
    auto_promoted   INTEGER NOT NULL DEFAULT 0,
    promoted_at     TEXT,
    UNIQUE(original, corrected, context)
);

CREATE INDEX IF NOT EXISTS idx_corr_freq
    ON corrections(frequency DESC, confidence_gain DESC);

CREATE INDEX IF NOT EXISTS idx_corr_promoted
    ON corrections(auto_promoted);
"""


@dataclass(slots=True)
class PromotionCriteria:
    """معايير الترقية التلقائية / Auto-promotion eligibility criteria."""

    min_frequency: int = 3
    min_confidence_gain: float = 0.05
    min_avg_confidence_after: float = 0.80
    max_age_days: int = 30
    no_medical_conflict: bool = True
    require_cross_context: bool = True
    min_context_count: int = 2


@dataclass(slots=True)
class PromotionResult:
    """نتيجة تقييم ترقية واحدة / Result of a single promotion evaluation."""

    correction_id: int
    original: str
    corrected: str
    frequency: int
    confidence_gain: float
    promoted: bool = False
    reasons_passed: list[str] = field(default_factory=list)
    reasons_failed: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


@dataclass(slots=True)
class PromotionStats:
    """إحصائيات الترقية التلقائية / Auto-promotion statistics."""

    total_evaluated: int = 0
    total_promoted: int = 0
    total_rejected: int = 0
    promotion_rate: float = 0.0
    last_cycle_at: str = ""
    cycle_count: int = 0


class AutoPromotionEngine:
    """
    محرك الترقية التلقائية للتصحيحات.

    Monitors the ``corrections`` table and automatically promotes
    corrections that satisfy *all* criteria from the review queue
    to the active correction cache.
    """

    DEFAULT_CRITERIA = PromotionCriteria()

    def __init__(
        self,
        db_path: str | Path | None = None,
        criteria: PromotionCriteria | None = None,
    ) -> None:
        """
        Args:
            db_path: مسار قاعدة بيانات SQLite.
                يُنشئ ملفاً مؤقتاً إن لم يُحدَّد.
            criteria: معايير الترقية. يستخدم الافتراضية إن لم يُحدَّد.
        """
        if db_path is None:
            self._db_path = os.path.join(
                tempfile.gettempdir(), "omni_corrections.db"
            )
        else:
            self._db_path = str(db_path)

        self.criteria = criteria or self.DEFAULT_CRITERIA
        self._cycle_count: int = 0
        self._promotion_history: list[PromotionResult] = []
        self._ensure_schema()

    # ── واجهة عامة / Public API ──────────────────────────────────────────

    def evaluate(self, correction: dict[str, Any]) -> PromotionResult:
        """تقييم تصحيح واحد للترقية.

        Args:
            correction: قاموس يحتوي على حقول التصحيح
                (original, corrected, frequency, confidence_gain,
                confidence_after, first_seen, contexts, ...).

        Returns:
            ``PromotionResult`` مع تفاصيل التقييم.
        """
        freq = int(correction.get("frequency", 0))
        gain = float(correction.get("confidence_gain", 0.0))
        conf_after = float(correction.get("confidence_after", 0.0))
        first_seen = correction.get("first_seen", "")
        contexts = correction.get("contexts", "")
        context_list = (
            [c.strip() for c in str(contexts).split(",") if c.strip()]
            if contexts
            else []
        )
        if not context_list and "context" in correction:
            context_list = [correction["context"]]

        checks: dict[str, bool] = {}
        passed: list[str] = []
        failed: list[str] = []

        # 1. التكرار / Frequency
        freq_ok = freq >= self.criteria.min_frequency
        checks["frequency"] = freq_ok
        if freq_ok:
            passed.append(f"التكرار {freq} ≥ {self.criteria.min_frequency}")
        else:
            failed.append(
                f"التكرار {freq} < {self.criteria.min_frequency}"
            )

        # 2. تحسّن الثقة / Confidence gain
        gain_ok = gain >= self.criteria.min_confidence_gain
        checks["confidence_gain"] = gain_ok
        if gain_ok:
            passed.append(f"تحسّن الثقة {gain:.3f} ≥ {self.criteria.min_confidence_gain}")
        else:
            failed.append(
                f"تحسّن الثقة {gain:.3f} < {self.criteria.min_confidence_gain}"
            )

        # 3. متوسط الثقة بعد التصحيح / Avg confidence after
        conf_ok = conf_after >= self.criteria.min_avg_confidence_after
        checks["confidence_after"] = conf_ok
        if conf_ok:
            passed.append(
                f"الثقة بعد التصحيح {conf_after:.2f} ≥ "
                f"{self.criteria.min_avg_confidence_after}"
            )
        else:
            failed.append(
                f"الثقة بعد التصحيح {conf_after:.2f} < "
                f"{self.criteria.min_avg_confidence_after}"
            )

        # 4. العمر / Age
        days_since = self._days_since(first_seen)
        age_ok = days_since <= self.criteria.max_age_days
        checks["age"] = age_ok
        if age_ok:
            passed.append(f"العمر {days_since} يوم ≤ {self.criteria.max_age_days}")
        else:
            failed.append(f"العمر {days_since} يوم > {self.criteria.max_age_days}")

        # 5. تعارض طبي / Medical conflict
        if self.criteria.no_medical_conflict:
            medical_ok = not self._has_medical_conflict(
                correction.get("original", ""),
                correction.get("corrected", ""),
            )
        else:
            medical_ok = True
        checks["no_medical_conflict"] = medical_ok
        if medical_ok:
            passed.append("لا يوجد تعارض طبي")
        else:
            failed.append("يوجد تعارض في السمات الطبية المحمية")

        # 6. سياقات متعددة / Cross-context
        if self.criteria.require_cross_context:
            ctx_ok = len(set(context_list)) >= self.criteria.min_context_count
        else:
            ctx_ok = True
        checks["cross_context"] = ctx_ok
        if ctx_ok:
            passed.append(
                f"سياقات متعددة ({len(set(context_list))} ≥ "
                f"{self.criteria.min_context_count})"
            )
        else:
            failed.append(
                f"عدد السياقات {len(set(context_list))} < "
                f"{self.criteria.min_context_count}"
            )

        all_passed = all(checks.values())

        return PromotionResult(
            correction_id=int(correction.get("id", -1)),
            original=correction.get("original", ""),
            corrected=correction.get("corrected", ""),
            frequency=freq,
            confidence_gain=gain,
            promoted=all_passed,
            reasons_passed=passed,
            reasons_failed=failed,
            checks=checks,
        )

    def run_promotion_cycle(self) -> list[PromotionResult]:
        """تنفيذ دورة ترقية كاملة على جميع التصحيحات المعلّقة.

        Returns:
            قائمة نتائج التقييم لكل تصحيح تم فحصه.
        """
        results: list[PromotionResult] = []

        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                cur.execute(
                    "SELECT * FROM corrections "
                    "WHERE auto_promoted = 0 "
                    "ORDER BY frequency DESC, confidence_gain DESC"
                )

                for row in cur.fetchall():
                    row_dict = dict(row)
                    # تجميع السياقات لكل تصحيح
                    contexts = self._get_contexts(cur, row_dict["id"])
                    row_dict["contexts"] = ", ".join(contexts)

                    result = self.evaluate(row_dict)

                    if result.promoted:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        cur.execute(
                            "UPDATE corrections SET auto_promoted = 1, "
                            "promoted_at = ? WHERE id = ?",
                            (now_iso, result.correction_id),
                        )
                        conn.commit()
                        logger.info(
                            "Correction promoted: '%s' → '%s' "
                            "(freq=%d, gain=%.3f)",
                            result.original,
                            result.corrected,
                            result.frequency,
                            result.confidence_gain,
                        )

                    results.append(result)
        except sqlite3.Error as exc:
            logger.error("Database error during promotion cycle: %s", exc)
            raise

        self._cycle_count += 1
        self._promotion_history.extend(results)
        logger.info(
            "Promotion cycle #%d complete: %d evaluated, %d promoted",
            self._cycle_count,
            len(results),
            sum(1 for r in results if r.promoted),
        )

        return results

    def get_stats(self) -> PromotionStats:
        """إحصائيات الترقيات عبر جميع الدورات.

        Returns:
            ``PromotionStats`` مع ملخص شامل.
        """
        total = len(self._promotion_history)
        promoted = sum(1 for r in self._promotion_history if r.promoted)
        rejected = total - promoted
        return PromotionStats(
            total_evaluated=total,
            total_promoted=promoted,
            total_rejected=rejected,
            promotion_rate=(promoted / total) if total > 0 else 0.0,
            last_cycle_at=(
                datetime.now(timezone.utc).isoformat()
                if self._cycle_count > 0
                else ""
            ),
            cycle_count=self._cycle_count,
        )

    # ── داخلي / Internal ────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """التأكد من وجود الجداول المطلوبة في قاعدة البيانات."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.executescript(_CORRECTIONS_DDL)
        except sqlite3.Error as exc:
            logger.error("Failed to initialise corrections schema: %s", exc)
            raise

    @staticmethod
    def _days_since(iso_date: str) -> int:
        """حساب عدد الأيام منذ تاريخ ISO."""
        try:
            dt = datetime.fromisoformat(iso_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days
        except (ValueError, TypeError):
            return 999

    @staticmethod
    def _has_medical_conflict(original: str, corrected: str) -> bool:
        """فحص تعارض السمات الطبية بين الأصل والمصحّح.

        يستخدم `MedicalContextProtector` إن توفّر، وإلا يعود False.
        """
        try:
            from packages.core.medical_context_protector import (
                MedicalContextProtector,
            )
            protector = MedicalContextProtector()
            safe, _ = protector.check_merge_safety(original, corrected)
            return not safe
        except Exception:
            # إذا لم يتوفّر المحمي، نتجاهل هذا الفحص
            return False

    @staticmethod
    def _get_contexts(cur: sqlite3.Cursor, correction_id: int) -> list[str]:
        """استخراج السياقات الفريدة لتصحيح معيّن."""
        try:
            cur.execute(
                "SELECT DISTINCT context FROM corrections "
                "WHERE original = (SELECT original FROM corrections WHERE id = ?) "
                "AND corrected = (SELECT corrected FROM corrections WHERE id = ?)",
                (correction_id, correction_id),
            )
            return [row[0] for row in cur.fetchall() if row[0]]
        except sqlite3.Error:
            return []