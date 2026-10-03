"""
Omni Medical OCR Pipeline - FastAPI Server
============================================
REST API for programmatic access to the OCR pipeline.
Run with: uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import contextlib
import os
import sys
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

app = FastAPI(
    title="Omni Medical OCR Pipeline API",
    description="REST API for Arabic medical OCR with ensemble engines and AI spell checking",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class OCRRequest(BaseModel):
    """Request model for text-based OCR correction."""
    text: str = Field(..., min_length=1, description="Arabic text to correct")
    engine: str | None = Field(None, description="OCR engine to use (tesseract/easyocr/paddleocr/trocr/ensemble)")
    auto_correct: bool = Field(True, description="Apply automatic spell correction")


class SpellCheckRequest(BaseModel):
    """Request model for spell checking."""
    text: str = Field(..., min_length=1, description="Arabic text to spell check")


class WordResult(BaseModel):
    """Individual word result with confidence."""
    word: str
    confidence: float
    corrected: bool = False
    original: str | None = None


class OCRResponse(BaseModel):
    """Response model for OCR operations."""
    success: bool
    text: str
    confidence: float
    engine_used: str
    processing_time: float
    word_count: int
    corrections_applied: int = 0


class BatchItemResult(BaseModel):
    """Result for a single file in batch processing."""
    filename: str
    text: str
    confidence: float
    processing_time: float
    success: bool
    error: str | None = None


class BatchResponse(BaseModel):
    """Response model for batch OCR operations."""
    total_files: int
    successful: int
    failed: int
    total_time: float
    results: list[BatchItemResult]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    engines_available: list[str]


class EngineInfo(BaseModel):
    """Information about an OCR engine."""
    name: str
    available: bool
    description: str


# ─── Lazy Pipeline Initialization ─────────────────────────────────────────────

_pipeline = None
_spell_checker = None


def get_pipeline():
    """Lazy-initialize the OCR pipeline."""
    global _pipeline
    if _pipeline is None:
        try:
            from src.core.pipeline import OmniMedicalOCR
            _pipeline = OmniMedicalOCR()
        except Exception as e:
            print(f"[WARNING] Pipeline init failed: {e}")
            _pipeline = "unavailable"
    return _pipeline


def get_spell_checker():
    """Lazy-initialize the spell checker."""
    global _spell_checker
    if _spell_checker is None:
        try:
            from src.spellcheck.hybrid_spell_checker import HybridSpellChecker
            _spell_checker = HybridSpellChecker()
        except Exception as e:
            print(f"[WARNING] Spell checker init failed: {e}")
            _spell_checker = "unavailable"
    return _spell_checker


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and available engines."""
    engines = ["tesseract", "easyocr", "paddleocr", "trocr", "ensemble"]
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        engines_available=engines,
    )


@app.get("/engines", response_model=list[EngineInfo])
async def list_engines():
    """List all available OCR engines with their status."""
    engines_info = [
        EngineInfo(name="tesseract", available=True, description="Tesseract OCR with Arabic language support"),
        EngineInfo(name="easyocr", available=True, description="EasyOCR with Arabic+English detection"),
        EngineInfo(name="paddleocr", available=True, description="PaddleOCR with Arabic layout analysis"),
        EngineInfo(name="trocr", available=True, description="Microsoft TrOCR transformer model"),
        EngineInfo(name="ensemble", available=True, description="Weighted ensemble of all engines"),
    ]
    return engines_info


