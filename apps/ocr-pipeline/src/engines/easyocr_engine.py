"""
EasyOCR Engine
==============

Wraps ``easyocr.Reader`` with Arabic + English language support, automatic
GPU/CPU detection, paragraph detection mode for medical documents, and
confidence calibration.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np

from src.engines.base_engine import BBox, OCREngine, OCRResult, ImageInput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Confidence calibration
# ---------------------------------------------------------------------------

def _calibrate_confidence(raw_confidence: float) -> float:
    """Apply a calibration mapping to EasyOCR's raw confidence.

    EasyOCR tends to over-estimate confidence for Arabic text.  This
    sigmoid-like mapping compresses the high end and stretches the low
    end for a more realistic distribution.

    Parameters
    ----------
    raw_confidence : float
        Raw confidence from EasyOCR in ``[0.0, 1.0]``.

    Returns
    -------
    float
        Calibrated confidence in ``[0.0, 1.0]``.
    """
    # Piecewise-linear calibration:
    #   [0.0, 0.5] -> scaled to [0.0, 0.4]  (boost low confidences)
    #   [0.5, 0.8] -> scaled to [0.4, 0.75] (linear)
    #   [0.8, 1.0] -> compressed to [0.75, 0.95] (cap the top)
    if raw_confidence <= 0.5:
        return raw_confidence * 0.8
    elif raw_confidence <= 0.8:
        return 0.4 + (raw_confidence - 0.5) * (0.35 / 0.3)
    else:
        return 0.75 + (raw_confidence - 0.8) * (0.2 / 0.2)


# ---------------------------------------------------------------------------
# EasyOCREngine
# ---------------------------------------------------------------------------

class EasyOCREngine(OCREngine):
    """EasyOCR engine with Arabic + English medical document support.

    Features:

    * Automatic GPU/CPU detection via ``torch.cuda.is_available()``.
    * Paragraph detection mode that groups nearby text regions into
      coherent paragraphs (useful for multi-line medical notes).
    * Confidence calibration to counter EasyOCR's over-confidence on
      Arabic text.

    Parameters
    ----------
    languages : list[str] | None
        Language codes for the reader (default ``["ar", "en"]``).
    gpu : bool | None
        Force GPU (``True``) or CPU (``False``).  If *None*, auto-detect.
    model_storage_directory : str | None
        Custom directory for EasyOCR model weights.
    download_enabled : bool
        Allow downloading models if not found locally.
    detect_network : str
        Text detection model (default ``"craft"``).
    paragraph : bool
        Enable paragraph grouping (default *True* for medical docs).
    calibrate_confidence : bool
        Apply confidence calibration (default *True*).
    batch_size : int
        Batch size for internal batching (default ``1``).
    min_confidence : float
        Minimum confidence threshold to keep a detection.
    """

    def __init__(
        self,
        languages: Optional[List[str]] = None,
        gpu: Optional[bool] = None,
        model_storage_directory: Optional[str] = None,
        download_enabled: bool = True,
        detect_network: str = "craft",
        paragraph: bool = True,
        calibrate_confidence: bool = True,
        batch_size: int = 1,
        min_confidence: float = 0.1,
    ) -> None:
        super().__init__(engine_name="easyocr")
        self._languages = languages or ["ar", "en"]
        self._gpu = gpu
        self._model_storage_directory = model_storage_directory
        self._download_enabled = download_enabled
        self._detect_network = detect_network
        self._paragraph = paragraph
        self._calibrate_confidence = calibrate_confidence
        self._batch_size = batch_size
        self._min_confidence = min_confidence

        # Lazy-loaded reader
        self._reader: Any = None

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_reader(self) -> Any:
        """Lazy-initialise the EasyOCR reader."""
        if self._reader is not None:
            return self._reader

        import easyocr

        # Determine GPU usage
        gpu = self._gpu
        if gpu is None:
            try:
                import torch
                gpu = torch.cuda.is_available()
            except ImportError:
                gpu = False
            self._logger.info("GPU auto-detection: %s.", gpu)

        kwargs: Dict[str, Any] = {
            "lang_list": self._languages,
            "gpu": gpu,
            "download_enabled": self._download_enabled,
            "detect_network": self._detect_network,
            "verbose": False,
        }
        if self._model_storage_directory is not None:
            kwargs["model_storage_directory"] = self._model_storage_directory

        self._logger.info(
            "Initialising EasyOCR (langs=%s, gpu=%s, paragraph=%s).",
            self._languages, gpu, self._paragraph,
        )
        self._reader = easyocr.Reader(**kwargs)
        self._gpu = gpu  # store resolved value
        return self._reader

    def _check_availability(self) -> None:
        """Verify EasyOCR is importable and a reader can be created."""
        import easyocr  # noqa: F401
        reader = self._init_reader()
        self._logger.info("EasyOCR reader ready (langs=%s).", self._languages)

    # ------------------------------------------------------------------
    # Core OCR
    # ------------------------------------------------------------------

    def ocr(self, image: ImageInput) -> OCRResult:
        """Run EasyOCR on a single image.

        Parameters
        ----------
        image : ImageInput
            File path, numpy array, or PIL Image.

        Returns
        -------
        OCRResult
            Recognition result with per-line bounding boxes and
            optional word-level data.
        """
        reader = self._init_reader()
        validated = self.validate_image(image) if not isinstance(image, np.ndarray) else image
        preprocessed = self.preprocess(validated)

        # EasyOCR expects RGB
        rgb = self._to_rgb(preprocessed)

        # Run detection + recognition
        t0 = time.perf_counter()
        detections = reader.readtext_batched(
            [rgb],
            batch_size=self._batch_size,
            paragraph=self._paragraph,
        )
        inference_time = time.perf_counter() - t0

        # reader.readtext_batched returns a list of lists
        # Each inner item: (bbox_points, text, confidence)
        page_detections: List[Tuple[Any, str, float]] = detections[0] if detections else []

        if not page_detections:
            return OCRResult(
                text="",
                confidence=0.0,
                bbox=None,
                engine_name=self.engine_name,
                processing_time=inference_time,
                metadata={
                    "languages": self._languages,
                    "gpu": self._gpu,
                    "paragraph": self._paragraph,
                },
            )

        # Build per-line results
        lines_text: List[str] = []
        line_confs: List[float] = []
        line_bboxes: List[BBox] = []
        word_level: List[tuple[str, float, BBox]] = []

        for bbox_pts, text, raw_conf in page_detections:
            text = text.strip()
            if not text:
                continue

            conf = _calibrate_confidence(raw_conf) if self._calibrate_confidence else raw_conf
            if conf < self._min_confidence:
                continue

            # Extract bounding box
            pts = np.array(bbox_pts, dtype=np.float64)
            x_min = float(pts[:, 0].min())
            y_min = float(pts[:, 1].min())
            x_max = float(pts[:, 0].max())
            y_max = float(pts[:, 1].max())
            bbox = BBox(x_min, y_min, x_max, y_max)

            lines_text.append(text)
            line_confs.append(conf)
            line_bboxes.append(bbox)

            # Store as a single "word" entry at line level for compatibility
            word_level.append((text, conf, bbox))

        if not lines_text:
            return OCRResult(
                text="",
                confidence=0.0,
                bbox=None,
                engine_name=self.engine_name,
                processing_time=inference_time,
                metadata={"languages": self._languages, "gpu": self._gpu},
            )

        # Full text (lines separated by newlines)
        full_text = "\n".join(lines_text)
        avg_confidence = sum(line_confs) / len(line_confs)

        # Overall bounding box
        overall_bbox = BBox(
            x_min=min(b.x_min for b in line_bboxes),
            y_min=min(b.y_min for b in line_bboxes),
            x_max=max(b.x_max for b in line_bboxes),
            y_max=max(b.y_max for b in line_bboxes),
        )

        return OCRResult(
            text=full_text,
            confidence=avg_confidence,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            processing_time=inference_time,
            word_level=word_level,
            metadata={
                "languages": self._languages,
                "gpu": self._gpu,
                "paragraph": self._paragraph,
                "line_count": len(lines_text),
                "word_count": sum(len(t.split()) for t in lines_text),
                "calibrated": self._calibrate_confidence,
            },
        )

    def ocr_batch(self, images: Sequence[ImageInput]) -> List[OCRResult]:
        """Run EasyOCR on a batch of images.

        Uses EasyOCR's built-in batched inference for better GPU
        utilisation when ``batch_size > 1``.

        Parameters
        ----------
        images : sequence of ImageInput
            Input images.

        Returns
        -------
        list[OCRResult]
        """
        reader = self._init_reader()
        rgb_images: List[np.ndarray] = []

        for img in images:
            validated = self.validate_image(img) if not isinstance(img, np.ndarray) else img
            preprocessed = self.preprocess(validated)
            rgb_images.append(self._to_rgb(preprocessed))

        t0 = time.perf_counter()
        all_detections = reader.readtext_batched(
            rgb_images,
            batch_size=self._batch_size,
            paragraph=self._paragraph,
        )
        inference_time = time.perf_counter() - t0

        results: List[OCRResult] = []
        for idx, page_dets in enumerate(all_detections):
            result = self._build_result_from_detections(
                page_dets, inference_time / max(len(images), 1),
            )
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result_from_detections(
        self,
        detections: List[Tuple[Any, str, float]],
        processing_time: float,
    ) -> OCRResult:
        """Convert raw EasyOCR detections to an :class:`OCRResult`."""
        lines_text: List[str] = []
        line_confs: List[float] = []
        line_bboxes: List[BBox] = []
        word_level: List[tuple[str, float, BBox]] = []

        for bbox_pts, text, raw_conf in detections:
            text = text.strip()
            if not text:
                continue
            conf = _calibrate_confidence(raw_conf) if self._calibrate_confidence else raw_conf
            if conf < self._min_confidence:
                continue

            pts = np.array(bbox_pts, dtype=np.float64)
            bbox = BBox(
                x_min=float(pts[:, 0].min()),
                y_min=float(pts[:, 1].min()),
                x_max=float(pts[:, 0].max()),
                y_max=float(pts[:, 1].max()),
            )
            lines_text.append(text)
            line_confs.append(conf)
            line_bboxes.append(bbox)
            word_level.append((text, conf, bbox))

        if not lines_text:
            return OCRResult(
                text="",
                confidence=0.0,
                bbox=None,
                engine_name=self.engine_name,
                processing_time=processing_time,
            )

        full_text = "\n".join(lines_text)
        avg_conf = sum(line_confs) / len(line_confs)
        overall_bbox = BBox(
            x_min=min(b.x_min for b in line_bboxes),
            y_min=min(b.y_min for b in line_bboxes),
            x_max=max(b.x_max for b in line_bboxes),
            y_max=max(b.y_max for b in line_bboxes),
        )

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            processing_time=processing_time,
            word_level=word_level,
            metadata={"languages": self._languages, "gpu": self._gpu},
        )

    @staticmethod
    def _to_rgb(image: np.ndarray) -> np.ndarray:
        """Ensure image is RGB uint8 (EasyOCR requirement)."""
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        if image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return image

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release EasyOCR resources."""
        # EasyOCR's Reader does not expose an explicit close/cleanup
        # method.  GPU memory is managed by PyTorch.
        if self._reader is not None:
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
        self._reader = None
        super().close()