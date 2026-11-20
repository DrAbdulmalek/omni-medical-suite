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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.db.models.auth import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path sandboxing — security: only allow paths under explicit upload/data roots
# ---------------------------------------------------------------------------

_ALLOWED_DIRS: list[Path] | None = None


def _get_allowed_dirs() -> list[Path]:
    """Get and cache explicitly configured filesystem roots.

    There is deliberately no implicit CWD fallback: the repository/application
    directory may contain secrets, source code, credentials, or configuration.
    """
    global _ALLOWED_DIRS
    if _ALLOWED_DIRS is not None:
        return _ALLOWED_DIRS
    dirs_str = os.environ.get("OMNI_ALLOWED_DIRS")
    if not dirs_str:
        dirs_str = os.path.join(os.getcwd(), "data")
    _ALLOWED_DIRS = [
        Path(d.strip()).resolve()
        for d in dirs_str.split(",")
        if d.strip()
    ]
    return _ALLOWED_DIRS


def _validate_path(path_str: str, must_exist: bool = True) -> Path:
    """Validate that a path is within explicitly allowed directories."""
    resolved = Path(path_str).resolve()
    allowed = _get_allowed_dirs()
    if not any(resolved.is_relative_to(allowed_dir) for allowed_dir in allowed):
        raise HTTPException(status_code=403, detail="Path is outside allowed directories")
    if must_exist and not resolved.exists():
        raise HTTPException(status_code=400, detail="Path not found")
    return resolved


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
# Minimal fallback classifier
# ---------------------------------------------------------------------------

class _MinimalClassifier:
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
        if best_score <= 0.05:
            best_cat, best_score = "general", 0.1
        return {"category": best_cat, "confidence": round(best_score, 3), "all_scores": {k: round(v, 3) for k, v in scores.items()}}


_classifier: Optional[Any] = None
_classifier_type: str = "none"
_search_model: Optional[Any] = None
_qdrant_client: Optional[Any] = None


def _get_classifier() -> tuple[Any, str]:
    global _classifier, _classifier_type
    if _classifier is not None:
        return _classifier, _classifier_type
    try:
        from hf_space.packages.core.classifier import MedicalClassifier
        _classifier = MedicalClassifier()
        _classifier_type = "MedicalClassifier (hf-space)"
        return _classifier, _classifier_type
    except Exception as exc:
        logger.debug("hf-space classifier unavailable: %s", exc)
    try:
        from packages.core.classifier import MedicalClassifier
        _classifier = MedicalClassifier()
        _classifier_type = "MedicalClassifier (packages)"
        return _classifier, _classifier_type
    except Exception as exc:
        logger.debug("packages.core classifier unavailable: %s", exc)
    _classifier = _MinimalClassifier()
    _classifier_type = "_MinimalClassifier (fallback)"
    return _classifier, _classifier_type


def _get_search_model():
    global _search_model
    if _search_model is not None:
        return _search_model
    try:
        from sentence_transformers import SentenceTransformer
        _search_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    except Exception as exc:
        logger.warning("SentenceTransformer unavailable: %s", exc)
    return _search_model


def _get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client
    try:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(host="localhost", port=6333, timeout=5.0)
    except Exception as exc:
        logger.warning("QdrantClient unavailable: %s", exc)
    return _qdrant_client


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


router = APIRouter()


@router.post("/classify", response_model=ClassifyResponse)
async def classify_text(req: ClassifyRequest, current_user: User = Depends(get_current_user)):
    """Classify medical text; authentication is mandatory."""
    clf, _ = _get_classifier()
    try:
        result = clf.classify(req.text)
    except Exception:
        logger.exception("Classification error")
        raise HTTPException(status_code=500, detail="Classification failed")
    if isinstance(result, dict):
        category = result.get("category", "general")
        confidence = result.get("confidence", 0.0)
        all_scores = result.get("all_scores", {})
    else:
        category, confidence, all_scores = str(result), 0.5, {}
    if confidence < req.min_confidence:
        category, confidence = "general", 0.0
    return ClassifyResponse(category=category, confidence=round(confidence, 3), all_scores=all_scores)


@router.post("/organize", response_model=OrganizeResponse)
async def organize_files(req: OrganizeRequest, current_user: User = Depends(get_current_user)):
    """Organize files; authentication and explicit filesystem sandbox are mandatory."""
    source = _validate_path(req.source_dir)
    target = _validate_path(req.target_dir, must_exist=False) if req.target_dir else source
    if not source.is_dir():
        raise HTTPException(status_code=400, detail="Source directory is not a directory")
    clf, _ = _get_classifier()
    organized: dict[str, list[str]] = {}
    errors: list[str] = []
    total = 0
    for item in source.iterdir():
        if not item.is_file():
            continue
        total += 1
        try:
            binary_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".mp3", ".wav", ".mp4", ".avi", ".mkv", ".mov", ".exe", ".dll"}
            text_content = ""
            if item.suffix.lower() not in binary_exts:
                try:
                    text_content = item.read_text(encoding="utf-8", errors="ignore")[:4096]
                except Exception:
                    pass
            result = clf.classify(f"{item.stem} {text_content}")
            category = _sanitize_category(result.get("category", "general") if isinstance(result, dict) else "general")
            cat_dir = target / category
            organized.setdefault(category, []).append(item.name)
            if not req.dry_run:
                cat_dir.mkdir(parents=True, exist_ok=True)
                dest = cat_dir / item.name
                if not dest.resolve().is_relative_to(target.resolve()):
                    raise HTTPException(status_code=403, detail="Destination escapes sandbox")
                if req.move_files:
                    shutil.move(str(item), str(dest))
                else:
                    shutil.copy2(str(item), str(dest))
        except HTTPException:
            raise
        except Exception:
            errors.append(f"{item.name}: error during processing")
    return OrganizeResponse(organized=organized, dry_run=req.dry_run, total_files=total, errors=errors)


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Search medical data; authentication is mandatory."""
    client = _get_qdrant_client()
    model = _get_search_model()
    if client and model:
        try:
            query_vec = model.encode(q).tolist()
            hits = client.search(collection_name="medical_docs", query_vector=query_vec, limit=limit)
            results = [{"id": str(h.id), "score": h.score, "payload": h.payload or {}} for h in hits]
            return SearchResponse(query=q, results=results, engine="qdrant+sentence-transformers", total=len(results))
        except Exception as exc:
            logger.debug("Qdrant search unavailable: %s", exc)
    try:
        from rapidfuzz import fuzz as rfuzz
        data_dir = os.environ.get("OMNI_DATA_DIR", "data")
        data_root = _validate_path(data_dir)
        results: list[dict[str, Any]] = []
        for fpath in glob.glob(os.path.join(str(data_root), "**/*"), recursive=True):
            if os.path.isfile(fpath):
                score = rfuzz.token_sort_ratio(q.lower(), os.path.basename(fpath).lower())
                if score > 40:
                    results.append({"path": fpath, "score": score / 100.0})
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:limit]
        return SearchResponse(query=q, results=results, engine="rapidfuzz-local", total=len(results))
    except HTTPException:
        raise
    except Exception as exc:
        logger.debug("Local fuzzy search unavailable: %s", exc)
    return SearchResponse(query=q, results=[], engine="unavailable", total=0)
