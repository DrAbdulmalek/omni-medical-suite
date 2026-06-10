#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_orchestrator.py
=========================
المنسّق الرئيسي لخط المعالجة الكامل.

يربط جميع المكونات: OCR متوازي ← دمج V2 ← تقسيم دلالي ←
إزالة تكرار دلالي ← تجميع النتائج.

Pipeline orchestrator that ties everything together:
  OCR parallel → Fusion V2 → Semantic Chunking → Semantic Dedup →
  output aggregation.

يدعم المعالجة المجمّعة (DocumentBatch)، قاطع الدائرة
(Circuit Breaker) بحدّ 5 إخفاقات متتالية وإعادة تعيين بعد 300 ثانية،
وتكامل Prometheus (تحميل كسول).
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "DocumentBatch",
    "PipelineConfig",
    "PipelineResult",
    "ProcessingPipeline",
]

logger = logging.getLogger(__name__)


# ── حالة قاطع الدائرة / Circuit breaker states ──────────────────────────
class CircuitState(str, Enum):
    """حالات قاطع الدائرة."""

    CLOSED = "closed"      # يعمل طبيعياً
    OPEN = "open"          # مفتوح — يرفض الطلبات
    HALF_OPEN = "half_open"  # نصف مفتوح — يسمح بطلب اختبار


