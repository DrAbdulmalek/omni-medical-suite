"""OmniMedical Suite v2.0 — Corrections Router"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.metrics import corrections_applied, promotion_queue_size
from app.schemas.correction import CorrectionCreate, CorrectionResponse, CorrectionStats
from app.services.correction_service import CorrectionService

router = APIRouter(prefix="/corrections", tags=["Corrections"])

correction_service = CorrectionService()


@router.post("/", response_model=CorrectionResponse)
async def create_correction(
    correction: CorrectionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Submit a manual correction to the review queue"""
    result = await correction_service.create_correction(correction)
    corrections_applied.labels(source="manual").inc()
    return result


@router.get("/", response_model=List[CorrectionResponse])
async def list_corrections(
    status: Optional[str] = Query(None, description="pending, approved, rejected, auto_promoted"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List corrections with optional filtering"""
    return await correction_service.list_corrections(status=status, limit=limit, offset=offset)


@router.get("/stats", response_model=CorrectionStats)
async def get_correction_stats(db: AsyncSession = Depends(get_db)):
    """Get correction memory statistics"""
    stats = correction_service.get_stats()
    promotion_queue_size.set(stats.get("queue_size", 0))
    return CorrectionStats(**stats)


@router.post("/{correction_id}/approve")
async def approve_correction(correction_id: str, db: AsyncSession = Depends(get_db)):
    """Approve a pending correction (doctor review)"""
    return await correction_service.approve_correction(correction_id)


@router.post("/{correction_id}/reject")
async def reject_correction(
    correction_id: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Reject a pending correction with optional reason"""
    return await correction_service.reject_correction(correction_id, reason)


@router.post("/run-promotion")
async def run_auto_promotion(db: AsyncSession = Depends(get_db)):
    """Manually trigger auto-promotion cycle"""
    promoted = correction_service.run_promotion_cycle()
    return {"promoted_count": len(promoted), "promotions": promoted}
