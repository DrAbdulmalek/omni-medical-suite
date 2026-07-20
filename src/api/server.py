"""
FastAPI REST API server — wraps Omni Medical Suite core engines.

Endpoints:
  POST /api/classify   — classify medical text using MedicalClassifier
  POST /api/organize   — organize files into category folders
  GET  /api/search     — semantic search via Qdrant / local-fuzzy fallback
  GET  /api/stats      — categories + engine availability
  GET  /api/health     — lightweight health probe (Ollama, Qdrant, PaddleOCR, Tesseract)

All engine imports are lazy — the server starts instantly and gracefully
degrades when optional dependencies are unavailable.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path sandboxing — security: only allow paths under configured directories
# ---------------------------------------------------------------------------

# Comma-separated list of allowed base directories (env: OMNI_ALLOWED_DIRS)
# Default: current working directory + data/ dir
_ALLOWED_DIRS: list[Path] | None = None

def _get_allowed_dirs() -> list[Path]:
    """Get and cache the list of allowed directories."""
    global _ALLOWED_DIRS
    if _ALLOWED_DIRS is not None:
        return _ALLOWED_DIRS
    dirs_str = os.environ.get(
        "OMNI_ALLOWED_DIRS",
        os.path.join(os.getcwd(), "data"),
    )
    _ALLOWED_DIRS = [
        Path(d.strip()).resolve()
        for d in dirs_str.split(",")
        if d.strip()
    ]
    # Always allow cwd
    _ALLOWED_DIRS.append(Path.cwd().resolve())
    return _ALLOWED_DIRS


def _validate_path(path_str: str, must_exist: bool = True) -> Path:
    """Validate that a path is within allowed directories (sandboxing).

    Raises HTTPException(403) if the path escapes the sandbox.
    """
    resolved = Path(path_str).resolve()
    allowed = _get_allowed_dirs()
    if not any(resolved.is_relative_to(allowed_dir) for allowed_dir in allowed):
        raise HTTPException(
            status_code=403,
            detail="Path is outside allowed directories",
        )
    if must_exist and not resolved.exists():
        raise HTTPException(status_code=400, detail=f"Path not found: {resolved}")
    return resolved


# Safe category names for organize endpoint (prevent path traversal via category)
_SAFE_CATEGORY_RE = re.compile(r"^[a-zA-Z0-9_\-\u0600-\u06FF]+$")


def _sanitize_category(category: str) -> str:
    """Sanitize a classifier category for use as a directory name."""
    if not _SAFE_CATEGORY_RE.match(category):
        return "general"
    return category


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Medical text to classify")
    min_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Minimum confidence threshold")

class ClassifyResponse(BaseModel):
    category: str
    confidence: float
    all_scores: dict[str, float] = Field(default_factory=dict)

class OrganizeRequest(BaseModel):
    source_dir: str = Field(..., description="Directory containing files to organize")
    target_dir: str = Field("", description="Target directory (defaults to source_dir)")
    dry_run: bool = Field(True, description="Preview only — do not move files")
    move_files: bool = Field(False, description="Move files instead of copying")

class OrganizeResponse(BaseModel):
    organized: dict[str, list[str]] = Field(default_factory=dict)
    dry_run: bool = True
    total_files: int = 0
    errors: list[str] = Field(default_factory=list)

class SearchResponse(BaseModel):
    query: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    engine: str = "unavailable"
    total: int = 0

class StatsResponse(BaseModel):
    categories: list[str] = Field(default_factory=list)
    engines: dict[str, bool] = Field(default_factory=dict)

class HealthResponse(BaseModel):
    status: str = "ok"
    ollama_available: bool = False
    qdrant_available: bool = False
    paddleocr_available: bool = False
    tesseract_available: bool = False
    version: str = "2.0.0"


# ---------------------------------------------------------------------------
# Minimal fallback classifier (when full MedicalClassifier is unavailable)
# ---------------------------------------------------------------------------

class _MinimalClassifier:
    """Lightweight keyword-based classifier used when the full engine cannot load."""

    _KEYWORDS: dict[str, list[str]] = {
        "orthopedic": ["كسر", "fracture", "عظم", "bone", "مفصل", "joint"],
        "cardiology": ["قلب", "heart", "cardiac", "شرايين", "artery"],
        "neurology": ["دماغ", "brain", "عصبي", "neuro", "صرع", "epilepsy"],
        "radiology": ["أشعة", "radiology", "تصوير", "imaging", "x-ray", "ct", "mri"],
        "pathology": ["أنسجة", "pathology", "خزعة", "biopsy"],
        "pharmacology": ["دواء", "drug", "medication", "وصفة", "prescription"],
        "research": ["بحث", "research", "دراسة", "study"],
        "medical_admin": ["تقرير", "report", "ملف", "file", "مريض", "patient"],
        "general": [],
    }

    def classify(self, text: str) -> dict[str, Any]:
        text_lower = text.lower()
        scores: dict[str, float] = {}
        for cat, keywords in self._KEYWORDS.items():
            if not keywords:
                scores[cat] = 0.05
                continue
            match_count = sum(1 for kw in keywords if kw.lower() in text_lower)
            scores[cat] = min(match_count / max(len(keywords), 1), 1.0)

        best_cat = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_cat]

        # If no keyword matched, default to "general"
        if best_score <= 0.05:
            best_cat = "general"
            best_score = 0.1

        return {
            "category": best_cat,
            "confidence": round(best_score, 3),
            "all_scores": {k: round(v, 3) for k, v in scores.items()},
        }


# ---------------------------------------------------------------------------
# Lazy-singleton engine accessors
# ---------------------------------------------------------------------------

_classifier: Optional[Any] = None
_classifier_type: str = "none"
_search_model: Optional[Any] = None
_qdrant_client: Optional[Any] = None


def _get_classifier() -> tuple[Any, str]:
    """Return (classifier_instance, type_label) with three fallback paths."""
    global _classifier, _classifier_type
    if _classifier is not None:
        return _classifier, _classifier_type

    # Path 1: hf-space packages
    try:
        from hf_space.packages.core.classifier import MedicalClassifier
        _classifier = MedicalClassifier()
        _classifier_type = "MedicalClassifier (hf-space)"
        logger.info("Loaded MedicalClassifier from hf-space.packages.core")
        return _classifier, _classifier_type
    except Exception as exc:
        logger.debug("hf-space classifier unavailable: %s", exc)

    # Path 2: packages core
    try:
        from packages.core.classifier import MedicalClassifier
        _classifier = MedicalClassifier()
        _classifier_type = "MedicalClassifier (packages)"
        logger.info("Loaded MedicalClassifier from packages.core")
        return _classifier, _classifier_type
    except Exception as exc:
        logger.debug("packages.core classifier unavailable: %s", exc)

    # Path 3: minimal fallback
    _classifier = _MinimalClassifier()
    _classifier_type = "_MinimalClassifier (fallback)"
    logger.warning("Full classifier unavailable — using _MinimalClassifier fallback")
    return _classifier, _classifier_type


def _get_search_model():
    """Lazily load and cache the SentenceTransformer model."""
    global _search_model
    if _search_model is not None:
        return _search_model
    try:
        from sentence_transformers import SentenceTransformer
        _search_model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        logger.info("Loaded SentenceTransformer search model")
    except Exception as exc:
        logger.warning("SentenceTransformer unavailable: %s", exc)
    return _search_model


def _get_qdrant_client():
    """Lazily load and cache the QdrantClient."""
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client
    try:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(host="localhost", port=6333, timeout=5.0)
        logger.info("Loaded QdrantClient")
    except Exception as exc:
        logger.warning("QdrantClient unavailable: %s", exc)
    return _qdrant_client


# ---------------------------------------------------------------------------
# Async health-check helpers (non-blocking)
# ---------------------------------------------------------------------------

async def _check_ollama() -> bool:
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:11434/api/tags", timeout=3.0)
            return r.status_code == 200
    except Exception:
        return False


async def _check_qdrant() -> bool:
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:6333/collections", timeout=3.0)
            return r.status_code == 200
    except Exception:
        return False


def _check_paddleocr() -> bool:
    try:
        from paddleocr import PaddleOCR  # noqa: F401
        return True
    except Exception:
        return False


def _check_tesseract() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.post("/classify", response_model=ClassifyResponse)
async def classify_text(req: ClassifyRequest):
    """Classify medical text using the best available classifier engine."""
    clf, clf_type = _get_classifier()
    try:
        result = clf.classify(req.text)
    except Exception as exc:
        logger.error("Classification error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Classification failed")

    # Normalize output — both MedicalClassifier and _MinimalClassifier return dicts
    if isinstance(result, dict):
        category = result.get("category", "general")
        confidence = result.get("confidence", 0.0)
        all_scores = result.get("all_scores", {})
    else:
        category = str(result)
        confidence = 0.5
        all_scores = {}

    # Apply confidence filter
    if confidence < req.min_confidence:
        category = "general"
        confidence = 0.0

    return ClassifyResponse(
        category=category,
        confidence=round(confidence, 3),
        all_scores=all_scores,
    )


@router.post("/organize", response_model=OrganizeResponse)
async def organize_files(req: OrganizeRequest):
    """Organize files in source_dir into category-based subdirectories."""
    # Security: validate paths are within allowed directories
    source = _validate_path(req.source_dir)
    target = _validate_path(req.target_dir, must_exist=False) if req.target_dir else source

    if not source.is_dir():
        raise HTTPException(status_code=400, detail=f"Source directory not found: {source}")

    # Security: ensure target is within sandbox
    try:
        _validate_path(str(target), must_exist=False)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Target directory is outside allowed directories")

    clf, _ = _get_classifier()
    organized: dict[str, list[str]] = {}
    errors: list[str] = []
    total = 0

    for item in source.iterdir():
        if not item.is_file():
            continue
        total += 1
        try:
            # Skip binary files — only read text-like files
            binary_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp",
                          ".mp3", ".wav", ".mp4", ".avi", ".mkv", ".mov", ".exe", ".dll"}
            text_content = ""
            if item.suffix.lower() not in binary_exts:
                try:
                    text_content = item.read_text(encoding="utf-8", errors="ignore")[:4096]
                except Exception:
                    pass

            # Classify by filename + content
            label_text = f"{item.stem} {text_content}"
            result = clf.classify(label_text)
            category = result.get("category", "general") if isinstance(result, dict) else "general"

            # Security: sanitize category to prevent path traversal
            category = _sanitize_category(category)

            cat_dir = target / category
            organized.setdefault(category, []).append(item.name)

            if not req.dry_run:
                cat_dir.mkdir(parents=True, exist_ok=True)
                dest = cat_dir / item.name
                if req.move_files:
                    shutil.move(str(item), str(dest))
                else:
                    shutil.copy2(str(item), str(dest))
        except Exception as exc:
            errors.append(f"{item.name}: error during processing")

    return OrganizeResponse(
        organized=organized,
        dry_run=req.dry_run,
        total_files=total,
        errors=errors,
    )


@router.get("/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    """Semantic search — falls back through Qdrant → local-fuzzy → unavailable."""
    # Path 1: Qdrant vector search (with cached model & client)
    client = _get_qdrant_client()
    model = _get_search_model()
    if client and model:
        try:
            query_vec = model.encode(q).tolist()
            hits = client.search(collection_name="medical_docs", query_vector=query_vec, limit=limit)
            results = [
                {"id": str(h.id), "score": h.score, "payload": h.payload or {}}
                for h in hits
            ]
            return SearchResponse(query=q, results=results, engine="qdrant+sentence-transformers", total=len(results))
        except Exception as exc:
            logger.debug("Qdrant search unavailable: %s", exc)

    # Path 2: local fuzzy search with rapidfuzz
    try:
        from rapidfuzz import fuzz as rfuzz

        data_dir = os.environ.get("OMNI_DATA_DIR", "data")
        results: list[dict[str, Any]] = []
        for fpath in glob.glob(os.path.join(data_dir, "**/*"), recursive=True):
            if os.path.isfile(fpath):
                score = rfuzz.token_sort_ratio(q.lower(), os.path.basename(fpath).lower())
                if score > 40:
                    results.append({"path": fpath, "score": score / 100.0})
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:limit]
        return SearchResponse(query=q, results=results, engine="rapidfuzz-local", total=len(results))
    except Exception as exc:
        logger.debug("Local fuzzy search unavailable: %s", exc)

    # Path 3: unavailable
    return SearchResponse(query=q, results=[], engine="unavailable", total=0)


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Return categories and engine availability flags."""
    clf, clf_type = _get_classifier()
    categories: list[str] = []

    # Try to get categories from the classifier
    if hasattr(clf, "get_categories"):
        try:
            categories = clf.get_categories()
        except Exception:
            pass
    if not categories:
        categories = list(_MinimalClassifier._KEYWORDS.keys())

    # Run health checks concurrently
    ollama_ok, qdrant_ok = await asyncio.gather(
        _check_ollama(), _check_qdrant()
    )

    engines = {
        "classifier": clf_type != "none",
        "ollama": ollama_ok,
        "qdrant": qdrant_ok,
        "paddleocr": _check_paddleocr(),
        "tesseract": _check_tesseract(),
    }

    return StatsResponse(categories=categories, engines=engines)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Lightweight health probe — checks external service availability concurrently."""
    ollama_ok, qdrant_ok = await asyncio.gather(
        _check_ollama(), _check_qdrant()
    )
    return HealthResponse(
        status="ok",
        ollama_available=ollama_ok,
        qdrant_available=qdrant_ok,
        paddleocr_available=_check_paddleocr(),
        tesseract_available=_check_tesseract(),
    )


# ---------------------------------------------------------------------------
# Standalone app (for running without the full app/main.py)
# ---------------------------------------------------------------------------

def create_standalone_app() -> "FastAPI":
    """Create a standalone FastAPI app with CORS for local development."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    _app = FastAPI(
        title="Omni Medical Suite — Core Engines API",
        description="REST API wrapping classifier, organizer, search, stats, and health engines",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _app.include_router(router, prefix="/api", tags=["core-engines"])

    @_app.get("/health")
    async def standalone_health():
        return {"status": "ok", "mode": "standalone"}

    return _app


# Only create standalone app when run directly: uvicorn src.api.server:app --port 8420
def _get_app():
    """Factory for standalone app — avoids creating app at import time."""
    return create_standalone_app()


# For uvicorn: uvicorn src.api.server:app --port 8420
app = create_standalone_app()
