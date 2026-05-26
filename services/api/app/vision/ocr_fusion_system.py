"""
OCR Fusion System for Omni-Medical Suite
==========================================

A comprehensive OCR fusion, semantic deduplication, and medical knowledge graph
system designed for multilingual (English/Arabic) medical document processing.

Modules:
    - Data Models: Pydantic models for OCR output, bounding boxes, chunks, clusters,
      medical entities, relations, and knowledge graphs.
    - OCR Engines: Five pluggable OCR backends (Tesseract, EasyOCR, PaddleOCR,
      TrOCR, Surya) extending a common abstract base.
    - OCRFusionEngine: Multi-engine orchestration with four fusion strategies
      (weighted vote, character-level consensus, best confidence, smart fallback).
    - SemanticDeduplicationEngine: Embedding-based deduplication using
      sentence-transformers and FAISS IVFFlat indexing with DBSCAN clustering.
    - MedicalKnowledgeGraph: Regex and NLP-based extraction of medical entities
      (diagnoses, medications, procedures, anatomy, dates, values) and their
      relations, with optional NetworkX visualisation.
    - OmniMedicalPipeline: End-to-end orchestrator that wires OCR → dedup → KG.

Author: Omni-Medical Suite Team
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Pydantic (graceful import – allow running without pydantic for testing)
# ---------------------------------------------------------------------------
try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Minimal shim so type-checking still works; real code-path always has pydantic
    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self):
            return self.__dict__

        def model_dump_json(self):
            return json.dumps(self.__dict__, default=str, ensure_ascii=False)

    class Field:  # type: ignore[no-redef]
        def __init__(self, default=None, **kw):
            self.default = default

    def field_validator(*_args, **_kw):
        def decorator(fn):
            return fn
        return decorator


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("ocr_fusion_system")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ============================================================================
# SECTION 1 – Data Models
# ============================================================================


class BoundingBox(BaseModel):
    """Axis-aligned bounding box for a detected text region.

    Attributes:
        x: Horizontal offset from the left edge (pixels).
        y: Vertical offset from the top edge (pixels).
        w: Width of the region (pixels).
        h: Height of the region (pixels).
    """

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(ge=0)
    h: int = Field(ge=0)

    @property
    def area(self) -> int:
        """Return the area of the bounding box in square pixels."""
        return self.w * self.h

    @property
    def center(self) -> Tuple[int, int]:
        """Return the center point ``(cx, cy)``."""
        return (self.x + self.w // 2, self.y + self.h // 2)

    def iou(self, other: "BoundingBox") -> float:
        """Compute intersection-over-union with another bounding box."""
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x + self.w, other.x + other.w)
        y2 = min(self.y + self.h, other.y + other.h)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


class OCROutput(BaseModel):
    """Result from a single OCR engine.

    Attributes:
        engine_name: Identifier of the engine that produced this output.
        text: Recognised text content.
        confidence: Overall confidence score in the range [0, 1].
        regions: Bounding boxes for detected text regions.
        processing_time_ms: Wall-clock time the engine took (milliseconds).
        language_detected: Detected language code (e.g. ``'eng'``, ``'ara'``).
    """

    engine_name: str
    text: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    regions: List[BoundingBox] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    language_detected: str = "eng"


class FusedResult(BaseModel):
    """Result after fusing multiple OCR engine outputs.

    Attributes:
        final_text: The combined / consensus text.
        fusion_method: Name of the fusion strategy used.
        engine_results: Individual engine results before fusion.
        confidence_scores: Per-engine confidence mapping.
        processing_time_ms: Total fusion pipeline time (milliseconds).
        word_count: Number of words in ``final_text``.
    """

    final_text: str = ""
    fusion_method: str = ""
    engine_results: List[OCROutput] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    processing_time_ms: float = 0.0
    word_count: int = 0

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.word_count = len(self.final_text.split())


class DocumentChunk(BaseModel):
    """A textual chunk extracted from a document for deduplication.

    Attributes:
        chunk_id: Unique identifier (UUID).
        text: Chunk text content.
        page_num: Source page number (1-indexed).
        chunk_index: Sequential index within the page.
        embedding: Dense embedding vector (lazy-populated).
        metadata: Arbitrary key-value metadata.
    """

    chunk_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str = ""
    page_num: int = 1
    chunk_index: int = 0
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticCluster(BaseModel):
    """A group of semantically similar document chunks.

    Attributes:
        cluster_id: Unique cluster identifier.
        chunks: Member chunks.
        representative_text: The most representative text from the cluster.
        centroid_embedding: Mean embedding of all members.
        similarity_score: Average pairwise cosine similarity.
    """

    cluster_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    chunks: List[DocumentChunk] = Field(default_factory=list)
    representative_text: str = ""
    centroid_embedding: List[float] = Field(default_factory=list)
    similarity_score: float = 0.0


class EntityType(str, Enum):
    """Supported medical entity types."""
    DIAGNOSIS = "DIAGNOSIS"
    MEDICATION = "MEDICATION"
    PROCEDURE = "PROCEDURE"
    ANATOMY = "ANATOMY"
    DATE = "DATE"
    VALUE = "VALUE"


class MedicalEntity(BaseModel):
    """An extracted medical entity.

    Attributes:
        entity_type: The category of the entity.
        text: The matched text span.
        confidence: Extraction confidence [0, 1].
        position: ``(start, end)`` character offsets in source text.
        metadata: Additional info (e.g. dosage for medications).
    """

    entity_type: EntityType
    text: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    position: Tuple[int, int] = (0, 0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Relation(BaseModel):
    """A binary relation between two medical entities.

    Attributes:
        subject: Text of the subject entity.
        predicate: Relation type (e.g. ``DIAGNOSED_WITH``).
        object: Text of the object entity.
        confidence: Relation confidence [0, 1].
    """

    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class KnowledgeGraph(BaseModel):
    """A small medical knowledge graph extracted from a single document.

    Attributes:
        entities: Extracted entities.
        relations: Extracted relations.
        metadata: Provenance / processing metadata.
    """

    entities: List[MedicalEntity] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# SECTION 2 – OCR Engine Implementations
# ============================================================================


class BaseOCREngine(ABC):
    """Abstract base class for all OCR engines.

    Every concrete engine must implement :meth:`recognize` and :meth:`is_available`.
    The default :meth:`preprocess` pipeline applies grayscale conversion, Gaussian
    denoising, adaptive thresholding, and optional deskewing.
    """

    name: str = "base"
    supported_languages: List[str] = ["eng"]

    @abstractmethod
    async def recognize(
        self, image_path: str, lang: str = "eng+ara"
    ) -> OCROutput:
        """Run OCR on an image file and return structured output.

        Args:
            image_path: Absolute path to the image (or ``np.ndarray``).
            lang: Language hint string (e.g. ``'eng+ara'``).

        Returns:
            An :class:`OCROutput` instance with text, confidence, and regions.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the underlying OCR library is installed."""

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Apply a standard image preprocessing pipeline.

        Steps:
            1. Convert to grayscale (if not already).
            2. Gaussian blur for denoising (kernel=3).
            3. Otsu's thresholding for binarisation.
            4. Morphological thinning to remove small noise.
            5. Deskew via projection profile (if OpenCV available).

        Args:
            image: BGR or grayscale ``np.ndarray``.

        Returns:
            Preprocessed grayscale ``np.ndarray`` (uint8).
        """
        try:
            import cv2

            # 1. Grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # 2. Gaussian denoise
            gray = cv2.GaussianBlur(gray, (3, 3), 0)

            # 3. Adaptive threshold (better for uneven lighting)
            binary = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 8,
            )

            # 4. Morphological opening – remove small noise
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

            # 5. Deskew using minAreaRect on white pixels
            coords = np.column_stack(np.where(binary > 0))
            if len(coords) > 100:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                if abs(angle) > 0.5:
                    (h_img, w_img) = gray.shape
                    center = (w_img // 2, h_img // 2)
                    M = cv2.getRotationMatrix2D(center, angle, 1.0)
                    gray = cv2.warpAffine(gray, M, (w_img, h_img), flags=cv2.INTER_CUBIC)

            return gray
        except ImportError:
            logger.warning("OpenCV not available – skipping image preprocessing")
            return image


# ---------------------------------------------------------------------------
# 1. Tesseract Engine
# ---------------------------------------------------------------------------

class TesseractEngine(BaseOCREngine):
    """OCR engine backed by **Tesseract** via ``pytesseract``.

    Supports English and Arabic. Returns word-level bounding boxes by querying
    ``tesseract.image_to_data``.
    """

    name = "tesseract"
    supported_languages = ["eng", "ara"]

    def is_available(self) -> bool:
        """Check whether ``pytesseract`` and the ``tesseract`` binary are present."""
        try:
            import pytesseract  # noqa: F401
            import shutil
            return shutil.which("tesseract") is not None
        except ImportError:
            return False

    async def recognize(
        self, image_path: str, lang: str = "eng+ara"
    ) -> OCROutput:
        """Recognise text using Tesseract with word-level bounding boxes.

        Args:
            image_path: Path to the image file on disk.
            lang: Tesseract language string.

        Returns:
            :class:`OCROutput` with word-level regions.

        Raises:
            RuntimeError: If Tesseract is not installed.
        """
        import pytesseract

        t0 = time.perf_counter()

        if not self.is_available():
            raise RuntimeError("Tesseract OCR is not installed or not on PATH")

        try:
            import cv2
            image = cv2.imread(image_path)
            if image is None:
                raise FileNotFoundError(f"Cannot read image: {image_path}")
            processed = self.preprocess(image)
        except ImportError:
            from PIL import Image
            processed = np.array(Image.open(image_path).convert("L"))

        # Run OCR with bounding-box data
        data = pytesseract.image_to_data(
            processed, lang=lang, output_type=pytesseract.Output.DICT,
        )

        regions: List[BoundingBox] = []
        words: List[str] = []
        confs: List[float] = []

        for i, word_text in enumerate(data["text"]):
            conf = int(data["conf"][i])
            if conf > 0 and word_text.strip():
                words.append(word_text.strip())
                confs.append(conf / 100.0)
                regions.append(BoundingBox(
                    x=data["left"][i],
                    y=data["top"][i],
                    w=data["width"][i],
                    h=data["height"][i],
                ))

        full_text = pytesseract.image_to_string(processed, lang=lang).strip()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        avg_conf = float(np.mean(confs)) if confs else 0.0

        return OCROutput(
            engine_name=self.name,
            text=full_text,
            confidence=avg_conf,
            regions=regions,
            processing_time_ms=elapsed_ms,
            language_detected=self._detect_language(full_text),
        )

    @staticmethod
    def _detect_language(text: str) -> str:
        """Simple heuristic to detect dominant language."""
        if not text:
            return "eng"
        arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        ratio = arabic_chars / max(len(text), 1)
        return "ara" if ratio > 0.3 else "eng"


# ---------------------------------------------------------------------------
# 2. EasyOCR Engine
# ---------------------------------------------------------------------------

class EasyOCREngine(BaseOCREngine):
    """OCR engine backed by **EasyOCR**.

    GPU-aware – falls back to CPU when CUDA is unavailable. Returns
    paragraph-level text regions.
    """

    name = "easyocr"
    supported_languages = ["en", "ar"]

    def __init__(self) -> None:
        self._reader: Any = None

    def _get_reader(self, lang: str = "en,ar") -> Any:
        """Lazy-load the EasyOCR ``Reader`` singleton."""
        if self._reader is None:
            import easyocr
            langs = [l.strip() for l in lang.replace("+", ",").split(",") if l.strip()]
            gpu = self._has_cuda()
            logger.info("Initialising EasyOCR (GPU=%s, langs=%s)", gpu, langs)
            self._reader = easyocr.Reader(langs, gpu=gpu)
        return self._reader

    @staticmethod
    def _has_cuda() -> bool:
        """Check CUDA availability."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Return ``True`` if ``easyocr`` is importable."""
        try:
            import easyocr  # noqa: F401
            return True
        except ImportError:
            return False

    async def recognize(
        self, image_path: str, lang: str = "eng+ara"
    ) -> OCROutput:
        """Recognise text using EasyOCR.

        Args:
            image_path: Path to the image file.
            lang: Language hint (``'eng+ara'`` → ``'en,ar'``).

        Returns:
            :class:`OCROutput` with paragraph-level regions.
        """
        t0 = time.perf_counter()
        reader = self._get_reader(lang)

        loop = asyncio.get_event_loop()
        raw_results = await loop.run_in_executor(
            None, reader.readtext, image_path
        )

        regions: List[BoundingBox] = []
        texts: List[str] = []
        confs: List[float] = []

        for (bbox_points, text, conf) in raw_results:
            xs = [p[0] for p in bbox_points]
            ys = [p[1] for p in bbox_points]
            x, y = int(min(xs)), int(min(ys))
            w, h = int(max(xs)) - x, int(max(ys)) - y
            regions.append(BoundingBox(x=x, y=y, w=w, h=h))
            texts.append(text.strip())
            confs.append(float(conf))

        full_text = "\n".join(texts)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        avg_conf = float(np.mean(confs)) if confs else 0.0

        return OCROutput(
            engine_name=self.name,
            text=full_text,
            confidence=avg_conf,
            regions=regions,
            processing_time_ms=elapsed_ms,
            language_detected=TesseractEngine._detect_language(full_text),
        )


# ---------------------------------------------------------------------------
# 3. PaddleOCR Engine
# ---------------------------------------------------------------------------

class PaddleOCREngine(BaseOCREngine):
    """OCR engine backed by **PaddleOCR**.

    Multilingual support with line-level output regions.
    """

    name = "paddleocr"
    supported_languages = ["en", "ar", "ch", "ja", "ko"]

    def __init__(self) -> None:
        self._ocr: Any = None

    def _get_ocr(self, lang: str = "en") -> Any:
        """Lazy-load the PaddleOCR instance."""
        if self._ocr is None:
            from paddleocr import PaddleOCR as _PaddleOCR
            use_gpu = self._has_cuda()
            lang_map = {"eng": "en", "ara": "ar", "ar": "ar"}
            paddle_lang = "ar" if "ar" in lang.lower() else "en"
            logger.info("Initialising PaddleOCR (GPU=%s, lang=%s)", use_gpu, paddle_lang)
            self._ocr = _PaddleOCR(
                use_angle_cls=True,
                lang=paddle_lang,
                use_gpu=use_gpu,
                show_log=False,
            )
        return self._ocr

    @staticmethod
    def _has_cuda() -> bool:
        """Check CUDA availability via paddle framework."""
        try:
            import paddle
            return paddle.device.is_compiled_with_cuda()
        except Exception:
            return False

    def is_available(self) -> bool:
        """Return ``True`` if ``paddleocr`` is importable."""
        try:
            import paddleocr  # noqa: F401
            return True
        except ImportError:
            return False

    async def recognize(
        self, image_path: str, lang: str = "eng+ara"
    ) -> OCROutput:
        """Recognise text using PaddleOCR.

        Args:
            image_path: Path to the image file.
            lang: Language hint.

        Returns:
            :class:`OCROutput` with line-level regions.
        """
        t0 = time.perf_counter()
        ocr = self._get_ocr(lang)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ocr.ocr, image_path)

        regions: List[BoundingBox] = []
        texts: List[str] = []
        confs: List[float] = []

        if result and result[0]:
            for line in result[0]:
                box, (text, conf) = line[0], (line[1][0], line[1][1])
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                x, y = int(min(xs)), int(min(ys))
                w, h = int(max(xs)) - x, int(max(ys)) - y
                regions.append(BoundingBox(x=x, y=y, w=w, h=h))
                texts.append(text.strip())
                confs.append(float(conf))

        full_text = "\n".join(texts)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        avg_conf = float(np.mean(confs)) if confs else 0.0

        return OCROutput(
            engine_name=self.name,
            text=full_text,
            confidence=avg_conf,
            regions=regions,
            processing_time_ms=elapsed_ms,
            language_detected=TesseractEngine._detect_language(full_text),
        )


