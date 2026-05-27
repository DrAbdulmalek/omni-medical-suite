"""
Health check endpoints for Kubernetes probes and monitoring.
"""
import time
from fastapi import APIRouter, Depends
from app.schemas.ocr import HealthResponse
from app.core.config import settings

router = APIRouter()

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe — returns 200 if the API process is running."""
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        uptime_seconds=round(time.time() - _start_time, 2),
        components={"api": "running"},
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness probe — returns 200 only when all dependencies are reachable.
    Used by Kubernetes to route traffic to ready pods.
    """
    components = {"api": "running"}
    
    # Check database connectivity
    try:
        from app.core.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        components["database"] = "connected"
    except Exception:
        components["database"] = "unreachable"
    
    # Check Redis connectivity
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        components["redis"] = "connected"
    except Exception:
        components["redis"] = "unreachable"
    
    # Check Qdrant connectivity
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(url=settings.QDRANT_URL)
        qc.list_collections()
        components["qdrant"] = "connected"
    except Exception:
        components["qdrant"] = "unreachable"
    
    all_ok = all(v == "connected" or v == "running" for v in components.values())
    
    return HealthResponse(
        status="ready" if all_ok else "degraded",
        version=settings.APP_VERSION,
        uptime_seconds=round(time.time() - _start_time, 2),
        components=components,
    )
