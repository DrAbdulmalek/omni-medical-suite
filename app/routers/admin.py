# app/routers/admin.py
"""Admin Router - Stub for future implementation"""
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.db.models.auth import User

router = APIRouter()

@router.get("/system-status")
async def system_status(current_user: User = Depends(get_current_user)):
    # Security: system status is intentionally restricted to authenticated users.
    return {"status": "healthy", "message": "Admin endpoints - coming soon"}