# ---------------------------------------------------------------------------
# 4. TrOCR Engine (Handwriting)
# ---------------------------------------------------------------------------

class TrOCREngine(BaseOCREngine):
    """OCR engine backed by **HuggingFace TrOCR**.

    Best suited for handwritten text. Uses ``microsoft/trocr-base-handwritten``
    by default. The processor and model are lazy-loaded to avoid long startup.
    """

    name = "trocr"
    supported_languages = ["eng"]

    def __init__(self, model_name: str = "microsoft/trocr-base-handwritten") -> None:
        self._model_name = model_name
        self._processor: Any = None
        self._model: Any = None

    def _load_model(self) -> Tuple[Any, Any]:
        """Lazy-load the TrOCR processor and model."""
        if self._processor is None or self._model is None:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            logger.info("Loading TrOCR model: %s", self._model_name)
            self._processor = TrOCRProcessor.from_pretrained(self._model_name)
            self._model = VisionEncoderDecoderModel.from_pretrained(self._model_name)
        return self._processor, self._model

    def is_available(self) -> bool:
        """Return ``True`` if ``transformers`` is importable."""
        try:
            import transformers  # noqa: F401
            return True
        except ImportError:
            return False

    async def recognize(
        self, image_path: str, lang: str = "eng+ara"
    ) -> OCROutput:
        """Recognise handwriting using TrOCR.

        The image is processed line-by-line via projection-profile segmentation.

        Args:
            image_path: Path to the image file.
            lang: Language hint (TrOCR primarily supports English).

        Returns:
            :class:`OCROutput` with full-page text.
        """
        t0 = time.perf_counter()
        processor, model = self._load_model()

        try:
            import cv2
            image = cv2.imread(image_path)
            if image is None:
                raise FileNotFoundError(f"Cannot read image: {image_path}")
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            # Binarise for cleaner line segmentation
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        except ImportError:
            from PIL import Image
            pil_img = Image.open(image_path).convert("L")
            binary = np.array(pil_img)
            binary = 255 - binary  # invert

        # Simple line segmentation via horizontal projection
        line_images = self._segment_lines(binary)

        lines_text: List[str] = []
        for line_img in line_images:
            if line_img.size == 0:
                continue
            # Ensure 3-channel for processor
            if len(line_img.shape) == 2:
                line_img_pil = Image.fromarray(255 - line_img).convert("RGB")
            else:
                line_img_pil = Image.fromarray(255 - line_img[:, :, 0]).convert("RGB")

            pixel_values = processor(line_img_pil, return_tensors="pt").pixel_values
            loop = asyncio.get_event_loop()
            generated_ids = await loop.run_in_executor(
                None, lambda: model.generate(pixel_values)
            )
            decoded = processor.batch_decode(generated_ids, skip_special_tokens=True)
            lines_text.extend(decoded)

        full_text = "\n".join(lines_text)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        return OCROutput(
            engine_name=self.name,
            text=full_text,
            confidence=0.75,  # TrOCR does not expose per-token confidence easily
            regions=[],  # line-level regions could be populated with more work
            processing_time_ms=elapsed_ms,
            language_detected="eng",
        )

    @staticmethod
    def _segment_lines(binary: np.ndarray) -> List[np.ndarray]:
        """Segment a binarised image into horizontal text lines.

        Uses horizontal projection profile to find white-space gaps and
        splits the image into individual line strips.

        Args:
            binary: Inverted binary image (text=255, background=0).

        Returns:
            List of 2-D ``np.ndarray`` line images.
        """
        h_proj = np.sum(binary, axis=1)
        lines: List[np.ndarray] = []
        in_line = False
        start = 0

        for y, count in enumerate(h_proj):
            if count > 0 and not in_line:
                in_line = True
                start = y
            elif count == 0 and in_line:
                in_line = False
                if y - start > 5:  # ignore very short strips (noise)
                    lines.append(binary[start:y, :])

        # Capture final line
        if in_line and binary.shape[0] - start > 5:
            lines.append(binary[start:, :])

        return lines


