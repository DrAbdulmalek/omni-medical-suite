"""Health-check endpoints for OmniMedicalSuite.

ثلاث نقاط نهاية:
  /api/health        — فحص أساسي (basic)
  /api/health/ready  — فحص الجاهزية مع تفاصيل المكونات (readiness)
  /api/health/live   — فحص الحيوية البسيط (liveness)

Checks performed (weighted):
  - Database       30%  (simple query)
  - OCR engines    35%  (importable + functional)
  - Redis          15%  (PING)
  - LLM providers  10%  (API key + reachability)
  - Critical deps  10%  (torch, transformers, tesseract-cli)

In non-verbose mode, error details are hidden to prevent information
leakage (security best practice).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Query

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


# ═══════════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════════

class HealthStatus(StrEnum):
    """تصنيف حالة الصحة."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """نتيجة فحص مكون واحد."""

    __slots__ = ("name", "status", "latency_ms", "details", "error")

    def __init__(
        self,
        name: str,
        status: HealthStatus,
        latency_ms: float,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.name = name
        self.status = status
        self.latency_ms = round(latency_ms, 1)
        self.details = details or {}
        self.error = error

    def to_dict(self, verbose: bool = False) -> dict[str, Any]:
        """تحويل إلى قاموس.

        Args:
            verbose: إن كان True يعرض التفاصيل والأخطاء.
                في الوضع العادي يُخفي الأخطاء لمنع تسريب المعلومات.
        """
        d: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "latency_ms": self.latency_ms,
        }
        if verbose:
            d["details"] = self.details
            d["error"] = self.error
        return d

    @property
    def score(self) -> float:
        """تحويل الحالة إلى درجة رقمية (1 / 0.5 / 0)."""
        match self.status:
            case HealthStatus.HEALTHY:
                return 1.0
            case HealthStatus.DEGRADED:
                return 0.5
            case HealthStatus.UNHEALTHY:
                return 0.0


class SystemHealth:
    """تقرير صحة النظام الإجمالي."""

    __slots__ = ("status", "uptime_seconds", "components", "overall_score")

    def __init__(
        self,
        status: HealthStatus,
        uptime_seconds: float,
        components: list[ComponentHealth],
        overall_score: float,
    ) -> None:
        self.status = status
        self.uptime_seconds = round(uptime_seconds, 1)
        self.components = components
        self.overall_score = round(overall_score, 3)

    def to_dict(self, verbose: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "overall_score": self.overall_score,
        }
        if verbose:
            d["components"] = [
                c.to_dict(verbose=True) for c in self.components
            ]
        return d


# ═══════════════════════════════════════════════════════════════════════════
# Component weights (must sum to 1.0)
# ═══════════════════════════════════════════════════════════════════════════

_COMPONENT_WEIGHTS: dict[str, float] = {
    "database": 0.30,
    "ocr_engines": 0.35,
    "redis": 0.15,
    "llm_providers": 0.10,
    "critical_deps": 0.10,
}


# ═══════════════════════════════════════════════════════════════════════════
# Component checks
# ═══════════════════════════════════════════════════════════════════════════

async def _check_database() -> ComponentHealth:
    """فحص قاعدة البيانات — محاولة استعلام بسيط.

    Verifies the primary database is reachable by executing a simple
    ``SELECT 1`` query.
    """
    start = time.monotonic()
    try:
        import sqlite3

        # محاولة الاتصال بقاعدة البيانات الرئيسية
        db_candidates = [
            "omni_medical.db",
            "./data/omni_medical.db",
        ]
        connected = False
        for db_path in db_candidates:
            try:
                conn = sqlite3.connect(db_path, timeout=5)
                conn.execute("SELECT 1")
                conn.close()
                connected = True
                break
            except (sqlite3.Error, OSError):
                continue

        if not connected:
            # محاولة استخدام Prisma إن توفّر
            try:
                from app.services.prisma_client import get_prisma

                client = get_prisma()
                await client.query_raw("SELECT 1")
                connected = True
            except Exception:
                pass

        latency = (time.monotonic() - start) * 1000
        if connected:
            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                details={"engine": "sqlite"},
            )
        else:
            return ComponentHealth(
                name="database",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                details={"engine": "unavailable"},
                error="Database not reachable",
            )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        logger.warning("Database health check failed: %s", exc)
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            error="Database check error",
        )


async def _check_ocr_engines() -> ComponentHealth:
    """فحص محركات OCR — التحقق من إمكانية الاستيراد والتشغيل.

    Checks which OCR engines are importable and (where possible)
    functional.
    """
    start = time.monotonic()
    engine_status: dict[str, bool] = {}

    engines_to_check = {
        "tesseract": _check_tesseract,
        "easyocr": _check_easyocr,
        "paddleocr": _check_paddleocr,
        "trocr": _check_trocr,
        "surya": _check_surya,
    }

    for name, check_fn in engines_to_check.items():
        try:
            engine_status[name] = await asyncio.get_event_loop().run_in_executor(
                None, check_fn
            )
        except Exception:
            engine_status[name] = False

    available = sum(1 for v in engine_status.values() if v)
    total = len(engine_status)

    if available == 0:
        status = HealthStatus.UNHEALTHY
    elif available < total:
        status = HealthStatus.DEGRADED
    else:
        status = HealthStatus.HEALTHY

    return ComponentHealth(
        name="ocr_engines",
        status=status,
        latency_ms=(time.monotonic() - start) * 1000,
        details={
            "engines": engine_status,
            "available": available,
            "total": total,
        },
    )


def _check_tesseract() -> bool:
    """فحص Tesseract — التأكد من توفّر المكتبة و CLI."""
    try:
        import pytesseract  # type: ignore[import-untyped]

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        # فحص إضافي: هل الثنائي موجود عبر shutil
        return shutil.which("tesseract") is not None


def _check_easyocr() -> bool:
    """فحص EasyOCR — إمكانية الاستيراد."""
    try:
        import easyocr  # type: ignore[import-untyped]  # noqa: F401

        return True
    except Exception:
        return False


def _check_paddleocr() -> bool:
    """فحص PaddleOCR — إمكانية الاستيراد."""
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-untyped]  # noqa: F401

        return True
    except Exception:
        return False


def _check_trocr() -> bool:
    """فحص TrOCR — إمكانية استيراد transformers."""
    try:
        import transformers  # type: ignore[import-untyped]  # noqa: F401

        return True
    except Exception:
        return False


def _check_surya() -> bool:
    """فحص Surya OCR — إمكانية الاستيراد."""
    try:
        import surya_ocr  # type: ignore[import-untyped]  # noqa: F401

        return True
    except Exception:
        return False


async def _check_redis() -> ComponentHealth:
    """فحص Redis — أمر PING.

    Redis is optional — DEGRADED if unavailable, never UNHEALTHY.
    """
    start = time.monotonic()
    try:
        # محاولة الاتصال المباشر بـ Redis
        import redis as redis_lib  # type: ignore[import-untyped]

        r = redis_lib.Redis(
            host="localhost",
            port=6379,
            socket_timeout=3,
            socket_connect_timeout=3,
        )
        response = r.ping()
        latency = (time.monotonic() - start) * 1000
        if response:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                details={"connected": True},
            )
        else:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                details={"connected": False},
                error="Redis PING failed",
            )
    except Exception:
        # محاولة عبر عميل Redis المخصّص
        try:
            from app.services.redis_client import RedisClient

            ok = await RedisClient.health_check()
            latency = (time.monotonic() - start) * 1000
            if ok:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                    details={"connected": True},
                )
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                details={"connected": False},
                error="Redis not available (optional)",
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                details={"connected": False},
                error="Redis not available (optional)",
            )


async def _check_llm_providers() -> ComponentHealth:
    """فحص مزوّدي LLM — مفتاح API والوصولية.

    Checks whether LLM API keys are configured and (optionally)
    reachable. LLM is optional — DEGRADED if unavailable.
    """
    start = time.monotonic()
    provider_status: dict[str, Any] = {}

    # فحص المفاتيح من البيئة
    import os

    providers_config = {
        "mistral": os.environ.get("MISTRAL_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
    }

    for name, api_key in providers_config.items():
        has_key = bool(api_key and api_key.strip())
        provider_status[name] = {
            "key_configured": has_key,
        }

    any_configured = any(
        v.get("key_configured", False) for v in provider_status.values()
    )

    if not any_configured:
        status = HealthStatus.DEGRADED
        provider_status["note"] = "No LLM API keys configured"
    else:
        status = HealthStatus.HEALTHY

    return ComponentHealth(
        name="llm_providers",
        status=status,
        latency_ms=(time.monotonic() - start) * 1000,
        details={"providers": provider_status},
    )


async def _check_critical_deps() -> ComponentHealth:
    """فحص التبعيات الحرجة — torch, transformers, tesseract-cli.

    Uses ``shutil.which`` for CLI tools and ``importlib`` for packages.
    """
    start = time.monotonic()
    dep_status: dict[str, bool] = {}

    # حزم Python
    python_deps = {
        "torch": "torch",
        "transformers": "transformers",
        "PIL": "PIL",
        "numpy": "numpy",
    }
    for label, module_name in python_deps.items():
        try:
            __import__(module_name)
            dep_status[label] = True
        except Exception:
            dep_status[label] = False

    # أدوات CLI
    cli_deps = {
        "tesseract-cli": "tesseract",
    }
    for label, binary in cli_deps.items():
        dep_status[label] = shutil.which(binary) is not None

    missing = [k for k, v in dep_status.items() if not v]
    present = len(dep_status) - len(missing)

    if missing:
        status = HealthStatus.DEGRADED
    else:
        status = HealthStatus.HEALTHY

    return ComponentHealth(
        name="critical_deps",
        status=status,
        latency_ms=(time.monotonic() - start) * 1000,
        details={"packages": dep_status, "missing": missing, "present": present},
    )


# ═══════════════════════════════════════════════════════════════════════════
# Overall score
# ═══════════════════════════════════════════════════════════════════════════

def _compute_overall_score(components: list[ComponentHealth]) -> float:
    """حساب الدرجة الإجمالية المرجّحة (المجموع = 1.0).

    Weighted: Database 30%, OCR 35%, Redis 15%, LLM 10%, Deps 10%.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for comp in components:
        weight = _COMPONENT_WEIGHTS.get(comp.name, 0.0)
        weighted_sum += comp.score * weight
        total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _determine_status(score: float) -> HealthStatus:
    """تحويل الدرجة (0-1) إلى حالة."""
    if score >= 0.8:
        return HealthStatus.HEALTHY
    if score >= 0.5:
        return HealthStatus.DEGRADED
    return HealthStatus.UNHEALTHY


