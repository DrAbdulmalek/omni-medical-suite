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

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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
        logger.debug(f"hf-space classifier unavailable: {exc}")

    # Path 2: packages core
    try:
        from packages.core.classifier import MedicalClassifier
        _classifier = MedicalClassifier()
        _classifier_type = "MedicalClassifier (packages)"
        logger.info("Loaded MedicalClassifier from packages.core")
        return _classifier, _classifier_type
    except Exception as exc:
        logger.debug(f"packages.core classifier unavailable: {exc}")

    # Path 3: minimal fallback
    _classifier = _MinimalClassifier()
    _classifier_type = "_MinimalClassifier (fallback)"
    logger.warning("Full classifier unavailable — using _MinimalClassifier fallback")
    return _classifier, _classifier_type


# ---------------------------------------------------------------------------
# Health-check helpers
# ---------------------------------------------------------------------------

def _check_ollama() -> bool:
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def _check_qdrant() -> bool:
    try:
        import httpx
        r = httpx.get("http://localhost:6333/collections", timeout=3.0)
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
        logger.error(f"Classification error: {exc}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {exc}")

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
    source = Path(req.source_dir).resolve()
    target = Path(req.target_dir).resolve() if req.target_dir else source

    if not source.is_dir():
        raise HTTPException(status_code=400, detail=f"Source directory not found: {source}")

    clf, _ = _get_classifier()
    organized: dict[str, list[str]] = {}
    errors: list[str] = []
    total = 0

    for item in source.iterdir():
        if not item.is_file():
            continue
        total += 1
        try:
            # Read text content for classification (first 4KB)
            text_content = ""
            try:
                text_content = item.read_text(encoding="utf-8", errors="ignore")[:4096]
            except Exception:
                pass

            # Classify by filename + content
            label_text = f"{item.stem} {text_content}"
            result = clf.classify(label_text)
            category = result.get("category", "general") if isinstance(result, dict) else "general"

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
            errors.append(f"{item.name}: {exc}")

    return OrganizeResponse(
        organized=organized,
        dry_run=req.dry_run,
        total_files=total,
        errors=errors,
    )


@router.get("/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    """Semantic search — falls back through Qdrant → local-fuzzy → unavailable."""
    # Path 1: Qdrant vector search
    try:
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer

        client = QdrantClient(host="localhost", port=6333, timeout=5.0)
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        query_vec = model.encode(q).tolist()
        hits = client.search(collection_name="medical_docs", query_vector=query_vec, limit=limit)
        results = [
            {"id": str(h.id), "score": h.score, "payload": h.payload or {}}
            for h in hits
        ]
        return SearchResponse(query=q, results=results, engine="qdrant+sentence-transformers", total=len(results))
    except Exception as exc:
        logger.debug(f"Qdrant search unavailable: {exc}")

    # Path 2: local fuzzy search with rapidfuzz
    try:
        from rapidfuzz import fuzz as rfuzz
        import glob

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
        logger.debug(f"Local fuzzy search unavailable: {exc}")

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

    engines = {
        "classifier": clf_type != "none",
        "ollama": _check_ollama(),
        "qdrant": _check_qdrant(),
        "paddleocr": _check_paddleocr(),
        "tesseract": _check_tesseract(),
    }

    return StatsResponse(categories=categories, engines=engines)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Lightweight health probe — checks external service availability."""
    return HealthResponse(
        status="ok",
        ollama_available=_check_ollama(),
        qdrant_available=_check_qdrant(),
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


# When run directly: uvicorn src.api.server:app --port 8420
app = create_standalone_app()
