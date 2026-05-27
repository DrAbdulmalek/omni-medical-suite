"""
Pydantic schemas for OCR operations.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class OCRRequest(BaseModel):
    """Request schema for OCR processing."""
    engines: Optional[list[str]] = Field(default=None, description="OCR engines to use")
    language: Optional[str] = Field(default="auto", description="Language code or 'auto'")
    medical_mode: bool = Field(default=True, description="Enable medical term extraction")
    fusion_method: Optional[str] = Field(default="v2_spatial", description="Fusion method to use")


class OCRResult(BaseModel):
    """Single OCR engine result."""
    engine: str
    text: str
    confidence: float
    processing_time: float


class MedicalTerm(BaseModel):
    """Extracted medical term."""
    original: str
    translation: str
    language: str
    confidence: float
    context: str


class OCRResponse(BaseModel):
    """Full OCR response."""
    document_id: int
    filename: str
    status: str
    fused_text: Optional[str] = None
    individual_results: list[OCRResult] = []
    medical_terms: list[MedicalTerm] = []
    confidence_score: float = 0.0
    processing_time: float = 0.0


class TaskResponse(BaseModel):
    """Async task response."""
    task_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    uptime_seconds: float
    components: dict[str, str]


class CorrectionRequest(BaseModel):
    """Request to submit a correction."""
    document_id: int
    original_text: str
    corrected_text: str
    context: Optional[str] = None


class BatchOCRRequest(BaseModel):
    """Batch OCR processing request."""
    file_count: int = Field(ge=1, le=100)
    medical_mode: bool = True
    fusion_method: str = "v2_spatial"
