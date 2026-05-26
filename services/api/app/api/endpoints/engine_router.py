"""OCR engine management endpoints for OmniMedicalSuite.

Provides REST endpoints for listing, registering, testing, and benchmarking
OCR engines.  Supports dynamic plugin registration, single and batch document
processing with engine/method selection, and cross-engine benchmarking.

Endpoints
---------
GET  /engines/                  List all available OCR engines
GET  /engines/{engine_name}     Get details of a specific engine
POST /engines/register          Register a new OCR engine plugin
POST /engines/{engine_name}/test  Test an engine with a sample image
GET  /engines/fusion-methods    List available fusion methods
POST /engines/process           Process a document with specific settings
POST /engines/batch             Batch process multiple files
GET  /engines/benchmark         Run benchmark comparison across engines
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/engines", tags=["engines"])

# ---------------------------------------------------------------------------
# Singleton engine registry (lazily populated on first use)
# ---------------------------------------------------------------------------
_engine_registry: dict[str, Any] = {}  # name -> BaseOCREngine instance
_registry_initialised = False


async def _ensure_registry() -> dict[str, Any]:
    """Populate the engine registry if not yet initialised.

    Returns the mapping of engine name to engine instance.
    """
    global _engine_registry, _registry_initialised
    if _registry_initialised:
        return _engine_registry

    from ...core.config import get_settings
    from ...vision.ocr_fusion_system import OCRFusionEngine

    settings = get_settings()
    fusion = OCRFusionEngine(settings)
    fusion.discover_and_register_all()
    _engine_registry.update(fusion.engines)
    _registry_initialised = True

    logger.info("Engine registry initialised with %d engine(s): %s", len(_engine_registry), list(_engine_registry.keys()))
    return _engine_registry


# ===================================================================
# Pydantic models
# ===================================================================

class EngineInfo(BaseModel):
    """Information about a single OCR engine."""

    name: str
    status: str = "unknown"
    supported_languages: list[str] = Field(default_factory=list)
    description: str = ""


class EngineListResponse(BaseModel):
    """List of available OCR engines."""

    engines: list[EngineInfo]
    total: int = 0


class EngineDetailResponse(EngineInfo):
    """Detailed engine information."""

    status: str = "unknown"
    test_result: dict[str, Any] | None = None


class RegisterEngineRequest(BaseModel):
    """Request body for registering a new OCR engine."""

    module_path: str = Field(
        ...,
        description="Full Python module path for the engine class (e.g. 'my_plugin.engines.CustomOCR').",
    )
    class_name: str = Field(
        default="Engine",
        description="Name of the class within the module.",
    )
    engine_name: str | None = Field(
        default=None,
        description="Override the engine name. If None, the class 'name' attribute is used.",
    )


class RegisterEngineResponse(BaseModel):
    """Response after registering a new engine."""

    engine_name: str
    registered: bool
    message: str = ""


class FusionMethodResponse(BaseModel):
    """Available fusion methods."""

    methods: list[dict[str, str]]
    active_method: str = ""


class ProcessRequest(BaseModel):
    """Request body for processing with specific engine settings."""

    engines: list[str] | None = Field(
        default=None,
        description="List of specific engine names. None = all registered.",
    )
    fusion_method: str | None = Field(
        default=None,
        description="Fusion strategy to use.",
    )
    language: str = Field(
        default="eng+ara",
        description="Language hint (e.g. 'eng+ara').",
    )


class ProcessResponse(BaseModel):
    """Response after processing a document."""

    final_text: str = ""
    fusion_method: str = ""
    engine_results: list[dict[str, Any]] = Field(default_factory=list)
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    processing_time_ms: float = 0.0
    word_count: int = 0


class BatchProcessResponse(BaseModel):
    """Response after batch processing multiple files."""

    results: list[ProcessResponse]
    total_files: int = 0
    total_processing_time_ms: float = 0.0


class EngineTestResponse(BaseModel):
    """Result of testing a single engine."""

    engine_name: str
    success: bool
    text: str = ""
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    error: str | None = None


class BenchmarkResult(BaseModel):
    """Benchmark result for a single engine."""

    engine_name: str
    available: bool = False
    text_length: int = 0
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    error: str | None = None


class BenchmarkResponse(BaseModel):
    """Comparison benchmark across all engines."""

    results: list[BenchmarkResult]
    winner: str | None = None
    total_time_ms: float = 0.0


# ===================================================================
# Engine descriptions
# ===================================================================
_ENGINE_DESCRIPTIONS: dict[str, str] = {
    "tesseract": "Open-source OCR engine via pytesseract with strong multilingual support.",
    "easyocr": "GPU-accelerated OCR with 80+ languages. Paragraph-level detection.",
    "paddleocr": "Multilingual OCR by Baidu with excellent Arabic support.",
    "trocr": "HuggingFace Transformer-based OCR, optimised for handwritten text.",
    "surya": "Modern multilingual OCR with strong Arabic layout analysis.",
}


def _get_description(name: str) -> str:
    """Return a human-readable description for a known engine, or a generic one."""
    return _ENGINE_DESCRIPTIONS.get(name, f"Custom OCR engine: {name}")


# ===================================================================
# Endpoints
# ===================================================================

@router.get("/", response_model=EngineListResponse, summary="List all available OCR engines")
async def list_engines() -> EngineListResponse:
    """Return a list of all discovered OCR engines with their availability status."""
    registry = await _ensure_registry()
    engines = []

    for name, engine_instance in registry.items():
        try:
            available = engine_instance.is_available()
        except Exception:
            available = False

        engines.append(
            EngineInfo(
                name=name,
                status="available" if available else "unavailable",
                supported_languages=getattr(engine_instance, "supported_languages", []),
                description=_get_description(name),
            )
        )

    return EngineListResponse(engines=engines, total=len(engines))


@router.get("/fusion-methods", response_model=FusionMethodResponse, summary="List available fusion methods")
async def list_fusion_methods() -> FusionMethodResponse:
    """Return all available fusion strategies with descriptions."""
    from ...core.config import get_settings

    settings = get_settings()

    methods = [
        {"name": "weighted_vote", "description": "Confidence-weighted majority voting on words."},
        {"name": "character_level", "description": "Character-by-character consensus across engines."},
        {"name": "best_confidence", "description": "Selects output from the highest-confidence engine."},
        {"name": "smart_fallback", "description": "Best-confidence when one engine dominates; weighted vote otherwise."},
    ]

    return FusionMethodResponse(
        methods=methods,
        active_method=str(settings.OCR_FUSION_METHOD.value),
    )


@router.get("/{engine_name}", response_model=EngineDetailResponse, summary="Get engine details")
async def get_engine(engine_name: str) -> EngineDetailResponse:
    """Retrieve detailed information about a specific OCR engine.

    Raises
    ------
    404
        If the engine is not registered.
    """
    registry = await _ensure_registry()

    engine_instance = registry.get(engine_name)
    if engine_instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine '{engine_name}' is not registered. "
                   f"Available: {sorted(registry.keys())}",
        )

    try:
        available = engine_instance.is_available()
    except Exception:
        available = False

    return EngineDetailResponse(
        name=engine_name,
        status="available" if available else "unavailable",
        supported_languages=getattr(engine_instance, "supported_languages", []),
        description=_get_description(engine_name),
    )


@router.post("/register", response_model=RegisterEngineResponse, summary="Register a new OCR engine")
async def register_engine(body: RegisterEngineRequest) -> RegisterEngineResponse:
    """Register a new OCR engine from an external Python module.

    The engine class must extend :class:`BaseOCREngine` and implement
    ``recognize()`` and ``is_available()``.

    Raises
    ------
    400
        If the module or class cannot be imported, or if the class does not
        extend :class:`BaseOCREngine`.
    """
    from ...vision.ocr_fusion_system import BaseOCREngine

    try:
        import importlib
        module = importlib.import_module(body.module_path)
        engine_class = getattr(module, body.class_name)
    except (ImportError, AttributeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to import '{body.module_path}.{body.class_name}': {exc}",
        ) from exc

    try:
        instance = engine_class()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to instantiate engine class: {exc}",
        ) from exc

    if not isinstance(instance, BaseOCREngine):
        raise HTTPException(
            status_code=400,
            detail=f"Class '{body.class_name}' does not extend BaseOCREngine.",
        )

    engine_name = body.engine_name or getattr(instance, "name", body.class_name)
    _engine_registry[engine_name] = instance

    available = instance.is_available()
    logger.info("Registered custom engine '%s' (available=%s)", engine_name, available)

    return RegisterEngineResponse(
        engine_name=engine_name,
        registered=True,
        message=f"Engine '{engine_name}' registered successfully ({'available' if available else 'unavailable'}).",
    )


@router.post("/{engine_name}/test", response_model=EngineTestResponse, summary="Test an engine")
async def test_engine(
    engine_name: str,
    file: UploadFile = File(..., description="Sample image to test with"),
) -> EngineTestResponse:
    """Run a single OCR engine on a sample image and return results.

    Raises
    ------
    404
        If the engine is not registered.
    400
        If the engine is not available.
    """
    registry = await _ensure_registry()
    engine_instance = registry.get(engine_name)
    if engine_instance is None:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_name}' not registered.")

    if not engine_instance.is_available():
        raise HTTPException(
            status_code=400,
            detail=f"Engine '{engine_name}' is not available (missing dependencies).",
        )

    # Save the uploaded file to a temporary location
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    suffix = os.path.splitext(file.filename or ".png")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        t0 = time.perf_counter()
        result = await engine_instance.recognize(tmp_path)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        return EngineTestResponse(
            engine_name=engine_name,
            success=True,
            text=result.text,
            confidence=result.confidence,
            processing_time_ms=round(elapsed_ms, 2),
        )
    except Exception as exc:
        logger.error("Engine test failed for '%s': %s", engine_name, exc)
        return EngineTestResponse(
            engine_name=engine_name,
            success=False,
            error=str(exc),
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/process", response_model=ProcessResponse, summary="Process a document with specific engine settings")
async def process_document(
    file: UploadFile = File(..., description="Image or PDF to process"),
    engines: list[str] | None = None,
    fusion_method: str | None = None,
    language: str = "eng+ara",
) -> ProcessResponse:
    """Process a document using specified engines and fusion method.

    Parameters
    ----------
    file:
        The uploaded document file.
    engines:
        Optional list of specific engine names. If None, all registered
        engines are used.
    fusion_method:
        Optional fusion strategy override. If None, the default from
        configuration is used.
    language:
        Language hint string (default: ``eng+ara``).

    Raises
    ------
    400
        If the file is empty or no engines are available.
    """
    from ...vision.ocr_fusion_system import OCRFusionEngine, BaseOCREngine
    from ...core.config import get_settings

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Save to temporary file
    suffix = os.path.splitext(file.filename or ".png")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        settings = get_settings()
        fusion = OCRFusionEngine(settings)

        if engines:
            registry = await _ensure_registry()
            for eng_name in engines:
                instance = registry.get(eng_name)
                if instance is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Engine '{eng_name}' not registered.",
                    )
                fusion.register_engine(instance)
        else:
            fusion.discover_and_register_all()

        if not fusion.engines:
            raise HTTPException(
                status_code=400,
                detail="No OCR engines available.",
            )

        if fusion_method and fusion_method in fusion._VALID_METHODS:
            fusion.fusion_method = fusion_method

        t0 = time.perf_counter()
        result = await fusion.process(tmp_path, lang=language)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        engine_results = [
            {
                "engine_name": r.engine_name,
                "confidence": r.confidence,
                "processing_time_ms": r.processing_time_ms,
                "language_detected": r.language_detected,
            }
            for r in result.engine_results
        ]

        return ProcessResponse(
            final_text=result.final_text,
            fusion_method=result.fusion_method,
            engine_results=engine_results,
            confidence_scores=result.confidence_scores,
            processing_time_ms=round(elapsed_ms, 2),
            word_count=result.word_count,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Processing failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {exc}",
        ) from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/batch", response_model=BatchProcessResponse, summary="Batch process multiple files")
async def batch_process(
    files: list[UploadFile] = File(..., description="Multiple image/PDF files"),
    engines: list[str] | None = None,
    fusion_method: str | None = None,
    language: str = "eng+ara",
) -> BatchProcessResponse:
    """Process multiple files in a single request.

    Each file is processed independently through the OCR fusion pipeline.

    Raises
    ------
    400
        If no files are provided or no engines are available.
    """
    from ...vision.ocr_fusion_system import OCRFusionEngine
    from ...core.config import get_settings

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    settings = get_settings()
    fusion = OCRFusionEngine(settings)

    if engines:
        registry = await _ensure_registry()
        for eng_name in engines:
            instance = registry.get(eng_name)
            if instance:
                fusion.register_engine(instance)
    else:
        fusion.discover_and_register_all()

    if not fusion.engines:
        raise HTTPException(status_code=400, detail="No OCR engines available.")

    if fusion_method and fusion_method in fusion._VALID_METHODS:
        fusion.fusion_method = fusion_method

    t_start = time.perf_counter()
    results: list[ProcessResponse] = []

    for file in files:
        content = await file.read()
        if not content:
            continue

        suffix = os.path.splitext(file.filename or ".png")[1] or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            t0 = time.perf_counter()
            result = await fusion.process(tmp_path, lang=language)
            elapsed = (time.perf_counter() - t0) * 1000

            results.append(ProcessResponse(
                final_text=result.final_text,
                fusion_method=result.fusion_method,
                engine_results=[
                    {
                        "engine_name": r.engine_name,
                        "confidence": r.confidence,
                        "processing_time_ms": r.processing_time_ms,
                    }
                    for r in result.engine_results
                ],
                confidence_scores=result.confidence_scores,
                processing_time_ms=round(elapsed, 2),
                word_count=result.word_count,
            ))
        except Exception as exc:
            logger.error("Batch item failed (%s): %s", file.filename, exc)
            results.append(ProcessResponse(
                final_text="",
                fusion_method=fusion.fusion_method,
            ))
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    total_ms = (time.perf_counter() - t_start) * 1000

    return BatchProcessResponse(
        results=results,
        total_files=len(files),
        total_processing_time_ms=round(total_ms, 2),
    )


@router.get("/benchmark", response_model=BenchmarkResponse, summary="Run benchmark across all engines")
async def benchmark_engines(
    file: UploadFile | None = File(default=None, description="Optional image for benchmarking"),
) -> BenchmarkResponse:
    """Run each registered OCR engine on a sample image and compare results.

    If no file is provided, a synthetic test image is generated internally.

    Returns timing, confidence, and text-length metrics for each engine.
    """
    registry = await _ensure_registry()

    if not registry:
        raise HTTPException(status_code=400, detail="No OCR engines registered.")

    # Prepare test image
    if file:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        suffix = os.path.splitext(file.filename or ".png")[1] or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
    else:
        # Generate a synthetic test image
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.new("RGB", (800, 600), color="white")
            draw = ImageDraw.Draw(img)
            sample_text = (
                "Patient Medical Report\n"
                "Patient Name: Test Patient\n"
                "Diagnosis: Type 2 Diabetes\n"
                "Medication: Metformin 500mg\n"
                "Date: 2024-01-15"
            )
            draw.text((50, 50), sample_text, fill="black")

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            img.save(tmp.name)
            tmp_path = tmp.name
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Cannot generate test image (PIL not installed). Please provide a file.",
            )

    try:
        t_total_start = time.perf_counter()
        bench_results: list[BenchmarkResult] = []

        for name, engine_instance in registry.items():
            try:
                available = engine_instance.is_available()
            except Exception:
                available = False

            if not available:
                bench_results.append(BenchmarkResult(
                    engine_name=name,
                    available=False,
                ))
                continue

            try:
                t0 = time.perf_counter()
                result = await engine_instance.recognize(tmp_path)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                bench_results.append(BenchmarkResult(
                    engine_name=name,
                    available=True,
                    text_length=len(result.text),
                    confidence=result.confidence,
                    processing_time_ms=round(elapsed_ms, 2),
                ))
            except Exception as exc:
                bench_results.append(BenchmarkResult(
                    engine_name=name,
                    available=True,
                    error=str(exc),
                ))

        total_ms = (time.perf_counter() - t_total_start) * 1000

        # Determine winner (fastest with highest confidence)
        successful = [b for b in bench_results if b.available and not b.error]
        winner = None
        if successful:
            winner = max(successful, key=lambda b: b.confidence).engine_name

        return BenchmarkResponse(
            results=bench_results,
            winner=winner,
            total_time_ms=round(total_ms, 2),
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
