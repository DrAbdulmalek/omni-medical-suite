"""OmniMedicalSuite API – FastAPI application entry-point.

Wires together CORS, authentication middleware, routers, lifespan events
(startup / shutdown), and global exception handlers into a single
production-ready ASGI application.

Run with::

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import sys
import time
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import verify_api_key

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("omni.app")

# ── Stubs for routers that will be implemented in separate modules ────────
# These imports are wrapped in try/except so the application starts even if
# the router modules have not been created yet.
_RouterClasses: list[Any] = []


def _try_import_router(module_path: str, router_var: str) -> Any:
    """Attempt to import a router; return ``None`` on failure."""
    try:
        mod = __import__(module_path, fromlist=[router_var])
        return getattr(mod, router_var, None)
    except Exception as exc:
        logger.debug("Router '%s' not available: %s", module_path, exc)
        return None


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle.

    Startup tasks:
    1. Initialise the database connection.
    2. Optionally connect to Redis.
    3. Register OCR engines.
    4. Log a startup banner with system information.

    Shutdown tasks:
    1. Close Redis connection.
    2. Close database connection.
    """
    # ── Startup ──────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  %s v%s  –  Starting up", settings.APP_NAME, settings.APP_VERSION)
    logger.info("=" * 60)

    # 1. Database
    try:
        from app.services.prisma_client import init_db

        await init_db()
        logger.info("[startup] Database initialised successfully.")
    except Exception as exc:
        logger.error("[startup] Database initialisation failed: %s", exc)

    # 2. Redis (optional)
    try:
        from app.services.redis_client import init_redis

        await init_redis()
    except Exception as exc:
        logger.warning("[startup] Redis initialisation skipped: %s", exc)

    # 3. OCR engine registration
    _register_ocr_engines()

    # 4. Warm up connections
    _warm_connections()

    # 5. Startup banner
    _print_banner()

    logger.info("[startup] Application is ready to serve requests.")
    yield  # ── Application is running ──

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("[shutdown] Shutting down application …")

    try:
        from app.services.redis_client import close_redis

        await close_redis()
    except Exception:
        pass

    try:
        from app.services.prisma_client import close_db

        await close_db()
    except Exception:
        pass

    logger.info("[shutdown] Application stopped.")


