# app/routers/ocr.py
"""OCR Router - Stub for future implementation"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/engines")
async def list_engines():
    return {"engines": ["paddleocr", "tesseract", "easyocr", "trocr"]}

@router.post("/process")
async def process_ocr():
    return {"status": "not_implemented", "message": "OCR processing endpoint - coming soon"}