# ---------------------------------------------------------------------------
# 5. Surya OCR Engine
# ---------------------------------------------------------------------------

class SuryaEngine(BaseOCREngine):
    """OCR engine backed by **Surya OCR**.

    A modern multilingual OCR engine with strong Arabic support.
    """

    name = "surya"
    supported_languages = ["en", "ar", "ch", "ja", "ko", "hi", "ru"]

    def __init__(self) -> None:
        self._ocr: Any = None

    def _get_ocr(self) -> Any:
        """Lazy-load the Surya OCR instance."""
        if self._ocr is None:
            try:
                from surya.ocr import OCR as _SuryaOCR
                logger.info("Initialising Surya OCR")
                self._ocr = _SuryaOCR()
            except ImportError:
                try:
                    from surya.recognition import RecognitionModel
                    from surya.detection import DetectionModel
                    logger.info("Initialising Surya via component models")
                    self._ocr = {
                        "recognizer": RecognitionModel(),
                        "detector": DetectionModel(),
                    }
                except ImportError:
                    raise RuntimeError("Surya OCR is not installed")
        return self._ocr

    def is_available(self) -> bool:
        """Return ``True`` if ``surya`` is importable."""
        try:
            import surya  # noqa: F401
            return True
        except ImportError:
            return False

    async def recognize(
        self, image_path: str, lang: str = "eng+ara"
    ) -> OCROutput:
        """Recognise text using Surya OCR.

        Args:
            image_path: Path to the image file.
            lang: Language hint.

        Returns:
            :class:`OCROutput` with detected text and regions.
        """
        t0 = time.perf_counter()
        ocr = self._get_ocr()

        try:
            from PIL import Image
            image = Image.open(image_path)
        except Exception as exc:
            raise FileNotFoundError(f"Cannot open image {image_path}: {exc}") from exc

        # Try the high-level API first
        if callable(ocr):
            loop = asyncio.get_event_loop()
            predictions = await loop.run_in_executor(None, ocr.run, [image], [lang])
            texts = []
            regions = []
            for pred in predictions:
                for line in pred.text_lines:
                    texts.append(line.text)
                    b = line.bbox
                    x1, y1 = int(b[0]), int(b[1])
                    x2, y2 = int(b[2]), int(b[3])
                    regions.append(BoundingBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1))
        else:
            # Fallback to component-level API
            texts, regions = await self._recognize_components(ocr, image, lang)

        full_text = "\n".join(texts)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        return OCROutput(
            engine_name=self.name,
            text=full_text,
            confidence=0.85,  # Surya doesn't expose fine-grained confidence
            regions=regions,
            processing_time_ms=elapsed_ms,
            language_detected=TesseractEngine._detect_language(full_text),
        )

    async def _recognize_components(
        self, ocr: Dict[str, Any], image: Any, lang: str
    ) -> Tuple[List[str], List[BoundingBox]]:
        """Use the component-level Surya API (detector + recognizer)."""
        detector = ocr["detector"]
        recognizer = ocr["recognizer"]
        loop = asyncio.get_event_loop()

        detections = await loop.run_in_executor(None, detector.run, [image])
        texts: List[str] = []
        regions: List[BoundingBox] = []

        for det in detections:
            text_pred = await loop.run_in_executor(
                None, recognizer.run, [image], [det]
            )
            for tp in text_pred:
                texts.append(tp.text)
                b = tp.bbox
                x1, y1 = int(b[0]), int(b[1])
                x2, y2 = int(b[2]), int(b[3])
                regions.append(BoundingBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1))

        return texts, regions


# ============================================================================
# SECTION 3 – OCR Fusion Engine
# ============================================================================


