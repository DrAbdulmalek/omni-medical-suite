"""OmniMedical Suite v2.0 — Correction Service"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.config import settings
from app.core.metrics import corrections_applied, promotions_executed
from app.schemas.correction import CorrectionCreate, CorrectionResponse, CorrectionStats
from omnimedical_gradio_ui import CorrectionMemoryV2, AutoPromotionEngine, MedicalContextProtector


class CorrectionService:
    """Business logic for correction management"""

    def __init__(self):
        self.memory = CorrectionMemoryV2(settings.CORRECTION_DB_PATH)
        self.protector = MedicalContextProtector()
        self.promoter = AutoPromotionEngine(
            self.memory,
            self.protector,
            criteria={
                "min_frequency": settings.PROMOTION_FREQUENCY_THRESHOLD,
                "min_confidence_gain": settings.PROMOTION_CONFIDENCE_GAIN,
                "max_age_days": settings.PROMOTION_MAX_AGE_DAYS
            }
        )

    async def create_correction(self, correction: CorrectionCreate) -> CorrectionResponse:
        """Add correction to queue"""
        self.memory.save(
            original=correction.original,
            corrected=correction.corrected,
            language=correction.language,
            context_before=correction.context_before,
            context_after=correction.context_after,
            confidence_before=correction.confidence_before,
            confidence_after=correction.confidence_after,
            source_file="api_upload"
        )
        corrections_applied.labels(source="api").inc()

        return CorrectionResponse(
            id="temp-id",  # In production: from database
            original=correction.original,
            corrected=correction.corrected,
            status="pending",
            frequency=1,
            confidence_gain=correction.confidence_after - correction.confidence_before,
            auto_promoted=False,
            created_at=datetime.utcnow()
        )

    async def list_corrections(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[CorrectionResponse]:
        """List corrections from queue"""
        # In production: query PostgreSQL
        return []

    async def approve_correction(self, correction_id: str) -> Dict[str, Any]:
        """Doctor approves a correction"""
        # In production: update database, trigger promotion
        return {"status": "approved", "id": correction_id}

    async def reject_correction(self, correction_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Doctor rejects a correction"""
        return {"status": "rejected", "id": correction_id, "reason": reason}

    def get_stats(self) -> Dict[str, Any]:
        """Get correction memory statistics"""
        stats = self.memory.get_stats()
        return {
            "total": stats.get("total", 0),
            "promoted": stats.get("promoted", 0),
            "avg_gain": stats.get("avg_gain", 0.0),
            "top_corrections": [
                {"original": t[0], "corrected": t[1], "frequency": t[2], "gain": t[3]}
                for t in stats.get("top", [])
            ],
            "queue_size": stats.get("total", 0) - stats.get("promoted", 0)
        }

    def run_promotion_cycle(self) -> List[Dict]:
        """Manually trigger auto-promotion"""
        if not settings.AUTO_PROMOTION_ENABLED:
            return []

        promoted = self.promoter.run_promotion_cycle()
        promotions_executed.labels(result="success").inc(len(promoted))
        return promoted
