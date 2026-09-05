"""Hardened FastAPI OCR upload route."""
from __future__ import annotations
import logging, os, tempfile
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, ImageFile, UnidentifiedImageError
from src.processors.image_processor import MedicalImageProcessor
from src.processors.ocr_engine import MedicalOCREngine

router=APIRouter(); log=logging.getLogger(__name__)
ALLOWED_EXTENSIONS={".png",".jpg",".jpeg",".tif",".tiff",".bmp"}
MAX_UPLOAD_SIZE=10*1024*1024
MAX_IMAGE_PIXELS=40_000_000
MAX_IMAGE_SIDE=10_000
UPLOAD_CHUNK_SIZE=1024*1024
Image.MAX_IMAGE_PIXELS=MAX_IMAGE_PIXELS
ImageFile.LOAD_TRUNCATED_IMAGES=False

def _validate_image(path:str)->None:
    try:
        with Image.open(path) as image:
            width,height=image.size
            if width<1 or height<1 or width>MAX_IMAGE_SIDE or height>MAX_IMAGE_SIDE or width*height>MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions exceed policy")
            image.verify()
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400,detail="Invalid or unsupported image") from exc

@router.post("/ocr/process")
async def process_image(file:UploadFile=File(...)):
    filename=file.filename or "upload.png"; suffix=Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,detail="Unsupported file type")
    tmp_path=None; total=0
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix,delete=False) as tmp:
            tmp_path=tmp.name
            try: os.chmod(tmp_path,0o600)
            except OSError: pass
            while True:
                chunk=await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk: break
                total+=len(chunk)
                if total>MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413,detail="File too large")
                tmp.write(chunk)
            tmp.flush()
        _validate_image(tmp_path)
        processed=MedicalImageProcessor.full_pipeline(tmp_path)
        engine=MedicalOCREngine(languages=("ar","en"),use_easyocr=True,tesseract_lang="ara+eng")
        return {"filename":filename,"text":engine.extract_text(processed)}
    except HTTPException: raise
    except Exception:
        log.exception("OCR processing failed")
        raise HTTPException(status_code=500,detail="OCR processing failed")
    finally:
        await file.close()
        if tmp_path:
            try: os.unlink(tmp_path)
            except FileNotFoundError: pass
