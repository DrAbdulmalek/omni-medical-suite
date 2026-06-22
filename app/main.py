"""
OmniMedical Suite v2.0 — FastAPI Application Entry Point.
Arabic/English Medical OCR with Fusion, Semantic Dedup, and Knowledge Graph.
"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.telemetry import init_telemetry
from app.core.database import engine, Base
from app.routers import health, ocr, documents

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize OpenTelemetry
    init_telemetry()
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")
    
    yield
    
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Arabic/English Medical OCR System with Fusion, Semantic Dedup, and Knowledge Graph",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Register routers
app.include_router(health.router)
app.include_router(ocr.router)
app.include_router(documents.router)


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