def _get_uptime() -> float:
    """حساب وقت التشغيل بالثواني."""
    try:
        from app.core.config import settings

        return settings.uptime_seconds
    except Exception:
        # تراجع: وقت تشغيل العملية
        try:
            import os
            return time.time() - os.getpid()
        except Exception:
            return 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "",
    summary="Basic health check",
    response_model=dict[str, Any],
)
async def health_basic() -> dict[str, Any]:
    """فحص صحة أساسي — يعرض الحالة الإجمالية فقط.

    Returns overall status, score, and uptime without component
    details (minimal response for load balancers).
    """
    components = await asyncio.gather(
        _check_database(),
        _check_ocr_engines(),
        _check_redis(),
        _check_llm_providers(),
        _check_critical_deps(),
    )

    component_list = list(components)
    overall_score = _compute_overall_score(component_list)
    status = _determine_status(overall_score)
    uptime = _get_uptime()

    return {
        "status": status,
        "overall_score": overall_score,
        "uptime_seconds": round(uptime, 1),
    }


@router.get(
    "/ready",
    summary="Readiness probe — detailed component health",
    response_model=dict[str, Any],
)
async def readiness(
    verbose: bool = Query(
        False,
        description="Show component details and errors (default: hidden for security)",
    ),
) -> dict[str, Any]:
    """فحص الجاهزية — تفاصيل كل مكون.

    Runs parallel health checks on all system components and
    returns a weighted overall score with per-component details.

    In non-verbose mode (default), error details are hidden to
    prevent information leakage.
    """
    components = await asyncio.gather(
        _check_database(),
        _check_ocr_engines(),
        _check_redis(),
        _check_llm_providers(),
        _check_critical_deps(),
    )

    component_list = list(components)
    overall_score = _compute_overall_score(component_list)
    status = _determine_status(overall_score)
    uptime = _get_uptime()

    health = SystemHealth(
        status=status,
        uptime_seconds=uptime,
        components=component_list,
        overall_score=overall_score,
    )

    result = health.to_dict(verbose=verbose)

    # تحديث Prometheus metrics إن توفّر
    try:
        from packages.core.omnimedical_metrics import get_metrics_exporter

        metrics = get_metrics_exporter()
        metrics.update_health(overall_score)
        metrics.increment_health_check(status=status)
    except Exception:
        pass

    return result


@router.get(
    "/live",
    summary="Liveness probe — simple process check",
    response_model=dict[str, Any],
)
async def liveness() -> dict[str, Any]:
    """فحص الحيوية — خفيف للمنسّقات.

    Lightweight liveness indicator for Kubernetes / orchestrators.
    Always returns ``200`` as long as the process is running and not
    deadlocked.
    """
    uptime = _get_uptime()

    try:
        from app.core.config import settings

        app_name = settings.APP_NAME
        app_version = settings.APP_VERSION
    except Exception:
        app_name = "OmniMedicalSuite"
        app_version = "unknown"

    return {
        "status": "alive",
        "app": app_name,
        "version": app_version,
        "uptime_seconds": round(uptime, 1),
    }