class OCRFusionEngine:
    """Multi-engine OCR fusion orchestrator.

    Registers available OCR backends, runs them in parallel via a
    ``ThreadPoolExecutor``, and combines results using one of four strategies:

    * ``weighted_vote`` – confidence-weighted majority voting.
    * ``character_level_consensus`` – character-by-character voting.
    * ``best_confidence`` – selects the output from the highest-confidence engine.
    * ``smart_fallback`` – tries best-confidence, falls back to voting.

    Args:
        config: An :class:`OmniFileConfig`-like object. Must expose
            ``OCR_FUSION_METHOD`` and optionally ``enable_*`` flags.
    """

    _VALID_METHODS = {"weighted_vote", "character_level_consensus", "best_confidence", "smart_fallback"}

    def __init__(self, config: Any) -> None:
        """Initialise the fusion engine.

        Args:
            config: Configuration object with ``OCR_FUSION_METHOD`` attribute.
        """
        self.config = config
        self.engines: Dict[str, BaseOCREngine] = {}
        self.fusion_method: str = getattr(config, "OCR_FUSION_METHOD", "weighted_vote")
        if self.fusion_method not in self._VALID_METHODS:
            logger.warning(
                "Unknown fusion method '%s' – falling back to 'weighted_vote'",
                self.fusion_method,
            )
            self.fusion_method = "weighted_vote"
        self._executor = ThreadPoolExecutor(max_workers=4)

    # ------------------------------------------------------------------
    # Engine registration
    # ------------------------------------------------------------------

    def register_engine(self, engine: BaseOCREngine) -> None:
        """Register an OCR engine for use during fusion.

        Args:
            engine: A concrete :class:`BaseOCREngine` instance.

        Raises:
            TypeError: If *engine* is not a :class:`BaseOCREngine`.
        """
        if not isinstance(engine, BaseOCREngine):
            raise TypeError(f"Expected BaseOCREngine, got {type(engine).__name__}")
        if engine.is_available():
            self.engines[engine.name] = engine
            logger.info("Registered OCR engine: %s", engine.name)
        else:
            logger.warning(
                "OCR engine '%s' is not available (missing dependencies) – skipped",
                engine.name,
            )

    def discover_and_register_all(self) -> int:
        """Auto-discover and register every engine that is available.

        Returns:
            Number of engines successfully registered.
        """
        candidates = [
            TesseractEngine(),
            EasyOCREngine(),
            PaddleOCREngine(),
            TrOCREngine(),
            SuryaEngine(),
        ]
        for engine in candidates:
            self.register_engine(engine)
        return len(self.engines)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def process(self, image_path: str, lang: str = "eng+ara") -> FusedResult:
        """Run all registered engines in parallel and fuse results.

        Args:
            image_path: Path to the image file.
            lang: Language hint string.

        Returns:
            A :class:`FusedResult` with fused text and metadata.
        """
        t0 = time.perf_counter()

        if not self.engines:
            return FusedResult(
                final_text="",
                fusion_method="none",
                processing_time_ms=(time.perf_counter() - t0) * 1000,
            )

        results = await self._run_engines_parallel(image_path, lang)

        if not results:
            return FusedResult(
                final_text="",
                fusion_method="none",
                processing_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Dispatch to the selected fusion method
        fusion_fn = {
            "weighted_vote": self._weighted_vote,
            "character_level_consensus": self._character_level_consensus,
            "best_confidence": self._best_confidence,
            "smart_fallback": self._smart_fallback,
        }[self.fusion_method]

        fused = fusion_fn(results)
        fused.processing_time_ms = (time.perf_counter() - t0) * 1000
        fused.fusion_method = self.fusion_method
        fused.engine_results = results
        fused.confidence_scores = {r.engine_name: r.confidence for r in results}
        fused.word_count = len(fused.final_text.split())
        return fused

    async def _run_engines_parallel(
        self, image_path: str, lang: str
    ) -> List[OCROutput]:
        """Execute all registered OCR engines concurrently.

        Args:
            image_path: Path to the image.
            lang: Language hint.

        Returns:
            List of :class:`OCROutput` from all engines (excluding failures).
        """
        loop = asyncio.get_event_loop()
        tasks = []
        for name, engine in self.engines.items():
            tasks.append(
                loop.run_in_executor(
                    self._executor,
                    lambda e=engine, p=image_path, l=lang: asyncio.run(e.recognize(p, l)),
                )
            )

        results: List[OCROutput] = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as exc:
                logger.error("OCR engine failed: %s", exc, exc_info=True)

        return results

    # ------------------------------------------------------------------
    # Fusion strategies
    # ------------------------------------------------------------------

    def _weighted_vote(self, results: List[OCROutput]) -> FusedResult:
        """Fuse by confidence-weighted majority voting on words.

        For each unique word (normalised), the engine with the highest
        confidence "wins" and contributes its version of the word to the
        output. Words are ordered by the average y-coordinate of their
        regions to preserve reading order.

        Args:
            results: List of engine outputs.

        Returns:
            :class:`FusedResult` with the voted text.
        """
        # Build weighted word map: word -> (text, weight, y_position)
        word_votes: Dict[str, Tuple[str, float, float]] = {}
        for result in results:
            weight = self._calculate_confidence_weight(result)
            words = result.text.split()
            for word in words:
                norm = word.lower().strip(".,;:!?()-\"'")
                if not norm:
                    continue
                if norm not in word_votes or weight > word_votes[norm][1]:
                    # Estimate vertical position from regions if available
                    avg_y = 0.0
                    if result.regions:
                        avg_y = float(np.mean([r.y for r in result.regions]))
                    word_votes[norm] = (word, weight, avg_y)

        # Sort by vertical position then by natural reading order
        sorted_words = sorted(
            word_votes.values(),
            key=lambda w: (w[2], len(w[0])),
        )
        fused_text = " ".join(w[0] for w in sorted_words)

        avg_conf = float(np.mean([r.confidence for r in results])) if results else 0.0
        return FusedResult(
            final_text=fused_text,
            confidence={r.engine_name: r.confidence for r in results},
            word_count=len(fused_text.split()),
        )

    def _character_level_consensus(self, results: List[OCROutput]) -> FusedResult:
        """Fuse by character-level majority voting.

        Each engine output is aligned (padded / trimmed to equal length) and
        for each position the most common character across engines is chosen.

        Args:
            results: List of engine outputs.

        Returns:
            :class:`FusedResult` with the consensus text.
        """
        if not results:
            return FusedResult(final_text="")

        texts = [r.text for r in results]
        weights = [self._calculate_confidence_weight(r) for r in results]

        # Pad all texts to the same length
        max_len = max(len(t) for t in texts) if texts else 0
        padded = [t.ljust(max_len, "\x00") for t in texts]

        consensus_chars: List[str] = []
        for i in range(max_len):
            char_count: Dict[str, float] = defaultdict(float)
            for t, w in zip(padded, weights):
                ch = t[i]
                char_count[ch] += w
            best_char = max(char_count, key=char_count.get)  # type: ignore[arg-type]
            if best_char != "\x00":
                consensus_chars.append(best_char)

        fused_text = "".join(consensus_chars)
        avg_conf = float(np.mean([r.confidence for r in results])) if results else 0.0
        return FusedResult(
            final_text=fused_text,
            confidence={r.engine_name: r.confidence for r in results},
            word_count=len(fused_text.split()),
        )

    def _best_confidence(self, results: List[OCROutput]) -> FusedResult:
        """Select the output from the single highest-confidence engine.

        Args:
            results: List of engine outputs.

        Returns:
            :class:`FusedResult` from the best engine.
        """
        if not results:
            return FusedResult(final_text="")

        best = max(results, key=lambda r: r.confidence)
        return FusedResult(
            final_text=best.text,
            confidence={r.engine_name: r.confidence for r in results},
            word_count=len(best.text.split()),
        )

    def _smart_fallback(self, results: List[OCROutput]) -> FusedResult:
        """Smart fallback: use best-confidence when one engine clearly
        dominates; otherwise fall back to weighted voting.

        A engine "dominates" when its confidence exceeds the second-best by
        at least 15 percentage points.

        Args:
            results: List of engine outputs.

        Returns:
            :class:`FusedResult`.
        """
        if len(results) <= 1:
            return self._best_confidence(results)

        sorted_by_conf = sorted(results, key=lambda r: r.confidence, reverse=True)
        gap = sorted_by_conf[0].confidence - sorted_by_conf[1].confidence

        if gap >= 0.15:
            logger.info(
                "Smart fallback: using best engine '%s' (gap=%.2f)",
                sorted_by_conf[0].engine_name, gap,
            )
            return self._best_confidence(results)

        logger.info("Smart fallback: engines are close – using weighted vote")
        return self._weighted_vote(results)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _align_texts(self, results: List[OCROutput]) -> Dict[str, Any]:
        """Perform word-level alignment across engine outputs.

        Uses dynamic time warping (DTW) on word tokens to find the optimal
        alignment. This is useful for comparing outputs from different engines.

        Args:
            results: List of engine outputs.

        Returns:
            A dict with ``alignment`` (list of aligned word tuples) and
            ``alignment_score`` (average similarity).
        """
        if len(results) < 2:
            return {"alignment": [], "alignment_score": 1.0}

        word_lists = [r.text.split() for r in results]
        # Simple pairwise alignment for first two results using Levenshtein
        w1, w2 = word_lists[0], word_lists[1]
        aligned: List[Tuple[Optional[str], Optional[str]]] = []

        i, j = 0, 0
        while i < len(w1) and j < len(w2):
            if w1[i].lower() == w2[j].lower():
                aligned.append((w1[i], w2[j]))
                i += 1
                j += 1
            elif i + 1 < len(w1) and j < len(w2) and w1[i + 1].lower() == w2[j].lower():
                aligned.append((w1[i], None))  # deletion in w2
                i += 1
            elif i < len(w1) and j + 1 < len(w2) and w1[i].lower() == w2[j + 1].lower():
                aligned.append((None, w2[j]))  # insertion in w2
                j += 1
            else:
                aligned.append((w1[i], w2[j]))  # substitution
                i += 1
                j += 1

        # Remaining
        while i < len(w1):
            aligned.append((w1[i], None))
            i += 1
        while j < len(w2):
            aligned.append((None, w2[j]))
            j += 1

        matches = sum(1 for a, b in aligned if a and b and a.lower() == b.lower())
        score = matches / max(len(aligned), 1)

        return {"alignment": aligned, "alignment_score": score}

    @staticmethod
    def _calculate_confidence_weight(result: OCROutput) -> float:
        """Calculate a non-linear confidence weight for a result.

        Applies a power function to amplify differences: higher confidence
        gets disproportionately more weight.

        Args:
            result: A single engine output.

        Returns:
            A weight in [0, 1] (typically).
        """
        base = result.confidence
        # Sigmoid-like amplification
        return base ** 1.5


# ============================================================================
# SECTION 4 – Semantic Deduplication Engine
# ============================================================================


class SemanticDeduplicationEngine:
    """Embedding-based deduplication of document chunks.

    Uses ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``
    for dense embeddings, a FAISS IVFFlat index for fast similarity search,
    and DBSCAN for clustering.

    Args:
        similarity_threshold: Minimum cosine similarity to consider two
            chunks as duplicates.
        dbscan_eps: DBSCAN epsilon parameter for clustering.
        chunk_size: Target token count per chunk.
        chunk_overlap: Overlap between consecutive chunks.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        dbscan_eps: float = 0.3,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
    ) -> None:
        """Initialise the deduplication engine.

        Args:
            similarity_threshold: Cosine similarity threshold for duplicates.
            dbscan_eps: DBSCAN epsilon for clustering.
            chunk_size: Approximate chunk size in characters.
            chunk_overlap: Overlap between consecutive chunks in characters.
        """
        self.similarity_threshold = similarity_threshold
        self.dbscan_eps = dbscan_eps
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._model: Any = None
        self._faiss_index: Any = None
        self._dimension: int = 384  # MiniLM-L12 dimension
        self._initialised = False

    async def initialize(self) -> None:
        """Load the embedding model and build an empty FAISS index.

        This is an expensive operation and should be called once at startup.
        The model is lazy-loaded on first call.
        """
        if self._initialised:
            return

        try:
            from sentence_transformers import SentenceTransformer
            model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            logger.info("Loading sentence-transformer model: %s", model_name)
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(
                None, SentenceTransformer, model_name
            )
            self._dimension = self._model.get_sentence_embedding_dimension()
        except ImportError:
            logger.error(
                "sentence-transformers not installed – semantic dedup unavailable. "
                "Install with: pip install sentence-transformers"
            )
            return

        # Build empty FAISS IVFFlat index
        try:
            import faiss

            quantizer = faiss.IndexFlatIP(self._dimension)
            self._faiss_index = faiss.IndexIVFFlat(
                quantizer, self._dimension, min(100, self._dimension), faiss.METRIC_INNER_PRODUCT
            )
            self._faiss_index.set_nprobe(8)
            logger.info("FAISS IVFFlat index created (dim=%d)", self._dimension)
        except ImportError:
            logger.error(
                "faiss-cpu not installed – FAISS indexing unavailable. "
                "Install with: pip install faiss-cpu"
            )
            return

        self._initialised = True

    def _chunk_text(
        self, text: str, page_num: int = 1
    ) -> List[DocumentChunk]:
        """Split text into overlapping chunks.

        Splits on whitespace boundaries to avoid cutting words mid-token.

        Args:
            text: The full document text.
            page_num: Source page number (for metadata).

        Returns:
            List of :class:`DocumentChunk` instances.
        """
        if not text or not text.strip():
            return []

        chunks: List[DocumentChunk] = []
        start = 0
        idx = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at a whitespace boundary
            if end < len(text):
                ws_pos = text.rfind(" ", start, end)
                if ws_pos != -1 and ws_pos > start:
                    end = ws_pos

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        text=chunk_text,
                        page_num=page_num,
                        chunk_index=idx,
                    )
                )
                idx += 1

            start = end - self.chunk_overlap
            if start <= start - self.chunk_overlap + self.chunk_size and end >= len(text):
                break

        return chunks

    def _encode(self, texts: List[str]) -> np.ndarray:
        """Generate dense embeddings for a batch of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            ``np.ndarray`` of shape ``(len(texts), dimension)`` normalised
            to unit length.
        """
        if self._model is None:
            raise RuntimeError("Model not initialised – call initialize() first")
        loop = asyncio.get_event_loop()
        embeddings: np.ndarray = loop.run_in_executor(
            None, self._model.encode, texts
        )
        # L2-normalise for cosine similarity via inner product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        embeddings = embeddings / norms
        return embeddings.astype(np.float32)

    def _build_faiss_index(self, embeddings: np.ndarray) -> None:
        """Build a FAISS IVFFlat index from the given embeddings.

        If the number of vectors is smaller than the number of clusters,
        falls back to a flat (brute-force) index.

        Args:
            embeddings: Normalised embedding matrix ``(N, D)``.
        """
        try:
            import faiss
        except ImportError:
            logger.error("faiss-cpu not available – skipping index build")
            return

        n = embeddings.shape[0]
        if n == 0:
            return

        if n < 100:
            # Fall back to flat index for small datasets
            self._faiss_index = faiss.IndexFlatIP(self._dimension)
        else:
            n_clusters = min(100, max(1, int(np.sqrt(n))))
            quantizer = faiss.IndexFlatIP(self._dimension)
            self._faiss_index = faiss.IndexIVFFlat(
                quantizer, self._dimension, n_clusters, faiss.METRIC_INNER_PRODUCT
            )
            self._faiss_index.set_nprobe(8)

        # Train (only required for IVF indices)
        if hasattr(self._faiss_index, "train") and not self._faiss_index.is_trained:
            self._faiss_index.train(embeddings)

        self._faiss_index.add(embeddings)
        logger.info("FAISS index built with %d vectors", n)

    def _cluster(self, embeddings: np.ndarray) -> np.ndarray:
        """Cluster embeddings using DBSCAN.

        Args:
            embeddings: Normalised embedding matrix ``(N, D)``.

        Returns:
            Integer cluster labels. ``-1`` indicates noise.
        """
        from sklearn.cluster import DBSCAN

        # Convert cosine distance from cosine similarity (embeddings are L2-normed)
        distances = 1.0 - (embeddings @ embeddings.T)
        clustering = DBSCAN(
            eps=self.dbscan_eps,
            min_samples=2,
            metric="precomputed",
        ).fit(distances)
        return clustering.labels_

    def _merge_clusters(
        self,
        chunks: List[DocumentChunk],
        labels: np.ndarray,
        embeddings: np.ndarray,
    ) -> List[SemanticCluster]:
        """Group chunks by cluster labels and build :class:`SemanticCluster` objects.

        Args:
            chunks: The document chunks (one per row in *embeddings*).
            labels: Integer cluster labels from DBSCAN.
            embeddings: Normalised embedding matrix.

        Returns:
            List of :class:`SemanticCluster` instances (one per cluster).
        """
        cluster_map: Dict[int, List[int]] = defaultdict(list)
        for idx, label in enumerate(labels):
            cluster_map[label].append(idx)

        clusters: List[SemanticCluster] = []
        for label, indices in cluster_map.items():
            if label == -1:
                # Noise points – each becomes its own singleton cluster
                for idx in indices:
                    chunks[idx].embedding = embeddings[idx].tolist()
                    clusters.append(
                        SemanticCluster(
                            chunks=[chunks[idx]],
                            representative_text=chunks[idx].text,
                            centroid_embedding=embeddings[idx].tolist(),
                            similarity_score=1.0,
                        )
                    )
                continue

            member_chunks = [chunks[i] for i in indices]
            member_embeddings = embeddings[indices]

            # Centroid
            centroid = np.mean(member_embeddings, axis=0)
            centroid = centroid / max(np.linalg.norm(centroid), 1e-8)

            # Average pairwise similarity
            if len(indices) > 1:
                sim_matrix = member_embeddings @ member_embeddings.T
                # Extract upper triangle (excluding diagonal)
                triu_indices = np.triu_indices(len(indices), k=1)
                avg_sim = float(np.mean(sim_matrix[triu_indices])) if len(triu_indices[0]) > 0 else 1.0
            else:
                avg_sim = 1.0

            # Find representative
            rep_text = self._find_representative(member_chunks)

            # Attach embeddings to chunks
            for i, idx in enumerate(indices):
                member_chunks[i].embedding = member_embeddings[i].tolist()

            clusters.append(
                SemanticCluster(
                    chunks=member_chunks,
                    representative_text=rep_text,
                    centroid_embedding=centroid.tolist(),
                    similarity_score=avg_sim,
                )
            )

        return clusters

    @staticmethod
    def _find_representative(cluster_chunks: List[DocumentChunk]) -> str:
        """Select the representative text from a cluster.

        Strategy: pick the chunk with the highest character count (longest
        tends to be the most informative), breaking ties by index.

        Args:
            cluster_chunks: Chunks belonging to the same cluster.

        Returns:
            The representative text string.
        """
        if not cluster_chunks:
            return ""
        return max(cluster_chunks, key=lambda c: len(c.text)).text

    async def deduplicate(
        self, chunks: List[DocumentChunk]
    ) -> List[SemanticCluster]:
        """Run semantic deduplication on a list of document chunks.

        Steps:
            1. Encode chunks to embeddings.
            2. Build a FAISS IVFFlat index.
            3. Cluster using DBSCAN.
            4. Merge into :class:`SemanticCluster` objects.

        Args:
            chunks: Document chunks to deduplicate.

        Returns:
            List of semantic clusters (duplicates merged).
        """
        if not self._initialised:
            await self.initialize()

        if not chunks:
            return []

        if self._model is None:
            logger.warning("No model available – returning chunks as singleton clusters")
            return [
                SemanticCluster(
                    chunks=[c],
                    representative_text=c.text,
                    similarity_score=1.0,
                )
                for c in chunks
            ]

        texts = [c.text for c in chunks]
        embeddings = self._encode(texts)

        self._build_faiss_index(embeddings)
        labels = self._cluster(embeddings)

        return self._merge_clusters(chunks, labels, embeddings)


# ============================================================================
# SECTION 5 – Medical Knowledge Graph
# ============================================================================


class MedicalKnowledgeGraph:
    """Extract a medical knowledge graph from free-text OCR output.

    Uses regex patterns to identify entities (diagnoses, medications,
    procedures, anatomy, dates, values) in both English and Arabic, then
    applies relation-extraction patterns to connect them.

    Attributes:
        PATTERNS: Dictionary mapping entity types to regex lists.
        RELATION_PATTERNS: List of ``(regex, predicate)`` tuples.
    """

    # ------------------------------------------------------------------
    # Entity patterns (English + Arabic)
    # ------------------------------------------------------------------
    PATTERNS: Dict[EntityType, List[Tuple[str, re.Pattern]]] = {
        EntityType.DIAGNOSIS: [
            # English
            (r"\b(?:diagnosed with|diagnosis of|suffering from|has| Dx[:\s])\s+([A-Z][A-Za-z\s\-]+?)(?:,|;|\.|\n|$)", re.IGNORECASE),
            (r"\b(?:type\s+\d+\s+diabetes|Type 2 Diabetes|Type 1 Diabetes)\b", re.IGNORECASE),
            (r"\b(?:hypertension|hyperlipidemia|anemia|asthma|COPD|CHF|CKD|CAD)\b", re.IGNORECASE),
            (r"\b(?:myocardial infarction|pneumonia|bronchitis|gastritis|arthritis|osteoporosis)\b", re.IGNORECASE),
            # Arabic
            (r"(?:تشخيص|مصاب بـ|يعاني من|حالة)\s+[\u0600-\u06FF\s]+?(?:،|؛|\.|\n|$)", 0),
            (r"\b(?:سكري|ضغط|ارتفاع ضغط|أنيميا|ربو|قصور قلب|فشل كلوي|تصلب شرايين)\b", 0),
            (r"\b(?:السكري النوع الثاني|السكري النوع الأول|ضغط الدم المرتفع)\b", 0),
            (r"\b(?:التهاب رئوي|التهاب شعب|التهاب المعدة|التهاب مفاصل|هشاشة عظام)\b", 0),
        ],
        EntityType.MEDICATION: [
            # English – drug names + dosage
            (r"\b(?:Metformin|Insulin|Aspirin|Lisinopril|Amlodipine|Omeprazole|Atorvastatin|Losartan|Clopidogrel|Warfarin|Heparin|Prednisone|Salbutamol|Ibuprofen|Paracetamol|Amoxicillin|Azithromycin)\b\s*(?:\d+\.?\d*\s*(?:mg|mcg|ml|g))?", re.IGNORECASE),
            (r"\b(?:prescribed|take|administer|dose|dosage)[:\s]+\s+([A-Za-z]+(?:\s+\d+\.?\d*\s*(?:mg|mcg|ml|g))?)", re.IGNORECASE),
            # Arabic
            (r"\b(?:ميتفورمين|أنسولين|أسبرين|أوميبرازول|أتورفاستاتين|لوسارتان|وارفارين|هيبارين|بريدنيزون|سالبوتامول|أموكسيسيلين|بنادول|فولتارين)\b", 0),
            (r"\b(?:قرص|كبسولة|حقنة|ملعقة)\s+\d+\s*(?:ملغ|مجم|مل)\b", 0),
            (r"\b(?:الأدوية|الدواء|الوصفة|الجرعة)[:\s]*[\u0600-\u06FF\s\d.]+?(?:،|؛|\.|\n|$)", 0),
        ],
        EntityType.PROCEDURE: [
            # English
            (r"\b(?:underwent|performed|surgery|operation|CT scan|MRI|X-ray|ultrasound|biopsy|endoscopy|colonoscopy|ECG|EKG|angioplasty|bypass|transplant|dialysis|intubation|catheterisation)\b", re.IGNORECASE),
            (r"\b(?:blood test|urine test|lab work|CBC|BMP|HbA1c|lipid panel|liver function|renal function)\b", re.IGNORECASE),
            # Arabic
            (r"\b(?:عملية|جراحة|فحص|تصوير|أشعة|رنين مغناطيسي|إيكو|منظار|خزعة|قسطرة|غسيل كلوي|تنبيب)\b", 0),
            (r"\b(?:تحليل دم|تحليل بول|صورة دم|سكر صائم|وظائف كبد|وظائف كلى|دهون)\b", 0),
        ],
        EntityType.ANATOMY: [
            # English
            (r"\b(?:heart|lung|liver|kidney|brain|spine|chest|abdomen|pelvis|arm|leg|knee|shoulder|elbow|wrist|ankle|foot|hand|neck|throat|eye|ear|nose|skin|bone|joint|muscle|artery|vein)\b", re.IGNORECASE),
            (r"\b(?:left|right|bilateral)\s+(?:ventricle|atrium|lung|kidney|arm|leg|breast|eye|ear)\b", re.IGNORECASE),
            # Arabic
            (r"\b(?:القلب|الرئة|الكبد|الكلية|الدماغ|العمود الفقري|الصدر|البطن|الحوض|الذراع|الساق|الركبة|الكتف|المرفق|المعصم|الكاحل|القدم|اليد|الرقبة|الحلق|العين|الأذن|الأنف|الجلد|العظم|المفصل|العضلة|الشريان|الوريد)\b", 0),
            (r"\b(?:يمين|يسار|جانبي)\s+(?:البطين|الأذين|الرئة|الكلية|الذراع|الساق|الثدي|العين|الأذن)\b", 0),
        ],
        EntityType.DATE: [
            # English formats
            (r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", 0),
            (r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4}\b", re.IGNORECASE),
            (r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", 0),
            # Arabic / Hijri dates
            (r"\b\d{1,2}/\d{1,2}/\d{4}\s*[هـه]?\.?\b", 0),
            (r"(?:\d{1,2}\s+)?(?:يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+\d{4}\b", 0),
        ],
        EntityType.VALUE: [
            # Lab values, vitals
            (r"\b\d+\.?\d*\s*(?:mmHg|mg/dL|g/dL|mg/L|U/L|mEq/L|ng/mL|pg/mL|%|bpm|°C|°F)\b", 0),
            (r"\b(?:BP|blood pressure|HR|heart rate|RR|respiratory rate|SpO2|temp|temperature|weight|height|BMI)\s*[:=]?\s*\d+\.?\d*\s*(?:mmHg|bpm|mmol/L|mg/dL|kg|cm|°C)?\b", re.IGNORECASE),
            # Arabic
            (r"\b(?:ضغط الدم|النبض|التنفس|الحرارة|الوزن|الطول|مؤشر كتلة الجسم|نسبة السكر|الهيموجلوبين|الصفيحات)\s*[:=]?\s*\d+\.?\d*\b", 0),
            (r"\b\d+\.?\d*\s*(?:ملم زئبق|مج/دل|جرام/دل|نبضة/دقيقة|درجة مئوية)\b", 0),
        ],
    }

    # ------------------------------------------------------------------
    # Relation patterns
    # ------------------------------------------------------------------
    RELATION_PATTERNS: List[Tuple[str, str]] = [
        # English
        (r"patient\s+(?:has|is diagnosed with|was diagnosed with|suffers from)\s+(.+?)(?:,|;|\.|\n|$)", "DIAGNOSED_WITH"),
        (r"(?:prescribed|take|administer(?:ed)?|given)\s+(.+?)\s+(?:for|to treat)\s+(.+?)(?:,|;|\.|\n|$)", "PRESCRIBED_FOR"),
        (r"(?:perform(?:ed)?|underwent)\s+(.+?)\s+(?:on|of)\s+(.+?)(?:,|;|\.|\n|$)", "PERFORMED_ON"),
        (r"(?:normal|abnormal|elevated|low|high)\s+(.+?)\s+(?:in|of)\s+(.+?)(?:,|;|\.|\n|$)", "VALUE_OF"),
        # Arabic
        (r"(?:المريض|المريضة)\s+(?:مصاب|مصابة)\s+بـ?\s+(.+?)(?:،|؛|\.|\n|$)", "DIAGNOSED_WITH"),
        (r"(?:وصف|يأخذ|تناول)\s+(.+?)\s+(?:لعلاج|لـ)\s+(.+?)(?:،|؛|\.|\n|$)", "PRESCRIBED_FOR"),
        (r"(?:إجراء|تم|أجري)\s+(.+?)\s+(?:على|في)\s+(.+?)(?:،|؛|\.|\n|$)", "PERFORMED_ON"),
        (r"(?:طبيعي|غير طبيعي|مرتفع|منخفض)\s+(.+?)\s+(?:في|من)\s+(.+?)(?:،|؛|\.|\n|$)", "VALUE_OF"),
    ]

    def __init__(self) -> None:
        """Initialise with compiled regex patterns."""
        self._compiled_entity_patterns: Dict[EntityType, List[re.Pattern]] = {}
        self._compiled_relation_patterns: List[Tuple[re.Pattern, str]] = []

        for entity_type, pattern_list in self.PATTERNS.items():
            compiled: List[re.Pattern] = []
            for pattern_str, flags in pattern_list:
                compiled.append(re.compile(pattern_str, flags))
            self._compiled_entity_patterns[entity_type] = compiled

        for pattern_str, predicate in self.RELATION_PATTERNS:
            self._compiled_relation_patterns.append(
                (re.compile(pattern_str, re.IGNORECASE | re.DOTALL), predicate)
            )

    async def build(self, text: str) -> KnowledgeGraph:
        """Build a knowledge graph from a text string.

        Args:
            text: The document text (typically fused OCR output).

        Returns:
            A :class:`KnowledgeGraph` with entities and relations.
        """
        entities = self._extract_entities(text)
        relations = self._extract_relations(text, entities)

        return KnowledgeGraph(
            entities=entities,
            relations=relations,
            metadata={
                "source_text_length": len(text),
                "entity_count": len(entities),
                "relation_count": len(relations),
                "entity_type_distribution": Counter(e.entity_type.value for e in entities),
            },
        )

    def _extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract medical entities from text using regex patterns.

        Iterates over all compiled patterns and collects non-overlapping
        matches. Each entity is assigned a confidence of 1.0 for regex
        matches (as they are deterministic).

        Args:
            text: Source text.

        Returns:
            List of :class:`MedicalEntity` objects.
        """
        entities: List[MedicalEntity] = []
        seen_spans: List[Tuple[int, int]] = []

        for entity_type, patterns in self._compiled_entity_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # Use the first capturing group if present, else full match
                    matched_text = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
                    if not matched_text.strip():
                        continue

                    start, end = match.start(), match.end()

                    # Check for overlap with existing entities
                    overlaps = any(
                        start < existing_end and end > existing_start
                        for (existing_start, existing_end) in seen_spans
                    )
                    if overlaps:
                        continue

                    seen_spans.append((start, end))
                    entities.append(
                        MedicalEntity(
                            entity_type=entity_type,
                            text=matched_text.strip(),
                            confidence=1.0,
                            position=(start, end),
                        )
                    )

        return entities

    def _extract_relations(
        self, text: str, entities: List[MedicalEntity]
    ) -> List[Relation]:
        """Extract binary relations between entities using pattern matching.

        For each compiled relation pattern, extracts subject and object
        spans and matches them against known entities when possible.

        Args:
            text: Source text.
            entities: Already-extracted entities (used for grounding).

        Returns:
            List of :class:`Relation` objects.
        """
        entity_texts = {e.text.lower().strip(): e for e in entities}
        relations: List[Relation] = []

        for pattern, predicate in self._compiled_relation_patterns:
            for match in pattern.finditer(text):
                groups = match.groups()
                if len(groups) >= 2:
                    subject_text = groups[0].strip()
                    object_text = groups[1].strip()
                elif len(groups) == 1:
                    subject_text = groups[0].strip()
                    object_text = ""
                else:
                    continue

                if not subject_text:
                    continue

                relations.append(
                    Relation(
                        subject=subject_text,
                        predicate=predicate,
                        object=object_text,
                        confidence=0.8,
                    )
                )

        return relations

    def to_json(self, kg: KnowledgeGraph) -> str:
        """Serialise a knowledge graph to a JSON string.

        Args:
            kg: The knowledge graph to serialise.

        Returns:
            A JSON-formatted string.
        """
        return kg.model_dump_json(indent=2)

    def to_networkx(self, kg: KnowledgeGraph) -> Any:
        """Convert the knowledge graph to a NetworkX ``DiGraph``.

        Nodes are medical entities (keyed by text), edges are relations.

        Args:
            kg: The knowledge graph.

        Returns:
            A ``networkx.DiGraph`` instance, or ``None`` if NetworkX
            is not installed.
        """
        try:
            import networkx as nx

            G = nx.DiGraph()
            for entity in kg.entities:
                G.add_node(
                    entity.text,
                    type=entity.entity_type.value,
                    confidence=entity.confidence,
                )
            for rel in kg.relations:
                if rel.subject and rel.object:
                    G.add_edge(
                        rel.subject,
                        rel.object,
                        predicate=rel.predicate,
                        confidence=rel.confidence,
                    )
            return G
        except ImportError:
            logger.warning("NetworkX not installed – to_networkx() returns None")
            return None


# ============================================================================
# SECTION 6 – Omni Medical Pipeline (Orchestrator)
# ============================================================================


class OmniMedicalPipeline:
    """End-to-end orchestrator for medical document processing.

    Wires together:
        1. :class:`OCRFusionEngine` – multi-engine OCR with fusion.
        2. :class:`SemanticDeduplicationEngine` – embedding-based dedup.
        3. :class:`MedicalKnowledgeGraph` – entity and relation extraction.

    Usage::

        config = OmniFileConfig.from_profile("balanced")
        pipeline = OmniMedicalPipeline(config)
        await pipeline.initialize()
        result = await pipeline.process_document("path/to/image.png")
    """

    def __init__(self, config: Any) -> None:
        """Initialise the pipeline.

        Args:
            config: An :class:`OmniFileConfig`-like configuration object.
        """
        self.config = config
        self.ocr_fusion = OCRFusionEngine(config)
        self.semantic_dedup = SemanticDeduplicationEngine(
            similarity_threshold=getattr(config, "DEDUP_SIMILARITY_THRESHOLD", 0.85),
            dbscan_eps=getattr(config, "DEDUP_DBSCAN_EPS", 0.3),
            chunk_size=getattr(config, "DEDUP_CHUNK_SIZE", 512),
            chunk_overlap=getattr(config, "DEDUP_CHUNK_OVERLAP", 128),
        )
        self.knowledge_graph = MedicalKnowledgeGraph()

    async def initialize(self) -> None:
        """Register all available OCR engines and initialise dedup.

        This method should be called once before :meth:`process_document`.
        It performs engine discovery and triggers the (lazy) loading of
        the embedding model and FAISS index.
        """
        logger.info("Initialising OmniMedicalPipeline...")
        n_engines = self.ocr_fusion.discover_and_register_all()
        logger.info("Registered %d OCR engine(s): %s", n_engines, list(self.ocr_fusion.engines.keys()))
        await self.semantic_dedup.initialize()
        logger.info("OmniMedicalPipeline initialisation complete")

    async def process_document(self, image_path: str) -> Dict[str, Any]:
        """Process a single document image through the full pipeline.

        Steps:
            1. Run multi-engine OCR fusion.
            2. Chunk the fused text.
            3. Semantic deduplication of chunks.
            4. Build a medical knowledge graph.

        Args:
            image_path: Absolute path to the document image.

        Returns:
            A dictionary with keys:
                - ``fused_text`` (str): The fused OCR output.
                - ``fusion_method`` (str): The fusion strategy used.
                - ``fused_confidence`` (Dict[str, float]): Per-engine confidence.
                - ``deduplicated_clusters`` (List[Dict]): Dedup cluster summaries.
                - ``knowledge_graph`` (Dict): KG entities and relations.
                - ``processing_stats`` (Dict): Timing and count metadata.

        Raises:
            FileNotFoundError: If *image_path* does not exist.
        """
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        pipeline_start = time.perf_counter()
        stats: Dict[str, float] = {}

        # Step 1: OCR Fusion
        t0 = time.perf_counter()
        fused_result = await self.ocr_fusion.process(image_path)
        stats["ocr_fusion_ms"] = (time.perf_counter() - t0) * 1000

        # Step 2: Chunking
        t1 = time.perf_counter()
        chunks = self.semantic_dedup._chunk_text(fused_result.final_text)
        stats["chunking_ms"] = (time.perf_counter() - t1) * 1000

        # Step 3: Semantic Deduplication
        t2 = time.perf_counter()
        clusters = await self.semantic_dedup.deduplicate(chunks)
        stats["deduplication_ms"] = (time.perf_counter() - t2) * 1000

        # Step 4: Knowledge Graph
        t3 = time.perf_counter()
        kg = await self.knowledge_graph.build(fused_result.final_text)
        stats["knowledge_graph_ms"] = (time.perf_counter() - t3) * 1000

        stats["total_ms"] = (time.perf_counter() - pipeline_start) * 1000

        # Build cluster summaries
        cluster_summaries = [
            {
                "cluster_id": c.cluster_id,
                "chunk_count": len(c.chunks),
                "representative_text": c.representative_text[:200],
                "similarity_score": c.similarity_score,
            }
            for c in clusters
        ]

        # Build KG summary
        kg_summary = {
            "entities": [
                {
                    "type": e.entity_type.value,
                    "text": e.text,
                    "confidence": e.confidence,
                }
                for e in kg.entities
            ],
            "relations": [
                {
                    "subject": r.subject,
                    "predicate": r.predicate,
                    "object": r.object,
                    "confidence": r.confidence,
                }
                for r in kg.relations
            ],
            "metadata": kg.metadata,
        }

        return {
            "fused_text": fused_result.final_text,
            "fusion_method": fused_result.fusion_method,
            "fused_confidence": fused_result.confidence_scores,
            "deduplicated_clusters": cluster_summaries,
            "knowledge_graph": kg_summary,
            "processing_stats": stats,
        }

    @classmethod
    async def demo(cls) -> Dict[str, Any]:
        """Run a demonstration with synthetic medical data.

        This class method creates a pipeline with default settings, feeds it
        a synthetic bilingual (English/Arabic) medical text, and returns the
        full processing result.

        Returns:
            A dictionary matching :meth:`process_document` output format.
        """
        import tempfile

        sample_text = (
            "Patient Medical Report\n"
            "======================\n"
            "Patient Name: Ahmed Al-Rashid\n"
            "Date of Birth: 15/03/1965\n"
            "Date: 2024/01/20\n\n"
            "Diagnosis:\n"
            "Patient is diagnosed with Type 2 Diabetes and Hypertension.\n"
            "المريض مصاب بارتفاع ضغط الدم والسكري النوع الثاني\n\n"
            "Medications:\n"
            "Metformin 500mg twice daily\n"
            "Lisinopril 10mg once daily\n"
            "ميتفورمين 500 ملغ مرتين يومياً\n\n"
            "Vitals:\n"
            "BP: 140/90 mmHg\n"
            "Heart Rate: 88 bpm\n"
            "BMI: 28.5\n\n"
            "Lab Results:\n"
            "HbA1c: 7.8%\n"
            "Fasting Glucose: 145 mg/dL\n"
            "نسبة السكر الصائم: 145 مج/دل\n\n"
            "Procedures:\n"
            "Underwent echocardiography on heart.\n"
            "تم إجراء إيكو على القلب\n\n"
            "Follow-up in 3 months.\n"
            "متابعة بعد 3 أشهر.\n"
        )

        # Create a synthetic image with text rendered on it
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.error("Pillow not installed – cannot create demo image")
            return {"error": "Pillow not installed"}

        img = Image.new("RGB", (800, 1200), color="white")
        draw = ImageDraw.Draw(img)

        # Try to use a font that supports Arabic, fall back to default
        font = None
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        for fp in font_paths:
            if os.path.isfile(fp):
                try:
                    font = ImageFont.truetype(fp, 16)
                    break
                except Exception:
                    continue

        y_pos = 10
        for line in sample_text.split("\n"):
            draw.text((20, y_pos), line, fill="black", font=font)
            y_pos += 22

        # Write to temp file
        tmp_dir = tempfile.mkdtemp()
        demo_image_path = os.path.join(tmp_dir, "demo_medical_report.png")
        img.save(demo_image_path, "PNG")

        logger.info("Demo image created at: %s", demo_image_path)

        # Create pipeline with default config
        class _DummyConfig:
            OCR_FUSION_METHOD = "weighted_vote"
            DEDUP_SIMILARITY_THRESHOLD = 0.85
            DEDUP_DBSCAN_EPS = 0.3
            DEDUP_CHUNK_SIZE = 512
            DEDUP_CHUNK_OVERLAP = 128

        pipeline = cls(_DummyConfig())
        await pipeline.initialize()

        try:
            result = await pipeline.process_document(demo_image_path)
        except Exception as exc:
            logger.error("Demo processing failed: %s", exc, exc_info=True)
            result = {
                "error": str(exc),
                "fused_text": sample_text,
                "fusion_method": "demo_fallback",
                "fused_confidence": {},
                "deduplicated_clusters": [],
                "knowledge_graph": {"entities": [], "relations": [], "metadata": {}},
                "processing_stats": {"error": True},
            }

        # Cleanup
        try:
            os.unlink(demo_image_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

        return result


# ============================================================================
# SECTION 7 – Convenience Functions & Entry Point
# ============================================================================


async def process_medical_document(
    image_path: str,
    fusion_method: str = "weighted_vote",
    lang: str = "eng+ara",
) -> Dict[str, Any]:
    """High-level convenience function to process a single medical document.

    Args:
        image_path: Path to the document image.
        fusion_method: One of ``weighted_vote``, ``character_level_consensus``,
            ``best_confidence``, ``smart_fallback``.
        lang: Language hint for OCR engines.

    Returns:
        Processing result dictionary (see :meth:`OmniMedicalPipeline.process_document`).
    """
    class _QuickConfig:
        OCR_FUSION_METHOD = fusion_method
        DEDUP_SIMILARITY_THRESHOLD = 0.85
        DEDUP_DBSCAN_EPS = 0.3
        DEDUP_CHUNK_SIZE = 512
        DEDUP_CHUNK_OVERLAP = 128

    pipeline = OmniMedicalPipeline(_QuickConfig())
    await pipeline.initialize()
    return await pipeline.process_document(image_path)


def quick_ocr(
    image_path: str,
    engines: Optional[List[str]] = None,
    fusion_method: str = "best_confidence",
) -> FusedResult:
    """Synchronous quick-OCR function for notebooks and scripts.

    Runs the specified engines (or all available) and returns a fused result
    without semantic deduplication or knowledge graph extraction.

    Args:
        image_path: Path to the image file.
        engines: List of engine names to use (``None`` = all available).
        fusion_method: Fusion strategy name.

    Returns:
        A :class:`FusedResult`.
    """
    class _QuickConfig:
        OCR_FUSION_METHOD = fusion_method

    fusion = OCRFusionEngine(_QuickConfig())

    all_engines = {
        "tesseract": TesseractEngine(),
        "easyocr": EasyOCREngine(),
        "paddleocr": PaddleOCREngine(),
        "trocr": TrOCREngine(),
        "surya": SuryaEngine(),
    }

    selected_names = engines or list(all_engines.keys())
    for name in selected_names:
        if name in all_engines:
            fusion.register_engine(all_engines[name])

    results: List[OCROutput] = []
    for engine in fusion.engines.values():
        try:
            result = asyncio.run(engine.recognize(image_path))
            results.append(result)
        except Exception as exc:
            logger.error("Engine %s failed: %s", engine.name, exc)

    if not results:
        return FusedResult(final_text="")

    fusion_fn = {
        "weighted_vote": fusion._weighted_vote,
        "character_level_consensus": fusion._character_level_consensus,
        "best_confidence": fusion._best_confidence,
        "smart_fallback": fusion._smart_fallback,
    }.get(fusion_method, fusion._best_confidence)

    return fusion_fn(results)


# ============================================================================
# Module-level test / demo entry point
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Omni-Medical Suite – OCR Fusion System Demo")
    print("=" * 60)

    async def _main() -> None:
        """Run the built-in demo."""
        result = await OmniMedicalPipeline.demo()
        print(json.dumps(result, default=str, indent=2, ensure_ascii=False))

    asyncio.run(_main())