class CircuitBreaker:
    """
    قاطع دائرة بسيط لحماية خط المعالجة.

    Simple circuit breaker to protect the processing pipeline from
    cascading failures.

    Parameters
    ----------
    failure_threshold : int
        Number of consecutive failures before opening (default 5).
    reset_timeout_seconds : float
        Seconds to wait before transitioning from OPEN to HALF_OPEN
        (default 300).
    half_open_max_calls : int
        Max test calls in HALF_OPEN state (default 1).
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 300.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0

    @property
    def state(self) -> CircuitState:
        """الحالة الحالية (مع تحويل تلقائي من OPEN إلى HALF_OPEN)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.reset_timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    "Circuit breaker transitioning OPEN → HALF_OPEN "
                    "(%.0fs elapsed)",
                    elapsed,
                )
        return self._state

    def allow_request(self) -> bool:
        """هل يُسمح بتنفيذ الطلب؟"""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        # OPEN
        return False

    def record_success(self) -> None:
        """تسجيل نجاح — يعيد تعيين العداد."""
        self._failure_count = 0
        if self._state != CircuitState.CLOSED:
            logger.info(
                "Circuit breaker transitioning %s → CLOSED",
                self._state.value,
            )
        self._state = CircuitState.CLOSED
        self._half_open_calls = 0

    def record_failure(self) -> None:
        """تسجيل إخفاق."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.warning(
                    "Circuit breaker transitioning %s → OPEN "
                    "(%d consecutive failures)",
                    self._state.value,
                    self._failure_count,
                )
            self._state = CircuitState.OPEN


# ── أنواع البيانات / Data types ──────────────────────────────────────────


@dataclass(slots=True)
class PipelineConfig:
    """إعدادات خط المعالجة / Pipeline configuration."""

    # OCR
    ocr_engines: list[str] = field(
        default_factory=lambda: ["tesseract", "easyocr", "paddleocr"]
    )
    ocr_max_workers: int = 4
    ocr_confidence_threshold: float = 0.55

    # Fusion
    fusion_dbscan_eps: int = 15
    fusion_medical_bonus: float = 1.4

    # Deduplication
    dedup_enabled: bool = True
    dedup_similarity_threshold: float = 0.82

    # Batch
    batch_size: int = 10

    # General
    enable_metrics: bool = True
    timeout_seconds: float = 120.0


@dataclass(slots=True)
class PipelineResult:
    """نتيجة معالجة المستند / Document processing result."""

    text: str
    confidence: float
    processing_time: float
    engine_used: str
    fusion_strategy: str
    dedup_stats: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "processing_time": round(self.processing_time, 3),
            "engine_used": self.engine_used,
            "fusion_strategy": self.fusion_strategy,
            "dedup_stats": self.dedup_stats,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class DocumentBatch:
    """دفعة مستندات للمعالجة / Batch of documents to process."""

    paths: list[str | Path]
    config: PipelineConfig | None = None


class ProcessingPipeline:
    """
    المنسّق الرئيسي لخط المعالجة الكامل.

    Orchestrates the full document processing pipeline:
      1. Run OCR engines in parallel.
      2. Fuse results with ``OCRFusionV2``.
      3. Semantic chunking (simple sentence/paragraph split).
      4. Semantic deduplication.
      5. Aggregate and return results.

    Includes circuit-breaker protection and optional Prometheus metrics.
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        """
        Args:
            config: إعدادات خط المعالجة. يستخدم الافتراضية إن لم يُحدَّد.
        """
        self.config = config or PipelineConfig()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            reset_timeout_seconds=300.0,
        )
        self._metrics: Any = None

        if self.config.enable_metrics:
            self._init_metrics()

    def process(
        self,
        image_path: str | Path,
        config: PipelineConfig | None = None,
    ) -> PipelineResult:
        """معالجة صورة واحدة عبر خط المعالجة الكامل.

        Args:
            image_path: مسار الصورة.
            config: إعدادات تجاوز (اختياري).

        Returns:
            ``PipelineResult`` مع النص والثقة والتفاصيل.
        """
        cfg = config or self.config
        start_time = time.monotonic()
        image_path = Path(image_path)

        # فحص قاطع الدائرة
        if not self._circuit_breaker.allow_request():
            elapsed = time.monotonic() - start_time
            logger.error("Circuit breaker OPEN — request rejected.")
            self._record_metrics_failure("circuit_open", elapsed)
            return PipelineResult(
                text="",
                confidence=0.0,
                processing_time=elapsed,
                engine_used="none",
                fusion_strategy="none",
                error="Circuit breaker is OPEN — service temporarily unavailable",
            )

        try:
            # ── 1. OCR متوازي / Parallel OCR ──────────────────────────
            engine_results = self._run_ocr_parallel(image_path, cfg)

            if not engine_results:
                raise RuntimeError(
                    "All OCR engines failed to produce results."
                )

            # ── 2. دمج V2 / Fusion V2 ─────────────────────────────────
            fused = self._fuse_results(engine_results, cfg)

            # ── 3. تقسيم دلالي / Semantic chunking ──────────────────
            chunks = self._semantic_chunk(fused.text)

            # ── 4. إزالة التكرار الدلالي / Semantic dedup ────────────
            dedup_stats: dict[str, Any] = {"input_chunks": len(chunks)}
            final_text = fused.text
            if cfg.dedup_enabled and len(chunks) > 1:
                final_text = self._deduplicate_chunks(chunks, cfg)
                dedup_stats["dedup_applied"] = True
            else:
                dedup_stats["dedup_applied"] = False

            elapsed = time.monotonic() - start_time

            # ── تسجيل النجاح / Record success ────────────────────────
            self._circuit_breaker.record_success()
            self._record_metrics_success(
                fused.strategy_used,
                fused.confidence,
                elapsed,
            )

            engines_used = ", ".join(
                sorted(set(r.engine_name for r in engine_results))
            )

            return PipelineResult(
                text=final_text,
                confidence=fused.confidence,
                processing_time=elapsed,
                engine_used=engines_used,
                fusion_strategy=fused.strategy_used,
                dedup_stats=dedup_stats,
                metadata={
                    "input_file": str(image_path.name),
                    "ocr_tokens": len(engine_results),
                },
            )

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            self._circuit_breaker.record_failure()
            logger.error("Pipeline processing failed: %s", exc, exc_info=True)
            self._record_metrics_failure("processing_error", elapsed)

            return PipelineResult(
                text="",
                confidence=0.0,
                processing_time=elapsed,
                engine_used="none",
                fusion_strategy="none",
                error=str(exc),
            )

    def process_batch(self, batch: DocumentBatch) -> list[PipelineResult]:
        """معالجة دفعة من المستندات.

        Args:
            batch: الدفعة (قائمة مسارات + إعدادات اختيارية).

        Returns:
            قائمة نتائج المعالجة بترتيب المسارات.
        """
        cfg = batch.config or self.config
        results: list[PipelineResult] = []

        with ThreadPoolExecutor(
            max_workers=cfg.batch_size
        ) as executor:
            future_to_path = {
                executor.submit(self.process, p, cfg): p
                for p in batch.paths
            }
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result(timeout=cfg.timeout_seconds)
                    results.append(result)
                except Exception as exc:
                    logger.error(
                        "Batch processing error for %s: %s", path, exc
                    )
                    results.append(
                        PipelineResult(
                            text="",
                            confidence=0.0,
                            processing_time=0.0,
                            engine_used="none",
                            fusion_strategy="none",
                            error=f"Batch error: {exc}",
                            metadata={"input_file": str(path)},
                        )
                    )

        return results

    # ── المراحل الداخلية / Internal stages ───────────────────────────────

    def _run_ocr_parallel(
        self, image_path: Path, cfg: PipelineConfig
    ) -> list[Any]:
        """تشغيل محركات OCR بالتوازي."""
        from packages.core.ocr_fusion_v2 import BBox, EngineResult

        results: list[EngineResult] = []

        def _try_engine(engine_name: str) -> EngineResult | None:
            try:
                text, confidence = self._call_ocr_engine(
                    str(image_path), engine_name
                )
                return EngineResult(
                    text=text,
                    confidence=confidence,
                    bbox=BBox(),  # سيُملأ إن توفّر من المحرك
                    engine_name=engine_name,
                )
            except Exception as exc:
                logger.debug(
                    "OCR engine '%s' failed for %s: %s",
                    engine_name,
                    image_path.name,
                    exc,
                )
                return None

        with ThreadPoolExecutor(
            max_workers=cfg.ocr_max_workers
        ) as executor:
            futures = {
                executor.submit(_try_engine, eng): eng
                for eng in cfg.ocr_engines
            }
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)

        return results

    @staticmethod
    def _call_ocr_engine(image_path: str, engine_name: str) -> tuple[str, float]:
        """استدعاء محرك OCR بالاسم.

        يعود بنص ودرجة ثقة. يرفع ImportError إن لم يكن المحرك متاحاً.
        """
        if engine_name == "tesseract":
            import pytesseract  # type: ignore[import-untyped]
            from PIL import Image

            img = Image.open(image_path)
            data = pytesseract.image_to_data(
                img, lang="ara+eng", output_type=pytesseract.Output.DICT
            )
            # حساب متوسط الثقة للنصوص المكتشفة
            texts: list[str] = []
            confs: list[float] = []
            for t, c in zip(data["text"], data["conf"]):
                t = t.strip()
                if t and c > 0:
                    texts.append(t)
                    confs.append(c / 100.0)
            full_text = " ".join(texts)
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            return full_text, avg_conf

        elif engine_name == "easyocr":
            import easyocr  # type: ignore[import-untyped]
            import numpy as np  # type: ignore[import-untyped]

            reader = easyocr.Reader(["ar", "en"], gpu=False)
            ocr_results = reader.readtext(str(image_path))
            if not ocr_results:
                return "", 0.0
            texts = [r[1] for r in ocr_results]
            confs = [r[2] for r in ocr_results]
            return " ".join(texts), sum(confs) / len(confs)

        elif engine_name == "paddleocr":
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]

            ocr = PaddleOCR(use_angle_cls=True, lang="ar")
            result = ocr.ocr(str(image_path), cls=True)
            if not result or not result[0]:
                return "", 0.0
            texts = [line[1][0] for line in result[0]]
            confs = [line[1][1] for line in result[0]]
            return " ".join(texts), sum(confs) / len(confs)

        elif engine_name == "trocr":
            from transformers import pipeline  # type: ignore[import-untyped]

            ocr_pipe = pipeline(
                "image-to-text",
                model="microsoft/trocr-base-handwritten",
            )
            result = ocr_pipe(str(image_path))
            text = result[0]["generated_text"] if result else ""
            return text, 0.85  # TrOCR default confidence estimate

        elif engine_name == "surya":
            from surya_ocr import run_ocr  # type: ignore[import-untyped]

            result = run_ocr(str(image_path))
            texts = [r.text for r in result]
            return " ".join(texts), 0.87

        else:
            raise ValueError(f"Unknown OCR engine: {engine_name}")

    @staticmethod
    def _fuse_results(
        engine_results: list[Any], cfg: PipelineConfig
    ) -> Any:
        """دمج نتائج OCR باستخدام FusionV2."""
        from packages.core.ocr_fusion_v2 import OCRFusionV2

        fusion = OCRFusionV2(
            min_confidence=cfg.ocr_confidence_threshold,
            dbscan_eps=cfg.fusion_dbscan_eps,
            medical_bonus=cfg.fusion_medical_bonus,
        )
        return fusion.fuse(engine_results)

    @staticmethod
    def _semantic_chunk(text: str) -> list[str]:
        """تقسيم نص إلى قطع دلالية بسيطة (جمل/فقرات).

        Uses simple heuristics: split on double-newlines first,
        then on sentence-ending punctuation.
        """
        if not text.strip():
            return []

        # محاولة التقسيم بالفقرات
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) > 1:
            return paragraphs

        # محاولة التقسيم بالجمل
        import re

        sentences = re.split(r"(?<=[.!?؟。])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 1:
            return sentences

        # القطع النصية الكبيرة (كل 200 حرف كحد أقصى)
        if len(text) > 200:
            chunks = []
            for i in range(0, len(text), 200):
                chunk = text[i : i + 200].strip()
                if chunk:
                    chunks.append(chunk)
            return chunks

        return [text] if text.strip() else []

    def _deduplicate_chunks(
        self, chunks: list[str], cfg: PipelineConfig
    ) -> str:
        """إزالة التكرار الدلالي وإعادة تجميع النص."""
        try:
            from packages.core.semantic_deduplication import (
                SemanticDeduplicator,
            )

            dedup = SemanticDeduplicator(
                similarity_threshold=cfg.dedup_similarity_threshold,
            )
            results = dedup.deduplicate(chunks)

            unique_texts = []
            for r in results:
                if r.status == "merged":
                    unique_texts.append(r.text)
                else:
                    unique_texts.append(r.text)

            return "\n".join(unique_texts)
        except Exception as exc:
            logger.warning(
                "Semantic deduplication failed, returning original: %s",
                exc,
            )
            return "\n".join(chunks)

    # ── Prometheus metrics (lazy) ─────────────────────────────────────────

    def _init_metrics(self) -> None:
        """تحميل Prometheus metrics بالكسل."""
        try:
            from packages.core.omnimedical_metrics import MetricsExporter

            self._metrics = MetricsExporter()
            logger.info("Prometheus metrics exporter initialised.")
        except Exception as exc:
            logger.debug("Metrics not available: %s", exc)
            self._metrics = None

    def _record_metrics_success(
        self,
        strategy: str,
        confidence: float,
        elapsed: float,
    ) -> None:
        """تسجيل مقاييس النجاح."""
        if self._metrics is None:
            return
        try:
            self._metrics.record_fusion(
                strategy=strategy,
                confidence_before=0.0,
                confidence_after=confidence,
            )
        except Exception:
            pass

    def _record_metrics_failure(
        self, reason: str, elapsed: float
    ) -> None:
        """تسجيل مقاييس الإخفاق."""
        if self._metrics is None:
            return
        try:
            self._metrics.update_health(0.0)
        except Exception:
            pass