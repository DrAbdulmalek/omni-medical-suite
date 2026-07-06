# app/routers/jobs.py
"""Jobs Router - Stub for future implementation"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_jobs():
    return {"jobs": [], "message": "Jobs endpoints - coming soon"}

@router.post("/")
async def create_job():
    return {"status": "not_implemented", "message": "Job creation endpoint - coming soon"}