# app/routers/admin.py
"""Admin Router - Stub for future implementation"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/system-status")
async def system_status():
    return {"status": "healthy", "message": "Admin endpoints - coming soon"}