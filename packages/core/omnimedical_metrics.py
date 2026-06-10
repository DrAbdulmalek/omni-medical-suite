#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
omnimedical_metrics.py
=======================
مصدّر مقاييس Prometheus لمجموعة OmniMedical الطبية.

يتضمّن عدّادات ومقاييس ومدرّجات تكرارية لـ:
  - health_score           : Gauge — درجة الصحة الإجمالية
  - health_check_total     : Counter — إجمالي فحوصات الصحة
  - fusion_strategy_total  : Counter — عدد مرات استخدام كل استراتيجية دمج
  - fusion_confidence_*    : Histogram — الثقة قبل وبعد الدمج
  - review_queue_size      : Gauge — حجم قائمة المراجعة
  - corrections_saved_total: Counter — عدد التصحيحات المحفوظة
  - ocr_confidence_final   : Histogram — الثقة النهائية لـ OCR
  - security_checks        : Counter — فحوصات الأمان

إذا لم يتوفّر ``prometheus_client`` يُستخدم ``NoOpMetrics``
الذي يُتجاهل جميع العمليات بصمت.

Prometheus metrics exporter for OmniMedical Suite.
"""

from __future__ import annotations

import logging
import time
from typing import Any

__all__ = [
    "MetricsExporter",
    "NoOpMetrics",
    "get_metrics_exporter",
]

logger = logging.getLogger(__name__)

# ── محاولة استيراد Prometheus / Try importing prometheus_client ────────
_PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import (  # type: ignore[import-untyped]
        Counter,
        Gauge,
        Histogram,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.debug(
        "prometheus_client not installed — using NoOpMetrics."
    )


# ═══════════════════════════════════════════════════════════════════════════
# NoOp — بديل صامت عند عدم توفر Prometheus
# ═══════════════════════════════════════════════════════════════════════════

class NoOpMetrics:
    """
    بديل صامت لا يفعل شيئاً.

    Silent no-op replacement used when ``prometheus_client`` is not
    installed. All methods accept any arguments and return *None*.
    """

    def __init__(self, **kwargs: Any) -> None:  # noqa: D401
        pass

    # Gauge
    def update_health(self, score: float) -> None:
        """No-op."""
        pass

    def update_review_queue_size(self, size: int) -> None:
        """No-op."""
        pass

    # Counter
    def increment_health_check(self, status: str = "ok") -> None:
        """No-op."""
        pass

    def record_fusion(
        self,
        strategy: str,
        confidence_before: float,
        confidence_after: float,
    ) -> None:
        """No-op."""
        pass

    def record_correction(
        self,
        original: str,
        corrected: str,
        confidence_gain: float,
    ) -> None:
        """No-op."""
        pass

    def increment_security_check(
        self, check_type: str, result: str = "pass"
    ) -> None:
        """No-op."""
        pass

    # Histogram
    def update_ocr_confidence(self, confidence: float) -> None:
        """No-op."""
        pass


# ═══════════════════════════════════════════════════════════════════════════
# MetricsExporter — المصدّر الحقيقي
# ═══════════════════════════════════════════════════════════════════════════

if _PROMETHEUS_AVAILABLE:

    class MetricsExporter:  # type: ignore[no-redef]
        """
        مصدّر مقاييس Prometheus لمجموعة OmniMedical.

        Prometheus metrics exporter for the OmniMedical Suite.

        Exposes the following metrics:

        ======================  ============  ===================================
        Metric name             Type          Description
        ======================  ============  ===================================
        omnimedical_health      Gauge         Overall health score (0-1)
        omnimedical_health_chk  Counter       Total health checks (by status)
        omnimedical_fusion_str  Counter       Fusion strategy usage count
        omnimedical_fusion_conf Histogram     Confidence before/after fusion
        omnimedical_review_q    Gauge         Review queue depth
        omnimedical_corr_saved  Counter       Corrections saved total
        omnimedical_ocr_conf    Histogram     Final OCR confidence
        omnimedical_sec_checks  Counter       Security check results
        ======================  ============  ===================================
        """

        NAMESPACE = "omnimedical"

        def __init__(self, **kwargs: Any) -> None:  # noqa: D401
            ns = self.NAMESPACE

            # ── Gauge ───────────────────────────────────────────────────
            self._health_score = Gauge(
                f"{ns}_health_score",
                "Overall health score (0-1)",
            )
            self._review_queue_size = Gauge(
                f"{ns}_review_queue_size",
                "Current review queue depth",
            )

            # ── Counter ─────────────────────────────────────────────────
            self._health_check_total = Counter(
                f"{ns}_health_check_total",
                "Total health checks",
                ["status"],
            )
            self._fusion_strategy_total = Counter(
                f"{ns}_fusion_strategy_total",
                "Fusion strategy usage count",
                ["strategy"],
            )
            self._corrections_saved_total = Counter(
                f"{ns}_corrections_saved_total",
                "Total corrections saved",
            )
            self._security_checks = Counter(
                f"{ns}_security_checks",
                "Security check results",
                ["check_type", "result"],
            )

            # ── Histogram ───────────────────────────────────────────────
            self._fusion_confidence_before = Histogram(
                f"{ns}_fusion_confidence_before",
                "Confidence before fusion",
                buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            )
            self._fusion_confidence_after = Histogram(
                f"{ns}_fusion_confidence_after",
                "Confidence after fusion",
                buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            )
            self._ocr_confidence_final = Histogram(
                f"{ns}_ocr_confidence_final",
                "Final OCR confidence score",
                buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            )

        # ── Health ───────────────────────────────────────────────────────

        def update_health(self, score: float) -> None:
            """تحديث مقياس الصحة الإجمالي."""
            self._health_score.set(max(0.0, min(1.0, score)))
            self._health_check_total.labels(
                status="healthy" if score >= 0.8 else (
                    "degraded" if score >= 0.5 else "unhealthy"
                )
            ).inc()

        # ── Fusion ───────────────────────────────────────────────────────

        def record_fusion(
            self,
            strategy: str,
            confidence_before: float,
            confidence_after: float,
        ) -> None:
            """تسجيل عملية دمج OCR.

            Args:
                strategy: اسم استراتيجية الدمج.
                confidence_before: الثقة قبل الدمج.
                confidence_after: الثقة بعد الدمج.
            """
            self._fusion_strategy_total.labels(strategy=strategy).inc()
            if confidence_before > 0:
                self._fusion_confidence_before.observe(confidence_before)
            if confidence_after > 0:
                self._fusion_confidence_after.observe(confidence_after)

        # ── OCR ──────────────────────────────────────────────────────────

        def update_ocr_confidence(self, confidence: float) -> None:
            """تسجيل الثقة النهائية لـ OCR.

            Args:
                confidence: درجة الثقة النهائية (0-1).
            """
            self._ocr_confidence_final.observe(confidence)

        # ── Corrections ──────────────────────────────────────────────────

        def record_correction(
            self,
            original: str,
            corrected: str,
            confidence_gain: float,
        ) -> None:
            """تسجيل تصحيح جديد.

            Args:
                original: النص الأصلي.
                corrected: النص المصحّح.
                confidence_gain: مقدار التحسّن في الثقة.
            """
            self._corrections_saved_total.inc()
            logger.debug(
                "Correction recorded: '%s' → '%s' (gain=%.3f)",
                original,
                corrected,
                confidence_gain,
            )

        # ── Review queue ────────────────────────────────────────────────

        def update_review_queue_size(self, size: int) -> None:
            """تحديث حجم قائمة المراجعة.

            Args:
                size: عدد العناصر في القائمة.
            """
            self._review_queue_size.set(max(0, size))

        # ── Security ────────────────────────────────────────────────────

        def increment_security_check(
            self, check_type: str, result: str = "pass"
        ) -> None:
            """تسجيل نتيجة فحص أمان.

            Args:
                check_type: نوع الفحص (e.g., ``"input_validation"``).
                result: النتيجة (``"pass"`` / ``"fail"``).
            """
            self._security_checks.labels(
                check_type=check_type, result=result
            ).inc()

else:
    # Prometheus غير متوفر — استخدم NoOp
    MetricsExporter = NoOpMetrics  # type: ignore[misc,assignment]


# ═══════════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════════

_exporter_instance: MetricsExporter | None = None


def get_metrics_exporter() -> MetricsExporter:
    """إرجاع مفرد المصدّر (Singleton).

    Returns the global ``MetricsExporter`` instance, creating it on
    first call.
    """
    global _exporter_instance
    if _exporter_instance is None:
        _exporter_instance = MetricsExporter()
    return _exporter_instance