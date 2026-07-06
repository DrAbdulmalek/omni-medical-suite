# app/routers/datasets.py
"""Datasets Router - Stub for future implementation"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_datasets():
    return {"datasets": [], "message": "Dataset endpoints - coming soon"}