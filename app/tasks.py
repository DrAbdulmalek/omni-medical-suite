"""
Celery tasks for async OCR processing.
"""
import time
import logging
from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

app = Celery(
    "omnimedical",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=660,
    task_routes={
        "app.tasks.process_document_task": {"queue": "ocr"},
        "app.tasks.process_batch_task": {"queue": "ocr"},
        "app.tasks.extract_medical_terms_task": {"queue": "nlp"},
    },
)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_task(self, document_id: int, file_path: str):
    """Process a single document with OCR fusion."""
    from app.core.database import SessionLocal
    from app.models.document import Document, DocumentStatus
    from app.services.ocr_service import ocr_service
    
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return
        
        doc.status = DocumentStatus.PROCESSING.value
        db.commit()
        
        # Run OCR processing (synchronous within the worker)
        import asyncio
        result = asyncio.run(ocr_service.process_image(file_path))
        
        doc.fused_text = result["fused_text"]
        doc.confidence_score = result["confidence"]
        doc.ocr_engines_used = result["engines_used"]
        doc.processing_time = result["processing_time"]
        doc.status = DocumentStatus.COMPLETED.value
        db.commit()
        
        logger.info(f"Document {document_id} processed in {result['processing_time']:.2f}s")
        
    except Exception as exc:
        logger.error(f"Document {document_id} failed: {exc}")
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED.value
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()


@app.task(bind=True, max_retries=2)
def process_batch_task(self, document_ids: list[int]):
    """Process multiple documents in batch."""
    results = []
    for doc_id in document_ids:
        try:
            result = process_document_task(doc_id)
            results.append({"document_id": doc_id, "status": "completed"})
        except Exception as e:
            results.append({"document_id": doc_id, "status": "failed", "error": str(e)})
    return results


@app.task
def extract_medical_terms_task(text: str) -> list[dict]:
    """Extract medical terms from text."""
    import asyncio
    from app.services.ocr_service import ocr_service
    return asyncio.run(ocr_service.extract_medical_terms(text))


@app.task
def health_check_task():
    """Periodic health check task."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute("SELECT 1")
        return {"database": "healthy"}
    except Exception as e:
        return {"database": "unhealthy", "error": str(e)}
    finally:
        db.close()


@app.task
def cleanup_old_documents_task(days: int = 30):
    """Clean up documents older than specified days."""
    from datetime import datetime, timedelta
    from app.core.database import SessionLocal
    from app.models.document import Document
    import os
    
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        old_docs = db.query(Document).filter(Document.created_at < cutoff).all()
        count = 0
        for doc in old_docs:
            if doc.original_path and os.path.exists(doc.original_path):
                os.remove(doc.original_path)
            db.delete(doc)
            count += 1
        db.commit()
        logger.info(f"Cleaned up {count} old documents")
        return {"cleaned": count}
    finally:
        db.close()
