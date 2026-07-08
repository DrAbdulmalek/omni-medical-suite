"""
Health check endpoints for monitoring system status.

Provides liveness, readiness, and full health probes compatible with
Kubernetes/Docker health checks and Prometheus alerting.
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


async def check_database() -> Dict[str, Any]:
    """Check PostgreSQL database connectivity."""
    try:
        import asyncpg
        import os

        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "5432"))
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        dbname = os.getenv("DB_NAME", "omni_medical")

        conn = await asyncio.wait_for(
            asyncpg.connect(
                host=host, port=port, user=user, password=password, dbname=dbname
            ),
            timeout=5.0,
        )
        await conn.execute("SELECT 1")
        await conn.close()
        return {"database": "healthy", "status": "ok"}
    except ImportError:
        # asyncpg not installed — skip gracefully
        return {"database": "skipped", "status": "ok", "reason": "asyncpg not installed"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"database": "unhealthy", "status": "error", "error": str(e)}


async def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(url)
        client.ping()
        client.close()
        return {"redis": "healthy", "status": "ok"}
    except ImportError:
        return {"redis": "skipped", "status": "ok", "reason": "redis not installed"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"redis": "unhealthy", "status": "error", "error": str(e)}


async def check_qdrant() -> Dict[str, Any]:
    """Check Qdrant vector database connectivity."""
    try:
        from qdrant_client import QdrantClient
        import os

        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        client = QdrantClient(url=url)
        client.get_collections()
        return {"qdrant": "healthy", "status": "ok"}
    except ImportError:
        return {"qdrant": "skipped", "status": "ok", "reason": "qdrant-client not installed"}
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return {"qdrant": "unhealthy", "status": "error", "error": str(e)}


@router.get("/", summary="Full health check")
async def full_health_check() -> JSONResponse:
    """Comprehensive health check for all services.

    Runs checks against database, Redis, and Qdrant in parallel.
    Returns 'healthy' if all critical services are up, 'degraded' otherwise.
    """
    checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_qdrant(),
    )

    all_healthy = all(
        check.get("status") in ("ok", "skipped") for check in checks
    )
    status = "healthy" if all_healthy else "degraded"

    result = {
        "status": status,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(content=result)


@router.get("/liveness")
async def liveness_check() -> JSONResponse:
    """Simple liveness probe — confirms the process is running."""
    return JSONResponse(content={"status": "alive"})


@router.get("/readiness")
async def readiness_check() -> JSONResponse:
    """Readiness probe — checks critical dependencies before serving traffic."""
    db_check = await check_database()
    redis_check = await check_redis()

    db_ok = db_check.get("status") in ("ok", "skipped")
    redis_ok = redis_check.get("status") in ("ok", "skipped")

    if db_ok and redis_ok:
        return JSONResponse(content={"status": "ready"})
    else:
        return JSONResponse(
            content={
                "status": "not_ready",
                "checks": {"database": db_check, "redis": redis_check},
            },
            status_code=503,
        )