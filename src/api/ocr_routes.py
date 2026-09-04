# src/api/ocr_routes.py
"""
FastAPI routes for OCR processing of uploaded medical images.

Endpoints:
  POST /ocr/process
    Accepts a single image upload (png/jpg/jpeg/tif/tiff/bmp).
    Runs the MedicalImageProcessor full_pipeline, then OCR.
    Returns JSON: {"filename": ..., "text": ...}

Hardening:
  * Strict allowlist of file extensions.
  * Hard cap on upload size (10 MB default).
  * Upload is written to a NamedTemporaryFile in the system temp dir
    (not the project data dir), and unlinked in a ``finally`` block.
  * Any pipeline/OCR exception becomes HTTP 500 with the exception
    message (no stacktrace leak in production deployments that
    configure FastAPI's exception handlers).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.processors.image_processor import MedicalImageProcessor
from src.processors.ocr_engine import MedicalOCREngine


router = APIRouter()

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/ocr/process")
async def process_image(file: UploadFile = File(...)):
    filename = file.filename or "upload.png"
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        processed_image = MedicalImageProcessor.full_pipeline(tmp_path)
        engine = MedicalOCREngine(
            languages=("ar", "en"),
            use_easyocr=True,
            tesseract_lang="ara+eng",
        )
        text = engine.extract_text(processed_image)
        return {"filename": filename, "text": text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
