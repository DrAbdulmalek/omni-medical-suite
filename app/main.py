# app/main.py - Omni Medical Suite FastAPI Application
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_app_config, get_security_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app_config = get_app_config()
security_config = get_security_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage resources at application startup/shutdown."""
    logger.info("Starting Omni Medical Suite %s (%s)", app_config.APP_VERSION, app_config.ENVIRONMENT)

    if app_config.ENVIRONMENT in {"production", "staging"}:
        from app.db.session import init_db
        init_db()
        logger.info("Database engine initialized during startup")

    yield

    logger.info("Shutting down Omni Medical Suite")
    from app.db.session import close_db
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Omni Medical Suite API",
    description="Comprehensive Medical OCR and Text Processing Platform",
    version=app_config.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.CORS_ALLOW_ORIGINS,
    allow_credentials=security_config.CORS_ALLOW_CREDENTIALS,
    allow_methods=security_config.CORS_ALLOW_METHODS,
    allow_headers=security_config.CORS_ALLOW_HEADERS,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    if security_config.ENABLE_SECURITY_HEADERS:
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


from app.routers.auth import router as auth_router
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])

from app.routers.session_auth import limiter as auth_limiter
from app.routers.session_auth import router as session_auth_router
app.state.limiter = auth_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(session_auth_router, prefix="/api/auth", tags=["authentication"])

from app.routers.pipeline import router as pipeline_router
app.include_router(pipeline_router, prefix="/api/pipeline", tags=["pipeline"])

from app.routers.ocr import router as ocr_router
app.include_router(ocr_router, prefix="/api/ocr", tags=["ocr"])

from app.routers.jobs import router as jobs_router
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])

from app.routers.datasets import router as datasets_router
app.include_router(datasets_router, prefix="/api/datasets", tags=["datasets"])

from app.routers.models import router as models_router
app.include_router(models_router, prefix="/api/models", tags=["models"])

from app.routers.admin import router as admin_router
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

try:
    from app.packages.scanner_fixer.routers import scanner_fixer
    app.include_router(scanner_fixer.router, prefix="/api/scanner-fixer", tags=["scanner-fixer"])
except ImportError:
    logger.debug("Scanner-fixer package router not available")

try:
    from app.packages.benchmark_core.routers import benchmarks
    app.include_router(benchmarks.router, prefix="/api/benchmarks", tags=["benchmarks"])
except ImportError:
    logger.debug("Benchmark package router not available")

try:
    from app.packages.training_hub.routers import training
    app.include_router(training.router, prefix="/api/training", tags=["training"])
except ImportError:
    logger.debug("Training hub package router not available")

try:
    from src.api.server import router as core_api_router
    app.include_router(core_api_router, prefix="/api", tags=["core-engines"])
    logger.info("Core-engine API router mounted at /api")
except ImportError as exc:
    logger.warning("Core-engine API router not available: %s", exc)


@app.get("/health", tags=["health"])
async def health_check_endpoint():
    """Liveness probe: confirms the process is running."""
    return {"status": "healthy", "version": app_config.APP_VERSION, "environment": app_config.ENVIRONMENT}


@app.get("/ready", tags=["health"])
async def readiness_check_endpoint():
    """Readiness probe: checks required runtime dependencies."""
    from app.db.session import health_check

    database_ok = await health_check()
    if not database_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": {"database": "unavailable"}},
        )
    return {"status": "ready", "checks": {"database": "ok"}}


@app.get("/", tags=["root"])
async def root():
    return {
        "name": "Omni Medical Suite",
        "version": app_config.APP_VERSION,
        "description": "Comprehensive Medical OCR and Text Processing Platform",
        "docs": "/api/docs",
        "health": "/health",
        "readiness": "/ready",
    }


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error("Unexpected error: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_config.HOST,
        port=app_config.PORT,
        reload=app_config.DEBUG,
        workers=1 if app_config.DEBUG else app_config.WORKERS,
    )
