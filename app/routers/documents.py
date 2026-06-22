"""
Document management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.ocr import OCRResponse
from app.models.document import Document

router = APIRouter(prefix="/api/v1", tags=["Documents"])


@router.get("/documents", response_model=list[OCRResponse])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List all documents with pagination."""
    docs = db.query(Document).offset(skip).limit(limit).all()
    return [
        OCRResponse(
            document_id=d.id,
            filename=d.filename,
            status=d.status,
            fused_text=d.fused_text,
            medical_terms=d.medical_terms or [],
            confidence_score=d.confidence_score or 0.0,
            processing_time=d.processing_time or 0.0,
        )
        for d in docs
    ]


@router.get("/documents/{document_id}", response_model=OCRResponse)
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get a specific document by ID."""
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
    )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and its associated data."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"message": f"Document {document_id} deleted"}