# ---------------------------------------------------------------------------
# Custom OpenAPI schema
# ---------------------------------------------------------------------------
def custom_openapi():
    """Customize the OpenAPI schema with security schemes and Arabic description."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="OmniMedical Suite API",
        version="2.0.0",
        description=(
            "تدعم OCR متعدد المحركات، استخراج معلومات طبية، FHIR، والتحقق الطبي بالذكاء الاصطناعي\n\n"
            "Multi-engine OCR, medical information extraction, FHIR support, "
            "and AI-powered medical validation."
        ),
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# ---------------------------------------------------------------------------
# FastAPI instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="OmniMedicalSuite API",
    description=(
        "Production-grade API for medical document OCR, semantic analysis, "
        "entity extraction, and intelligent document processing."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.openapi = custom_openapi


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API key validation middleware (optional – only active when API_KEY is set)
@app.middleware("http")
async def api_key_middleware(request: Request, call_next: Any) -> Response:
    """Validate the ``Authorization: Bearer <API_KEY>`` header.

    Paths prefixed with ``/health``, ``/docs``, ``/redoc``, ``/openapi.json``,
    and ``/favicon`` are exempt from authentication.
    """
    exempt_prefixes = ("/health", "/docs", "/redoc", "/openapi.json", "/favicon")

    if any(request.url.path.startswith(prefix) for prefix in exempt_prefixes):
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid Authorization header. Expected: Bearer <API_KEY>."},
        )

    token = auth_header.removeprefix("Bearer ").strip()
    if not verify_api_key(token, settings.API_KEY):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key."},
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return 422 with structured validation error details."""
    errors = exc.errors()
    logger.warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        errors,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed.", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all handler that logs full traceback and returns 500."""
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred."},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Any) -> JSONResponse:
    """Return 404 for unknown routes."""
    return JSONResponse(
        status_code=404,
        content={"detail": f"Resource not found: {request.url.path}"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
# Health (always available)
from app.api.endpoints.health import router as health_router  # noqa: E402, WPS433

app.include_router(health_router)

# Documents (placeholder – import actual router when available)
_documents_router = _try_import_router("app.api.endpoints.documents", "router")
if _documents_router is not None:
    app.include_router(_documents_router)
else:
    logger.info("Documents router not loaded – module not yet implemented.")

# Tasks (placeholder)
_tasks_router = _try_import_router("app.api.endpoints.tasks", "router")
if _tasks_router is not None:
    app.include_router(_tasks_router)
else:
    logger.info("Tasks router not loaded – module not yet implemented.")

# OCR (placeholder)
_ocr_router = _try_import_router("app.api.endpoints.ocr", "router")
if _ocr_router is not None:
    app.include_router(_ocr_router)
else:
    logger.info("OCR router not loaded – module not yet implemented.")


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------
def _register_ocr_engines() -> None:
    """Pre-register available OCR engines and log status."""
    engines_available: dict[str, bool] = {}

    for engine_name in settings.OCR_ENGINE_PRIORITY:
        try:
            match engine_name:
                case "tesseract":
                    import pytesseract  # type: ignore[import-untyped]

                    pytesseract.get_tesseract_version()
                    engines_available[engine_name] = True
                case "easyocr":
                    import easyocr  # type: ignore[import-untyped]

                    engines_available[engine_name] = True
                case "paddleocr":
                    import paddleocr  # type: ignore[import-untyped]

                    engines_available[engine_name] = True
                case _:
                    engines_available[engine_name] = False
                    logger.info("[ocr] Engine '%s' not yet supported.", engine_name)
        except Exception as exc:
            engines_available[engine_name] = False
            logger.warning("[ocr] Engine '%s' unavailable: %s", engine_name, exc)

    available_count = sum(1 for v in engines_available.values() if v)
    logger.info(
        "[ocr] %d / %d engines ready: %s",
        available_count,
        len(engines_available),
        engines_available,
    )


def _warm_connections() -> None:
    """Warm up HTTP client pools and other lazy connections."""
    t0 = time.monotonic()
    try:
        import httpx  # type: ignore[import-untyped]

        with httpx.Client() as client:
            client.get("https://httpbin.org/get", timeout=2.0)
    except Exception:
        pass  # Non-critical – best-effort
    logger.info("[startup] Connection warm-up completed in %.1f ms", (time.monotonic() - t0) * 1000)


def _print_banner() -> None:
    """Log a formatted startup banner with system information."""
    try:
        from app.system.resource_monitor import get_system_resources, format_resources

        resources = format_resources(get_system_resources())
        gpu_info = "N/A"
        if resources.get("gpu_available"):
            gpu_info = f"{resources.get('gpu_name', 'unknown')} ({resources.get('gpu_memory_mb', '?')} MB)"

        logger.info("┌─────────────────────────────────────────────────────┐")
        logger.info("│  OmniMedicalSuite API   v%s                 │", settings.APP_VERSION)
        logger.info("├─────────────────────────────────────────────────────┤")
        logger.info("│  CPU:          %5.1f %%                             │", resources.get("cpu_percent", 0))
        logger.info("│  Memory:       %5.1f %% (%.1f / %.1f GB)     │",
                     resources.get("memory_percent", 0),
                     resources.get("memory_used_gb", 0),
                     resources.get("memory_total_gb", 0))
        logger.info("│  Disk:         %.1f / %.1f GB                   │",
                     resources.get("disk_used_gb", 0),
                     resources.get("disk_total_gb", 0))
        logger.info("│  GPU:          %-36s │", gpu_info)
        logger.info("│  Internet:     %-36s │",
                     "Yes" if resources.get("internet_available") else "No")
        logger.info("│  Log level:    %-36s │", settings.LOG_LEVEL)
        logger.info("└─────────────────────────────────────────────────────┘")
    except Exception as exc:
        logger.info("Startup banner skipped (resource monitor unavailable): %s", exc)