@app.post("/ocr", response_model=OCRResponse)
async def process_ocr(file: UploadFile = File(...), engine: str = "ensemble", auto_correct: bool = True):
    """
    Process an uploaded image or PDF with OCR.

    - **file**: Image (PNG/JPG/TIFF/BMP) or PDF file
    - **engine**: OCR engine to use (default: ensemble)
    - **auto_correct**: Apply spell correction (default: true)
    """
    pipeline = get_pipeline()
    if pipeline == "unavailable":
        raise HTTPException(status_code=503, detail="OCR pipeline is not available")

    start_time = time.time()
    original_text = ""
    corrected_text = ""
    corrections = 0

    try:
        # Save uploaded file to temp location
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Process based on file type
        if tmp_path.lower().endswith(".pdf"):
            result = pipeline.process_pdf(tmp_path)
        else:
            result = pipeline.process_image(tmp_path)

        original_text = result.text if hasattr(result, "text") else str(result)
        confidence = result.confidence if hasattr(result, "confidence") else 0.0
        engine_used = result.engine_name if hasattr(result, "engine_name") else engine

        # Apply spell correction
        if auto_correct:
            checker = get_spell_checker()
            if checker != "unavailable":
                corrected_text, _ = checker.correct_with_confidence(original_text)
                if corrected_text != original_text:
                    # Count word-level changes
                    orig_words = original_text.split()
                    corr_words = corrected_text.split()
                    corrections = sum(
                        1 for a, b in zip(orig_words, corr_words, strict=False) if a != b
                    )
                    original_text = corrected_text

        processing_time = time.time() - start_time

        return OCRResponse(
            success=True,
            text=original_text,
            confidence=confidence,
            engine_used=engine_used,
            processing_time=round(processing_time, 3),
            word_count=len(original_text.split()),
            corrections_applied=corrections,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e!s}")

    finally:
        # Cleanup temp file
        if 'tmp_path' in locals():
            with contextlib.suppress(Exception):
                os.unlink(tmp_path)


@app.post("/ocr/batch", response_model=BatchResponse)
async def process_batch(files: list[UploadFile] = File(...), engine: str = "ensemble"):
    """
    Process multiple uploaded files in batch.

    - **files**: Multiple image or PDF files
    - **engine**: OCR engine to use (default: ensemble)
    """
    pipeline = get_pipeline()
    if pipeline == "unavailable":
        raise HTTPException(status_code=503, detail="OCR pipeline is not available")

    start_time = time.time()
    results = []

    for file in files:
        file_start = time.time()
        try:
            suffix = Path(file.filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            if tmp_path.lower().endswith(".pdf"):
                result = pipeline.process_pdf(tmp_path)
            else:
                result = pipeline.process_image(tmp_path)

            text = result.text if hasattr(result, "text") else str(result)
            confidence = result.confidence if hasattr(result, "confidence") else 0.0

            results.append(BatchItemResult(
                filename=file.filename,
                text=text,
                confidence=confidence,
                processing_time=round(time.time() - file_start, 3),
                success=True,
            ))

        except Exception as e:
            results.append(BatchItemResult(
                filename=file.filename,
                text="",
                confidence=0.0,
                processing_time=round(time.time() - file_start, 3),
                success=False,
                error=str(e),
            ))

        finally:
            if 'tmp_path' in locals():
                with contextlib.suppress(Exception):
                    os.unlink(tmp_path)

    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    return BatchResponse(
        total_files=len(results),
        successful=successful,
        failed=failed,
        total_time=round(time.time() - start_time, 3),
        results=results,
    )


@app.post("/spellcheck", response_model=OCRResponse)
async def spell_check(request: SpellCheckRequest):
    """
    Correct Arabic medical OCR text using the hybrid spell checker.

    - **text**: Arabic text to correct
    """
    checker = get_spell_checker()
    if checker == "unavailable":
        raise HTTPException(status_code=503, detail="Spell checker is not available")

    start_time = time.time()

    try:
        corrected, confidence = checker.correct_with_confidence(request.text)
        corrections = sum(
            1 for a, b in zip(request.text.split(), corrected.split(), strict=False) if a != b
        )

        return OCRResponse(
            success=True,
            text=corrected,
            confidence=confidence,
            engine_used="hybrid-spellchecker",
            processing_time=round(time.time() - start_time, 3),
            word_count=len(corrected.split()),
            corrections_applied=corrections,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spell check failed: {e!s}")


# ─── Run Server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  Omni Medical OCR Pipeline - API Server")
    print("  Running on http://0.0.0.0:8000")
    print("  Docs: http://0.0.0.0:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
