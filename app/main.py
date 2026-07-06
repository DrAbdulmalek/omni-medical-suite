# app/main.py - Updated with RBAC middleware
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.config import get_app_config, get_security_config, validate_config
from app.db.session import init_db, close_db, get_db
from app.core.rbac import RBACMiddleware, create_default_admin
from app.routers import auth, pipeline, ocr, jobs, datasets, models, admin
from app.packages.scanner_fixer.routers import scanner_fixer
from app.packages.benchmark_core.routers import benchmarks
from app.packages.training_hub.routers import training

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate configuration on startup
validate_config()

# Get configurations
app_config = get_app_config()
security_config = get_security_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("🚀 Starting Omni Medical Suite...")

    # Initialize database
    init_db()
    logger.info("✅ Database initialized")

    # Create default admin if not exists
    try:
        async with async_scoped_session(AsyncSessionLocal) as db:
            await create_default_admin(db)
            logger.info("✅ Default admin user checked/created")
    except Exception as e:
        logger.error(f"❌ Failed to create default admin: {e}")

    # Validate database connection
    try:
        async with async_scoped_session(AsyncSessionLocal) as db:
            await health_check(db)
            logger.info("✅ Database connection healthy")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down Omni Medical Suite...")
    await close_db()
    logger.info("✅ Database connections closed")

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

# Add RBAC middleware
app.add_middleware(RBACMiddleware)

# Add CORS middleware with security config
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.CORS_ALLOW_ORIGINS,
    allow_credentials=security_config.CORS_ALLOW_CREDENTIALS,
    allow_methods=security_config.CORS_ALLOW_METHODS,
    allow_headers=security_config.CORS_ALLOW_HEADERS,
)

# Add Trusted Host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=security_config.CORS_ALLOW_ORIGINS
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    if security_config.ENABLE_SECURITY_HEADERS:
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self';"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(ocr.router, prefix="/api/ocr", tags=["ocr"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(scanner_fixer.router, prefix="/api/scanner-fixer", tags=["scanner-fixer"])
app.include_router(benchmarks.router, prefix="/api/benchmarks", tags=["benchmarks"])
app.include_router(training.router, prefix="/api/training", tags=["training"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check_endpoint():
    """Health check endpoint"""
    try:
        async with async_scoped_session(AsyncSessionLocal) as db:
            db_health = await health_check(db)
        return {
            "status": "healthy",
            "database": "healthy" if db_health else "unhealthy",
            "version": app_config.APP_VERSION,
            "environment": app_config.ENVIRONMENT
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "version": app_config.APP_VERSION,
                "environment": app_config.ENVIRONMENT
            }
        )

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
@app.exception_handler(RBACError)
async def rbac_error_handler(request: Request, exc: RBACError):
    """Handle RBAC errors"""
    logger.warning(f"RBAC Error: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

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
        workers=app_config.WORKERS
    )