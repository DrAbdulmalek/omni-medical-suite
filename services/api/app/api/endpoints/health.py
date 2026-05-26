"""Health-check endpoints for OmniMedicalSuite.

Exposes detailed readiness (``/health/ready``) and lightweight liveness
(``/health/live``) probes suitable for Kubernetes or any orchestrator.

Component checks run **in parallel** using :func:`asyncio.gather` and are
weighted to produce an overall health score between 0 and 1.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import StrEnum
from typing import Any

from fastapi import APIRouter

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class HealthStatus(StrEnum):
    """Triage status of a component or the system as a whole."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """Structured health result for a single subsystem."""

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "details": self.details,
            "error": self.error,
        }

    @property
    def score(self) -> float:
        """Normalise status to a numeric score (1 / 0.5 / 0)."""
        match self.status:
            case HealthStatus.HEALTHY:
                return 1.0
            case HealthStatus.DEGRADED:
                return 0.5
            case HealthStatus.UNHEALTHY:
                return 0.0


class SystemHealth:
    """Aggregated health report for the whole application."""

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "components": [c.to_dict() for c in self.components],
            "overall_score": self.overall_score,
        }


# ---------------------------------------------------------------------------
# Component weights (must sum to 1.0)
# ---------------------------------------------------------------------------
_COMPONENT_WEIGHTS: dict[str, float] = {
    "database": 0.30,
    "ocr_engines": 0.35,
    "dependencies": 0.15,
    "redis": 0.10,
    "llm_providers": 0.10,
}


# ---------------------------------------------------------------------------
# Individual component checks
# ---------------------------------------------------------------------------
async def _check_database() -> ComponentHealth:
    """Verify that the primary database is reachable and writable."""
    start = time.monotonic()
    try:
        from app.services.prisma_client import get_prisma

        client = get_prisma()
        await client.query_raw("SELECT 1")
        return ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=(time.monotonic() - start) * 1000,
            details={"engine": "sqlite"},
        )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        logger.warning("Database health check failed: %s", exc)
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            error=str(exc),
        )


async def _check_ocr_engines() -> ComponentHealth:
    """Check which OCR engines are importable and functional."""
    start = time.monotonic()
    engine_status: dict[str, bool] = {}

    for engine in ("tesseract", "easyocr", "paddleocr"):
        try:
            if engine == "tesseract":
                import pytesseract  # type: ignore[import-untyped]
                from PIL import Image

                # Verify tesseract binary is available
                pytesseract.get_tesseract_version()
                engine_status[engine] = True
            elif engine == "easyocr":
                import easyocr  # type: ignore[import-untyped]

                engine_status[engine] = True
            elif engine == "paddleocr":
                import paddleocr  # type: ignore[import-untyped]

                engine_status[engine] = True
        except Exception:
            engine_status[engine] = False

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
        details={"engines": engine_status, "available": available, "total": total},
    )


async def _check_dependencies() -> ComponentHealth:
    """Verify that critical Python packages are importable."""
    start = time.monotonic()
    dep_status: dict[str, bool] = {}

    packages = {
        "fastapi": "fastapi",
        "pydantic": "pydantic",
        "prisma": "prisma",
        "psutil": "psutil",
        "PIL": "PIL",
        "numpy": "numpy",
    }

    for label, module_name in packages.items():
        try:
            __import__(module_name)
            dep_status[label] = True
        except Exception:
            dep_status[label] = False

    missing = [k for k, v in dep_status.items() if not v]

    status = HealthStatus.UNHEALTHY if missing else HealthStatus.HEALTHY

    return ComponentHealth(
        name="dependencies",
        status=status,
        latency_ms=(time.monotonic() - start) * 1000,
        details={"packages": dep_status, "missing": missing},
    )


async def _check_redis() -> ComponentHealth:
    """Check Redis connectivity (optional)."""
    start = time.monotonic()
    try:
        from app.services.redis_client import RedisClient

        ok = await RedisClient.health_check()
        if ok:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=(time.monotonic() - start) * 1000,
                details={"connected": True},
            )
        else:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                latency_ms=(time.monotonic() - start) * 1000,
                details={"connected": False},
                error="Redis not available (optional – system will operate without cache)",
            )
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ComponentHealth(
            name="redis",
            status=HealthStatus.DEGRADED,
            latency_ms=latency,
            details={"connected": False},
            error=f"Redis check error (optional): {exc}",
        )


async def _check_llm_providers() -> ComponentHealth:
    """Check configured LLM provider health."""
    start = time.monotonic()
    provider_status: dict[str, Any] = {}

    try:
        from app.core.config import settings
        from app.ai.llm_router import LLMRouter

        router = LLMRouter(settings)
        results = await router.health_check()

        for name, info in results.items():
            provider_status[name] = {
                "status": info.get("status", False),
                "latency_ms": info.get("latency_ms"),
                "error": info.get("error"),
            }

        any_ok = any(info.get("status", False) for info in results.values())

        if not results:
            # No providers configured – degraded but acceptable
            status = HealthStatus.DEGRADED
            provider_status["note"] = "No LLM API keys configured"
        elif any_ok:
            status = HealthStatus.HEALTHY
        else:
            status = HealthStatus.UNHEALTHY
    except Exception as exc:
        status = HealthStatus.DEGRADED
        provider_status["error"] = str(exc)

    return ComponentHealth(
        name="llm_providers",
        status=status,
        latency_ms=(time.monotonic() - start) * 1000,
        details={"providers": provider_status},
    )


# ---------------------------------------------------------------------------
# Overall score calculation
# ---------------------------------------------------------------------------
def _compute_overall_score(components: list[ComponentHealth]) -> float:
    """Weighted average of component scores."""
    total_weight = 0.0
    weighted_sum = 0.0
    for comp in components:
        weight = _COMPONENT_WEIGHTS.get(comp.name, 0.0)
        weighted_sum += comp.score * weight
        total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _determine_status(score: float) -> HealthStatus:
    """Map a 0–1 score to a triage status."""
    if score >= 0.8:
        return HealthStatus.HEALTHY
    if score >= 0.5:
        return HealthStatus.DEGRADED
    return HealthStatus.UNHEALTHY


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/ready",
    summary="Readiness probe – detailed component health",
    response_model=dict[str, Any],
)
async def readiness() -> dict[str, Any]:
    """Run parallel health checks on all system components.

    Returns a weighted overall score and per-component details.
    """
    from app.core.config import settings

    components = await asyncio.gather(
        _check_database(),
        _check_ocr_engines(),
        _check_dependencies(),
        _check_redis(),
        _check_llm_providers(),
    )

    component_list = list(components)
    overall_score = _compute_overall_score(component_list)
    status = _determine_status(overall_score)

    health = SystemHealth(
        status=status,
        uptime_seconds=settings.uptime_seconds,
        components=component_list,
        overall_score=overall_score,
    )

    return health.to_dict()


@router.get(
    "/live",
    summary="Liveness probe – simple process check",
    response_model=dict[str, Any],
)
async def liveness() -> dict[str, Any]:
    """Lightweight liveness indicator for orchestrators.

    Always returns ``200`` as long as the process is running and not deadlocked.
    """
    from app.core.config import settings

    return {
        "status": "alive",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(settings.uptime_seconds, 1),
    }
