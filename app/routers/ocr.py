"""
OCR processing endpoints.
"""
import os
import uuid
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.telemetry import trace_operation, record_ocr_request
from app.schemas.ocr import OCRRequest, OCRResponse, OCRResult, MedicalTerm, TaskResponse
from app.models.document import Document, DocumentStatus

router = APIRouter(prefix="/api/v1", tags=["OCR"])


@router.post("/ocr/process", response_model=TaskResponse)
async def process_ocr(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and process a document with OCR. Returns a task ID for async processing."""
    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
    if ext not in ['png', 'jpg', 'jpeg', 'tiff', 'bmp', 'pdf']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    
    # Save file temporarily
    file_path = os.path.join(tempfile.gettempdir(), f"ocr_{uuid.uuid4().hex}_{file.filename}")
    try:
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Create document record
        doc = Document(
            filename=file.filename,
            original_path=file_path,
            status=DocumentStatus.PROCESSING.value,
            file_size=len(content),
            mime_type=file.content_type,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # Queue Celery task
        try:
            from app.tasks import process_document_task
            task = process_document_task.delay(doc.id, file_path)
            return TaskResponse(
                task_id=task.id,
                status="queued",
                message=f"Document {doc.id} queued for processing",
            )
        except ImportError:
            # Fallback: synchronous processing
            return TaskResponse(
                task_id=f"sync-{doc.id}",
                status="processing",
                message=f"Document {doc.id} processing synchronously",
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/result/{document_id}", response_model=OCRResponse)
async def get_ocr_result(document_id: int, db: Session = Depends(get_db)):
    """Retrieve OCR results for a processed document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return OCRResponse(
        document_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        fused_text=doc.fused_text,
        medical_terms=doc.medical_terms or [],
        confidence_score=doc.confidence_score or 0.0,
        processing_time=doc.processing_time or 0.0,
        individual_results=doc.ocr_engines_used or [],
    )


@router.get("/ocr/status/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """Check the status of an async OCR processing task."""
    try:
        from app.tasks import app as celery_app
        result = celery_app.AsyncResult(task_id)
        return TaskResponse(
            task_id=task_id,
            status=result.status,
            message=f"Task is {result.status}",
        )
    except ImportError:
        return TaskResponse(
            task_id=task_id,
            status="unknown",
            message="Celery not available",
        )
