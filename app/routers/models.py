# app/routers/models.py
"""Models Router - Stub for future implementation"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_models():
    return {"models": [], "message": "Model management endpoints - coming soon"}
