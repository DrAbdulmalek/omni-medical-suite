"""
Medical OCR Suite — Hugging Face Space Demo
FastAPI application exposing postprocessor capabilities.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import uvicorn
import os
import sys

# Install postprocessor from GitHub if not available
try:
    from medical_ocr_toolkit import correct_text, mask_phi, batch_process
except ImportError:
    print("Installing medical-ocr-postprocessor from GitHub...")
    import subprocess
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "git+https://github.com/DrAbdulmalek/medical-ocr-postprocessor.git@main"
    ])
    from medical_ocr_toolkit import correct_text, mask_phi, batch_process

app = FastAPI(
    title="Medical OCR Suite",
    description="منصة تصحيح النصوص الطبية — Medical OCR Postprocessing Demo",
    version="2.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


class TextCorrectionRequest(BaseModel):
    """Request body for text correction."""
    text: str = Field(..., description="النص المراد تصحيحه", min_length=1)
    language: str = Field(default="ar", description="لغة النص: ar أو en")

class BatchCorrectionRequest(BaseModel):
    """Request body for batch correction."""
    texts: List[str] = Field(..., description="قائمة النصوص المراد تصحيحها")
    language: str = Field(default="ar", description="لغة النص: ar أو en")

class PHIRequest(BaseModel):
    """Request body for PHI masking."""
    text: str = Field(..., description="النص المراد حجب بياناته الصحية", min_length=1)
    mode: str = Field(default="mask", description="نوع الحجب: mask, remove, replace")

class CorrectionResponse(BaseModel):
    corrected_text: str
    language: str
    changes_count: int = 0

class BatchResponse(BaseModel):
    results: List[dict]
    total: int
    language: str

class PHIResponse(BaseModel):
    masked_text: str
    entities_found: int = 0


@app.get("/")
def root():
    """Health check and platform info."""
    return {
        "message": "مرحباً بك في منصة معالجة النصوص الطبية 🏥",
        "status": "online",
        "version": "2.2.0",
        "endpoints": {
            "docs": "/docs",
            "correct": "POST /correct",
            "batch": "POST /correct/batch",
            "mask_phi": "POST /mask-phi",
            "health": "GET /health",
        },
        "github": "https://github.com/DrAbdulmalek/omni-medical-suite"
    }


@app.post("/correct", response_model=CorrectionResponse)
async def correct_medical_text(request: TextCorrectionRequest):
    """Correct medical OCR text using the postprocessor engine."""
    try:
        corrected = correct_text(request.text, language=request.language)
        changes = sum(
            1 for a, b in zip(request.text, corrected) if a != b
        )
        return CorrectionResponse(
            corrected_text=corrected,
            language=request.language,
            changes_count=changes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/correct/batch", response_model=BatchResponse)
async def correct_batch(request: BatchCorrectionRequest):
    """Correct multiple medical texts at once."""
    try:
        results = []
        for text in request.texts:
            corrected = correct_text(text, language=request.language)
            changes = sum(1 for a, b in zip(text, corrected) if a != b)
            results.append({
                "original": text[:100],
                "corrected": corrected[:100],
                "changes_count": changes
            })
        return BatchResponse(
            results=results,
            total=len(results),
            language=request.language
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mask-phi", response_model=PHIResponse)
async def mask_phi_data(request: PHIRequest):
    """Detect and mask Protected Health Information in text."""
    try:
        masked = mask_phi(request.text, mode=request.mode)
        entities = sum(1 for a, b in zip(request.text, masked) if a != b)
        return PHIResponse(
            masked_text=masked,
            entities_found=max(1, entities // 10)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    """Detailed system health check."""
    return {
        "status": "healthy",
        "port": int(os.getenv("PORT", 7860)),
        "version": "2.2.0",
        "components": {
            "api": "running",
            "postprocessor": "loaded"
        }
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
