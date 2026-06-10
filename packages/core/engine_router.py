"""
packages/core/engine_router.py
================================
موجّه محركات OCR الموحّد
دُمجت فيه نسختا core/engine_router.py و omni-core/engine_router.py

المميزات:
  - Cascading fallback: Mixed → Tesseract → Mistral → EasyOCR → Surya → TrOCR
  - Confidence threshold routing
  - Per-engine timeout وcircuit breaker
  - Language-aware routing (Arabic → PaddleOCR/TrOCR أولاً)
  - Metrics collection لكل engine
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


# ─── Engine Enum ──────────────────────────────────────────────

class Engine(str, Enum):
    MIXED     = "mixed_engine"
    TESSERACT = "tesseract"
    MISTRAL   = "mistral"
    EASYOCR   = "easyocr"
    SURYA     = "surya"
    TROCR     = "trocr"
    PADDLEOCR = "paddleocr"


# ─── Configuration ────────────────────────────────────────────

@dataclass
class EngineConfig:
    """إعدادات كل محرك OCR."""
    name: Engine
    enabled: bool = True
    timeout_seconds: float = 30.0
    min_confidence: float = 0.0     # لا يُستخدم إذا كان الـ engine الأخير
    priority: int = 0               # أصغر = أعلى أولوية
    arabic_optimized: bool = False  # للنصوص العربية — يُقدَّم هذا الـ engine
    gpu_required: bool = False


DEFAULT_ENGINE_CONFIGS: dict[Engine, EngineConfig] = {
    Engine.MIXED:     EngineConfig(Engine.MIXED,     priority=1, min_confidence=0.80),
    Engine.TESSERACT: EngineConfig(Engine.TESSERACT, priority=2, min_confidence=0.60),
    Engine.MISTRAL:   EngineConfig(Engine.MISTRAL,   priority=3, min_confidence=0.70, timeout_seconds=45),
    Engine.EASYOCR:   EngineConfig(Engine.EASYOCR,   priority=4, min_confidence=0.55),
    Engine.SURYA:     EngineConfig(Engine.SURYA,     priority=5, min_confidence=0.50),
    Engine.TROCR:     EngineConfig(Engine.TROCR,     priority=6, arabic_optimized=True, gpu_required=False),
    Engine.PADDLEOCR: EngineConfig(Engine.PADDLEOCR, priority=7, arabic_optimized=True),
}


# ─── Result ───────────────────────────────────────────────────

@dataclass
class RoutingResult:
    """نتيجة المعالجة من موجّه المحركات."""
    text: str
    confidence: float
    engine_used: Engine
    fallback_chain: list[Engine] = field(default_factory=list)
    processing_ms: float = 0.0
    language_detected: Optional[str] = None
    error_messages: list[str] = field(default_factory=list)

    @property
    def used_fallback(self) -> bool:
        return len(self.fallback_chain) > 1

    @property
    def success(self) -> bool:
        return bool(self.text.strip()) and self.confidence > 0.0


# ─── Circuit Breaker ──────────────────────────────────────────

class _CircuitBreaker:
    """يمنع محركاً فاشلاً من إبطاء كل الطلبات."""

    def __init__(self, failure_threshold: int = 3, reset_seconds: float = 60.0):
        self._failures: dict[Engine, int] = {}
        self._last_failure: dict[Engine, float] = {}
        self._threshold = failure_threshold
        self._reset = reset_seconds

    def is_open(self, engine: Engine) -> bool:
        failures = self._failures.get(engine, 0)
        if failures < self._threshold:
            return False
        last = self._last_failure.get(engine, 0.0)
        if time.monotonic() - last > self._reset:
            self._failures[engine] = 0
            return False
        return True

    def record_failure(self, engine: Engine) -> None:
        self._failures[engine] = self._failures.get(engine, 0) + 1
        self._last_failure[engine] = time.monotonic()

    def record_success(self, engine: Engine) -> None:
        self._failures[engine] = 0


# ─── Engine Router ────────────────────────────────────────────

class EngineRouter:
    """
    موجّه محركات OCR الموحّد.

    الاستخدام:
        router = EngineRouter(engine_order="mixed_engine,tesseract,mistral")
        result = router.process(image, language="ar")
    """

    def __init__(
        self,
        engine_order: str = "mixed_engine,tesseract,mistral,easyocr",
        configs: Optional[dict[Engine, EngineConfig]] = None,
        confidence_threshold: float = 0.75,
        arabic_threshold: float = 0.70,
    ):
        self._order = self._parse_order(engine_order)
        self._configs = configs or DEFAULT_ENGINE_CONFIGS
        self._confidence_threshold = confidence_threshold
        self._arabic_threshold = arabic_threshold
        self._circuit = _CircuitBreaker()
        self._handlers: dict[Engine, Callable] = {}
        self._metrics: dict[Engine, dict] = {e: {"calls": 0, "success": 0, "total_ms": 0.0} for e in Engine}

    # ── Public API ────────────────────────────────────────────

    def register_handler(self, engine: Engine, handler: Callable) -> None:
        """سجّل دالة معالجة للمحرك. الدالة تستقبل (image, **kwargs) وتُرجع (text, confidence)."""
        self._handlers[engine] = handler

    def process(
        self,
        image: Any,
        language: str = "auto",
        force_engine: Optional[Engine] = None,
        **kwargs,
    ) -> RoutingResult:
        """معالجة صورة عبر سلسلة المحركات مع fallback تلقائي."""
        start = time.monotonic()

        if force_engine:
            order = [force_engine]
        elif language in ("ar", "arabic"):
            order = self._arabic_order()
        else:
            order = self._order

        chain: list[Engine] = []
        errors: list[str] = []

        for engine in order:
            cfg = self._configs.get(engine, EngineConfig(engine))
            if not cfg.enabled:
                continue
            if self._circuit.is_open(engine):
                logger.debug(f"Circuit open for {engine} — skipping")
                continue
            if engine not in self._handlers:
                logger.debug(f"No handler registered for {engine} — skipping")
                continue

            chain.append(engine)
            try:
                text, confidence = self._call_engine(engine, image, cfg, **kwargs)
                self._circuit.record_success(engine)
                self._record_metric(engine, True, time.monotonic() - start)

                threshold = self._arabic_threshold if language in ("ar", "arabic") else self._confidence_threshold
                if confidence >= threshold or engine == order[-1]:
                    return RoutingResult(
                        text=text,
                        confidence=confidence,
                        engine_used=engine,
                        fallback_chain=chain,
                        processing_ms=(time.monotonic() - start) * 1000,
                        language_detected=language,
                        error_messages=errors,
                    )
                else:
                    logger.info(f"{engine}: confidence {confidence:.2f} < threshold {threshold:.2f} — trying next")

            except Exception as exc:
                self._circuit.record_failure(engine)
                self._record_metric(engine, False, time.monotonic() - start)
                msg = f"{engine}: {type(exc).__name__}: {exc}"
                errors.append(msg)
                logger.warning(msg)

        # إذا فشلت كل المحركات
        return RoutingResult(
            text="",
            confidence=0.0,
            engine_used=chain[-1] if chain else Engine.TESSERACT,
            fallback_chain=chain,
            processing_ms=(time.monotonic() - start) * 1000,
            error_messages=errors,
        )

    def get_metrics(self) -> dict[str, dict]:
        """إحصائيات الأداء لكل محرك."""
        out = {}
        for engine, m in self._metrics.items():
            calls = m["calls"] or 1
            out[engine.value] = {
                "calls": m["calls"],
                "success_rate": round(m["success"] / calls, 3),
                "avg_ms": round(m["total_ms"] / calls, 1),
            }
        return out

    def set_engine_enabled(self, engine: Engine, enabled: bool) -> None:
        if engine in self._configs:
            self._configs[engine].enabled = enabled

    # ── Internal ──────────────────────────────────────────────

    def _call_engine(self, engine: Engine, image: Any, cfg: EngineConfig, **kwargs):
        import signal

        handler = self._handlers[engine]

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"{engine} exceeded {cfg.timeout_seconds}s timeout")

        # timeouts only on Unix
        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(int(cfg.timeout_seconds))
            result = handler(image, **kwargs)
            signal.alarm(0)
            return result
        except AttributeError:
            # Windows — no SIGALRM
            return handler(image, **kwargs)

    def _arabic_order(self) -> list[Engine]:
        """أعد ترتيب المحركات للعربية — TrOCR وPaddleOCR أولاً."""
        arabic_first = [e for e in self._order if self._configs.get(e, EngineConfig(e)).arabic_optimized]
        rest = [e for e in self._order if e not in arabic_first]
        return arabic_first + rest

    def _parse_order(self, order_str: str) -> list[Engine]:
        result = []
        for name in order_str.split(","):
            name = name.strip()
            try:
                result.append(Engine(name))
            except ValueError:
                logger.warning(f"Unknown engine '{name}' in OCR_ENGINE_ORDER — ignored")
        return result or [Engine.TESSERACT]

    def _record_metric(self, engine: Engine, success: bool, elapsed: float) -> None:
        m = self._metrics[engine]
        m["calls"] += 1
        if success:
            m["success"] += 1
        m["total_ms"] += elapsed * 1000
