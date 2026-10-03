# app/routers/pipeline.py
"""Pipeline Router - Stub for future implementation"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_pipelines():
    return {"pipelines": [], "message": "Pipeline endpoints - coming soon"}

@router.post("/run")
async def run_pipeline():
    return {"status": "not_implemented", "message": "Pipeline execution endpoint - coming soon"}
