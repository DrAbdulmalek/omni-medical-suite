"""OmniMedical Suite v2.0 — Correction Schemas"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID


class CorrectionCreate(BaseModel):
    """Manual correction submission"""
    original: str = Field(..., min_length=1, max_length=1000)
    corrected: str = Field(..., min_length=1, max_length=1000)
    language: str = Field(default="ar")
    context_before: Optional[str] = ""
    context_after: Optional[str] = ""
    confidence_before: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_after: float = Field(default=0.95, ge=0.0, le=1.0)


class CorrectionResponse(BaseModel):
    """Correction in queue"""
    id: UUID
    original: str
    corrected: str
    status: str
    frequency: int
    confidence_gain: float
    auto_promoted: bool
    created_at: datetime


class CorrectionStats(BaseModel):
    """Correction memory statistics"""
    total: int
    promoted: int
    avg_gain: float
    top_corrections: List[dict]
    queue_size: int
