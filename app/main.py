# app/main.py - Omni Medical Suite FastAPI Application
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_app_config, get_security_config

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get configurations (with defaults to avoid validation errors on first run)
try:
    app_config = get_app_config()
    security_config = get_security_config()
except Exception as e:
    logger.warning(f"Config validation warning (using defaults): {e}")
    app_config = get_app_config()
    security_config = get_security_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Omni Medical Suite v2.0.0...")

    # Database initialization is deferred to first request
    # (PostgreSQL may not be available in all environments)
    logger.info("Database initialization deferred (connects on first request)")

    yield

    # Shutdown
    logger.info("Shutting down Omni Medical Suite...")
    try:
        from app.db.session import close_db
        await close_db()
    except Exception:
        pass
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Omni Medical Suite API",
    description="Comprehensive Medical OCR and Text Processing Platform",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.CORS_ALLOW_ORIGINS,
    allow_credentials=security_config.CORS_ALLOW_CREDENTIALS,
    allow_methods=security_config.CORS_ALLOW_METHODS,
    allow_headers=security_config.CORS_ALLOW_HEADERS,
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    if security_config.ENABLE_SECURITY_HEADERS:
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Include routers
from app.routers.auth import router as auth_router

app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])

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

# Try to include package routers (optional, may not exist)
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


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check_endpoint():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": app_config.APP_VERSION,
        "environment": app_config.ENVIRONMENT
    }


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "name": "Omni Medical Suite",
        "version": app_config.APP_VERSION,
        "description": "Comprehensive Medical OCR and Text Processing Platform",
        "docs": "/api/docs",
        "health": "/health"
    }


# Error handlers
@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Handle generic errors"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_config.HOST,
        port=app_config.PORT,
        reload=app_config.DEBUG,
        workers=1 if app_config.DEBUG else app_config.WORKERS
    )
