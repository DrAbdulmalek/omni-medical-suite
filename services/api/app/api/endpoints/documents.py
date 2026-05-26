"""Document management endpoints for OmniMedicalSuite.

Provides REST endpoints for uploading, listing, retrieving, and deleting
medical documents.  Uploaded images and PDFs are processed through the
OCR fusion pipeline and the extracted text is stored alongside the
document metadata.

Endpoints
---------
POST   /documents/upload                Upload and OCR a document
GET    /documents/                      List all documents (paginated)
GET    /documents/{document_id}         Get document details
GET    /documents/{document_id}/text    Get extracted text only
DELETE /documents/{document_id}         Delete a document
POST   /documents/{document_id}/reprocess  Re-run OCR with different settings
GET    /documents/{document_id}/knowledge-graph  Get document knowledge graph
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# ---------------------------------------------------------------------------
# Allowed MIME types for upload
# ---------------------------------------------------------------------------
_ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
    "image/gif",
}
_ALLOWED_MIME_TYPES = _ALLOWED_IMAGE_TYPES | {"application/pdf"}

# ---------------------------------------------------------------------------
# Upload directory (relative to project root, created on first upload)
# ---------------------------------------------------------------------------
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "uploads")


def _ensure_upload_dir() -> str:
    """Return the absolute path to the upload directory, creating it if needed."""
    abs_path = os.path.abspath(_UPLOAD_DIR)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


# ===================================================================
# Pydantic response models
# ===================================================================

class DocumentUploadResponse(BaseModel):
    """Response returned after a successful document upload."""

    document_id: str
    filename: str
    text: str
    page_count: int = 1
    processing_time_ms: float = 0.0
    word_count: int = 0
    created_at: str


class DocumentBrief(BaseModel):
    """Summary of a document used in list responses."""

    document_id: str
    filename: str
    mime_type: str = "application/octet-stream"
    file_size_bytes: int = 0
    created_at: str


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    documents: list[DocumentBrief]
    total: int = 0
    skip: int = 0
    take: int = 20


class DocumentDetailResponse(BaseModel):
    """Full document details including extracted text."""

    document_id: str
    filename: str
    filepath: str
    mime_type: str = "application/octet-stream"
    file_size_bytes: int = 0
    extracted_text: str = ""
    page_count: int = 1
    word_count: int = 0
    processing_time_ms: float = 0.0
    fusion_method: str = ""
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    created_at: str


class DocumentTextResponse(BaseModel):
    """Extracted text for a document."""

    document_id: str
    text: str
    word_count: int = 0
    language_detected: str = "eng"


class ReprocessRequest(BaseModel):
    """Request body for re-processing a document with different OCR settings."""

    engines: list[str] | None = Field(
        default=None,
        description="List of specific OCR engines to use. None = all registered.",
    )
    fusion_method: str | None = Field(
        default=None,
        description="Fusion strategy (weighted_vote, character_level, best_confidence, smart_fallback).",
    )
    language: str = Field(
        default="eng+ara",
        description="Language hint string (e.g. 'eng+ara').",
    )


class KnowledgeGraphResponse(BaseModel):
    """Knowledge graph extracted from a document."""

    document_id: str
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeleteResponse(BaseModel):
    """Confirmation of document deletion."""

    document_id: str
    deleted: bool = True
    message: str = ""


# ===================================================================
# Helper functions
# ===================================================================

async def _get_fusion_engine() -> Any:
    """Lazily create and return an OCRFusionEngine instance."""
    from ...core.config import get_settings
    from ...vision.ocr_fusion_system import OCRFusionEngine

    settings = get_settings()
    engine = OCRFusionEngine(settings)
    engine.discover_and_register_all()
    return engine


async def _run_ocr(filepath: str, language: str = "eng+ara") -> tuple[str, float, dict[str, float], str]:
    """Run OCR fusion on a file and return (text, time_ms, confidence, method).

    Parameters
    ----------
    filepath:
        Absolute path to the image file.
    language:
        Language hint string.

    Returns
    -------
    tuple[str, float, dict[str, float], str]
        (extracted_text, processing_time_ms, confidence_scores, fusion_method)
    """
    engine = await _get_fusion_engine()
    t0 = time.perf_counter()
    result = await engine.process(filepath, lang=language)
    elapsed = (time.perf_counter() - t0) * 1000
    return result.final_text, elapsed, result.confidence_scores, result.fusion_method


def _extracted_text_cache_path(document_id: str) -> str:
    """Return the path where extracted text JSON is cached."""
    return os.path.join(_ensure_upload_dir(), f"{document_id}_text.json")


# ===================================================================
# Endpoints
# ===================================================================

@router.post("/upload", response_model=DocumentUploadResponse, summary="Upload and OCR a medical document")
async def upload_document(
    file: UploadFile = File(..., description="Image or PDF file to upload"),
) -> DocumentUploadResponse:
    """Upload a medical document (image or PDF) and run OCR fusion.

    The file is saved to the server, processed through the OCR pipeline,
    and metadata is stored in the database.

    Raises
    ------
    400
        If the file type or size is invalid.
    500
        If OCR processing fails.
    """
    from ...core.config import get_settings

    settings = get_settings()

    # Validate MIME type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. Allowed: {sorted(_ALLOWED_MIME_TYPES)}",
        )

    # Read file content and validate size
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(content)} bytes). Maximum is {settings.max_upload_size_bytes} bytes.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Generate a unique document ID and save the file
    document_id = uuid.uuid4().hex[:24]
    filename = file.filename or f"document_{document_id}"
    upload_dir = _ensure_upload_dir()
    filepath = os.path.join(upload_dir, f"{document_id}_{filename}")

    try:
        with open(filepath, "wb") as f:
            f.write(content)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {exc}",
        ) from exc

    # Run OCR fusion pipeline
    t_start = time.perf_counter()
    try:
        extracted_text, processing_ms, confidence_scores, fusion_method = await _run_ocr(filepath)
    except Exception as exc:
        logger.error("OCR processing failed for document %s: %s", document_id, exc)
        # Clean up the saved file
        os.remove(filepath) if os.path.exists(filepath) else None
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {exc}",
        ) from exc

    total_ms = (time.perf_counter() - t_start) * 1000
    word_count = len(extracted_text.split())

    # Store document metadata in the database
    try:
        from ...services.prisma_client import create_document

        doc_record = await create_document(
            filename=filename,
            filepath=filepath,
            user_id="system",
            mime_type=content_type,
            file_size_bytes=len(content),
        )
        # Use the database-generated ID if available
        if doc_record and doc_record.get("id"):
            document_id = doc_record["id"]
    except Exception as exc:
        logger.warning("Failed to store document metadata in DB: %s", exc)
        # Non-fatal – the file is still processed and usable

    now = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Document uploaded: id=%s filename=%s words=%d time=%.1fms",
        document_id, filename, word_count, total_ms,
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=filename,
        text=extracted_text,
        page_count=1,
        processing_time_ms=round(total_ms, 2),
        word_count=word_count,
        created_at=now,
    )


@router.get("/", response_model=DocumentListResponse, summary="List all documents")
async def list_documents(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    take: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    search: str = Query(default="", description="Filter by filename (case-insensitive substring)"),
) -> DocumentListResponse:
    """Return a paginated list of all documents.

    Optionally filter by *search* substring against filenames.
    """
    from ...services.prisma_client import list_documents as db_list_documents

    try:
        docs = await db_list_documents(skip=skip, take=take)
    except Exception as exc:
        logger.error("Failed to list documents: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        ) from exc

    items: list[DocumentBrief] = []
    for doc in docs:
        if search and search.lower() not in doc.get("filename", "").lower():
            continue
        items.append(
            DocumentBrief(
                document_id=doc.get("id", ""),
                filename=doc.get("filename", ""),
                mime_type=doc.get("mimeType", "application/octet-stream"),
                file_size_bytes=doc.get("fileSizeBytes", 0),
                created_at=str(doc.get("createdAt", "")),
            )
        )

    return DocumentListResponse(
        documents=items,
        total=len(items),
        skip=skip,
        take=take,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse, summary="Get document details")
async def get_document(document_id: str) -> DocumentDetailResponse:
    """Retrieve full details for a specific document including extracted text.

    Raises
    ------
    404
        If the document does not exist.
    """
    from ...services.prisma_client import get_document as db_get_document

    doc = await db_get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    extracted_text = ""
    filepath = doc.get("filepath", "")
    if filepath and os.path.isfile(filepath):
        try:
            text, _, _, _ = await _run_ocr(filepath)
            extracted_text = text
        except Exception as exc:
            logger.warning("OCR re-run failed for document %s: %s", document_id, exc)
            extracted_text = "[OCR unavailable]"

    return DocumentDetailResponse(
        document_id=document_id,
        filename=doc.get("filename", ""),
        filepath=filepath,
        mime_type=doc.get("mimeType", "application/octet-stream"),
        file_size_bytes=doc.get("fileSizeBytes", 0),
        extracted_text=extracted_text,
        word_count=len(extracted_text.split()),
        created_at=str(doc.get("createdAt", "")),
    )


@router.get("/{document_id}/text", response_model=DocumentTextResponse, summary="Get extracted text only")
async def get_document_text(document_id: str) -> DocumentTextResponse:
    """Return only the extracted text for a document.

    Raises
    ------
    404
        If the document does not exist.
    """
    from ...services.prisma_client import get_document as db_get_document

    doc = await db_get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    extracted_text = ""
    filepath = doc.get("filepath", "")
    if filepath and os.path.isfile(filepath):
        try:
            text, _, _, _ = await _run_ocr(filepath)
            extracted_text = text
        except Exception as exc:
            logger.warning("OCR re-run failed for document %s: %s", document_id, exc)
            extracted_text = "[OCR unavailable]"

    return DocumentTextResponse(
        document_id=document_id,
        text=extracted_text,
        word_count=len(extracted_text.split()),
    )


@router.delete("/{document_id}", response_model=DeleteResponse, summary="Delete a document")
async def delete_document(document_id: str) -> DeleteResponse:
    """Delete a document and its associated file from disk.

    Raises
    ------
    404
        If the document does not exist.
    """
    from ...services.prisma_client import get_document as db_get_document
    from ...services.prisma_client import get_prisma

    doc = await db_get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    # Remove the file from disk
    filepath = doc.get("filepath", "")
    if filepath and os.path.isfile(filepath):
        try:
            os.remove(filepath)
            logger.info("Deleted file: %s", filepath)
        except OSError as exc:
            logger.warning("Failed to delete file %s: %s", filepath, exc)

    # Remove from database
    try:
        client = get_prisma()
        await client.document.delete(where={"id": document_id})
    except Exception as exc:
        logger.error("Failed to delete document record %s: %s", document_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Database error while deleting document: {exc}",
        ) from exc

    return DeleteResponse(
        document_id=document_id,
        deleted=True,
        message=f"Document '{doc.get('filename', '')}' deleted successfully.",
    )


@router.post("/{document_id}/reprocess", response_model=DocumentUploadResponse, summary="Re-run OCR with different settings")
async def reprocess_document(
    document_id: str,
    body: ReprocessRequest,
) -> DocumentUploadResponse:
    """Re-run the OCR pipeline on an existing document with optional engine
    and fusion method overrides.

    Raises
    ------
    404
        If the document does not exist.
    500
        If OCR processing fails.
    """
    from ...services.prisma_client import get_document as db_get_document

    doc = await db_get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    filepath = doc.get("filepath", "")
    if not filepath or not os.path.isfile(filepath):
        raise HTTPException(
            status_code=400,
            detail="Document file not found on disk – cannot reprocess.",
        )

    # Build a temporary config override if custom settings are provided
    from ...core.config import get_settings
    from ...vision.ocr_fusion_system import OCRFusionEngine

    settings = get_settings()
    engine = OCRFusionEngine(settings)

    if body.engines:
        # Only register the requested engines
        all_candidates = {
            "tesseract": "...vision.ocr_fusion_system.TesseractEngine",
            "easyocr": "...vision.ocr_fusion_system.EasyOCREngine",
            "paddleocr": "...vision.ocr_fusion_system.PaddleOCREngine",
            "trocr": "...vision.ocr_fusion_system.TrOCREngine",
            "surya": "...vision.ocr_fusion_system.SuryaEngine",
        }
        engine_classes = {
            "tesseract": __import__("app.vision.ocr_fusion_system", fromlist=["TesseractEngine"]).TesseractEngine,
            "easyocr": __import__("app.vision.ocr_fusion_system", fromlist=["EasyOCREngine"]).EasyOCREngine,
            "paddleocr": __import__("app.vision.ocr_fusion_system", fromlist=["PaddleOCREngine"]).PaddleOCREngine,
            "trocr": __import__("app.vision.ocr_fusion_system", fromlist=["TrOCREngine"]).TrOCREngine,
            "surya": __import__("app.vision.ocr_fusion_system", fromlist=["SuryaEngine"]).SuryaEngine,
        }
        for eng_name in body.engines:
            cls = engine_classes.get(eng_name)
            if cls:
                engine.register_engine(cls())
    else:
        engine.discover_and_register_all()

    if body.fusion_method:
        if body.fusion_method in engine._VALID_METHODS:
            engine.fusion_method = body.fusion_method
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid fusion method '{body.fusion_method}'. "
                       f"Valid: {sorted(engine._VALID_METHODS)}",
            )

    # Run OCR
    t_start = time.perf_counter()
    try:
        result = await engine.process(filepath, lang=body.language)
    except Exception as exc:
        logger.error("Reprocessing failed for document %s: %s", document_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"OCR reprocessing failed: {exc}",
        ) from exc

    total_ms = (time.perf_counter() - t_start) * 1000

    return DocumentUploadResponse(
        document_id=document_id,
        filename=doc.get("filename", ""),
        text=result.final_text,
        page_count=1,
        processing_time_ms=round(total_ms, 2),
        word_count=len(result.final_text.split()),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/{document_id}/knowledge-graph",
    response_model=KnowledgeGraphResponse,
    summary="Get knowledge graph for a document",
)
async def get_document_knowledge_graph(document_id: str) -> KnowledgeGraphResponse:
    """Extract and return the medical knowledge graph for a document.

    Runs the knowledge graph extraction pipeline on the document's extracted
    text and returns entities, relations, and metadata.

    Raises
    ------
    404
        If the document does not exist.
    500
        If knowledge graph extraction fails.
    """
    from ...services.prisma_client import get_document as db_get_document
    from ...vision.ocr_fusion_system import MedicalKnowledgeGraph

    doc = await db_get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    # Obtain extracted text
    extracted_text = ""
    filepath = doc.get("filepath", "")
    if filepath and os.path.isfile(filepath):
        try:
            text, _, _, _ = await _run_ocr(filepath)
            extracted_text = text
        except Exception:
            extracted_text = ""

    if not extracted_text.strip():
        return KnowledgeGraphResponse(
            document_id=document_id,
            entities=[],
            relations=[],
            metadata={"message": "No text available for knowledge graph extraction."},
        )

    # Build knowledge graph
    try:
        kg_engine = MedicalKnowledgeGraph()
        kg = await kg_engine.build(extracted_text)
    except Exception as exc:
        logger.error("Knowledge graph extraction failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge graph extraction failed: {exc}",
        ) from exc

    entities = [
        {
            "type": e.entity_type.value,
            "text": e.text,
            "confidence": e.confidence,
            "position": e.position,
        }
        for e in kg.entities
    ]
    relations = [
        {
            "subject": r.subject,
            "predicate": r.predicate,
            "object": r.object,
            "confidence": r.confidence,
        }
        for r in kg.relations
    ]

    return KnowledgeGraphResponse(
        document_id=document_id,
        entities=entities,
        relations=relations,
        metadata=kg.metadata,
    )
