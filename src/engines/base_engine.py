"""
Abstract Base OCR Engine
========================

Defines the ``OCREngine`` abstract base class and the ``OCRResult`` /
``BBox`` dataclasses that every concrete engine must produce.

All engine implementations inherit from :class:`OCREngine` and implement
:func:`ocr` and :func:`ocr_batch`.  The base class provides shared
validation, preprocessing hooks, and error-handling scaffolding.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Union

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ImageInput covers the most common types passed to OCR engines.
ImageInput = Union[str, np.ndarray, Image.Image, "PathLike"]


# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------

@dataclass
class BBox:
    """Axis-aligned bounding box ``(x_min, y_min, x_max, y_max)``.

    Coordinates are in absolute pixel values relative to the original
    image.  The origin ``(0, 0)`` is the top-left corner.

    Attributes
    ----------
    x_min : float
        Left edge x-coordinate.
    y_min : float
        Top edge y-coordinate.
    x_max : float
        Right edge x-coordinate.
    y_max : float
        Bottom edge y-coordinate.
    """

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        """Bounding box width."""
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        """Bounding box height."""
        return max(0.0, self.y_max - self.y_min)

    @property
    def area(self) -> float:
        """Bounding box area in square pixels."""
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        """Center point ``(cx, cy)``."""
        return (
            (self.x_min + self.x_max) / 2.0,
            (self.y_min + self.y_max) / 2.0,
        )

    def iou(self, other: BBox) -> float:
        """Compute Intersection-over-Union (IoU) with another bounding box.

        Parameters
        ----------
        other : BBox
            The other bounding box.

        Returns
        -------
        float
            IoU value in ``[0.0, 1.0]``.
        """
        xi1 = max(self.x_min, other.x_min)
        yi1 = max(self.y_min, other.y_min)
        xi2 = min(self.x_max, other.x_max)
        yi2 = min(self.y_max, other.y_max)

        intersection = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
        union = self.area + other.area - intersection
        return intersection / union if union > 0 else 0.0

    def contains(self, other: BBox) -> bool:
        """Return *True* if *other* is fully contained within this box."""
        return (
            self.x_min <= other.x_min
            and self.y_min <= other.y_min
            and self.x_max >= other.x_max
            and self.y_max >= other.y_max
        )


# ---------------------------------------------------------------------------
# OCR result
# ---------------------------------------------------------------------------

@dataclass
class OCRResult:
    """Structured output produced by every OCR engine.

    Attributes
    ----------
    text : str
        Recognised text (may span multiple lines).
    confidence : float
        Engine-reported confidence in ``[0.0, 1.0]``.
    bbox : BBox | None
        Bounding box of the recognised region, or *None* if the engine
        does not provide spatial information.
    engine_name : str
        Name of the engine that produced this result.
    processing_time : float
        Wall-clock seconds spent on this recognition call.
    word_level : list[tuple[str, float, BBox]] | None
        Optional word-level results ``(word, confidence, bbox)``.
        Engines that support hOCR or equivalent can populate this for
        finer-grained downstream processing.
    metadata : dict[str, Any]
        Arbitrary engine-specific metadata (e.g. PSM mode, language
        pair used, model identifier).
    """

    text: str
    confidence: float
    bbox: Optional[BBox] = None
    engine_name: str = ""
    processing_time: float = 0.0
    word_level: Optional[List[tuple[str, float, BBox]]] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class OCREngine(ABC):
    """Abstract base class for all OCR engines.

    Subclasses must implement :func:`ocr` and :func:`ocr_batch`.  The
    base class provides:

    * :func:`preprocess` — an overridable preprocessing hook.
    * :func:`validate_image` — input validation and conversion to
      ``numpy.ndarray``.
    * :func:`safe_ocr` — wraps :func:`ocr` with error handling and
      timing.
    * :func:`safe_ocr_batch` — wraps :func:`ocr_batch` with per-image
      error isolation.

    Parameters
    ----------
    engine_name : str
        Human-readable engine identifier (e.g. ``"tesseract"``).
    """

    def __init__(self, engine_name: str) -> None:
        self.engine_name = engine_name
        self._logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self._available: Optional[bool] = None

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def ocr(self, image: ImageInput) -> OCRResult:
        """Run OCR on a single image.

        Parameters
        ----------
        image : str | np.ndarray | PIL.Image.Image
            The image to process.  Accepts a file path, a numpy array
            (BGR or grayscale), or a PIL ``Image``.

        Returns
        -------
        OCRResult
            Structured recognition result.
        """
        ...

    @abstractmethod
    def ocr_batch(self, images: Sequence[ImageInput]) -> List[OCRResult]:
        """Run OCR on a batch of images.

        Parameters
        ----------
        images : sequence of image inputs
            Each element follows the same contract as :func:`ocr`.

        Returns
        -------
        list[OCRResult]
            One result per input image, in the same order.
        """
        ...

    # ------------------------------------------------------------------
    # Shared preprocessing hook
    # ------------------------------------------------------------------

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Optional preprocessing step applied before OCR.

        The default implementation converts to grayscale if the image
        is colour.  Subclasses may override to add engine-specific
        preprocessing (e.g. contrast enhancement for TrOCR).

        Parameters
        ----------
        image : numpy.ndarray
            Input image as a numpy array (BGR or grayscale).

        Returns
        -------
        numpy.ndarray
            Preprocessed image.
        """
        import cv2

        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            self._logger.debug("Converted BGR image to grayscale.")
            return gray
        return image

    # ------------------------------------------------------------------
    # Validation / conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_image(image: ImageInput) -> np.ndarray:
        """Validate and convert *image* to a ``numpy.ndarray`` (BGR).

        Accepts:

        * ``str`` / ``os.PathLike`` — loaded via OpenCV.
        * ``numpy.ndarray`` — returned as-is (assumed BGR/grayscale).
        * ``PIL.Image.Image`` — converted to BGR numpy array.

        Parameters
        ----------
        image : ImageInput
            The image to validate.

        Returns
        -------
        numpy.ndarray
            BGR or grayscale ``uint8`` numpy array.

        Raises
        ------
        TypeError
            If the input type is not supported.
        FileNotFoundError
            If a path is provided but does not exist.
        IOError
            If OpenCV cannot read the file.
        """
        import cv2

        if isinstance(image, np.ndarray):
            if image.size == 0:
                raise ValueError("Empty numpy array provided as image.")
            return image

        if isinstance(image, Image.Image):
            arr = np.array(image)
            if arr.ndim == 2:
                return arr  # grayscale
            # PIL is RGB; convert to BGR for OpenCV compatibility
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        # Treat as a file path
        path = str(image)
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Image file not found: {path}")

        arr = cv2.imread(path, cv2.IMREAD_COLOR)
        if arr is None:
            raise IOError(f"OpenCV could not read image: {path}")
        return arr

    # ------------------------------------------------------------------
    # Safe wrappers (error handling + timing)
    # ------------------------------------------------------------------

    def safe_ocr(self, image: ImageInput) -> OCRResult:
        """Run :func:`ocr` with timing, validation, and error handling.

        If the engine raises an exception, a fallback
        :class:`OCRResult` with empty text and zero confidence is
        returned so that callers never crash due to a single engine
        failure.

        Parameters
        ----------
        image : ImageInput
            Input image.

        Returns
        -------
        OCRResult
            Recognition result or fallback on error.
        """
        t0 = time.perf_counter()
        try:
            validated = self.validate_image(image)
            result = self.ocr(validated)
            result.processing_time = time.perf_counter() - t0
            result.engine_name = self.engine_name
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            self._logger.error(
                "OCR engine '%s' failed: %s (%.3fs)",
                self.engine_name, exc, elapsed,
                exc_info=True,
            )
            return OCRResult(
                text="",
                confidence=0.0,
                bbox=None,
                engine_name=self.engine_name,
                processing_time=elapsed,
                metadata={"error": str(exc)},
            )

    def safe_ocr_batch(
        self,
        images: Sequence[ImageInput],
    ) -> List[OCRResult]:
        """Run :func:`ocr_batch` with per-image error isolation.

        Each image is processed independently; if one fails, its slot
        contains a fallback :class:`OCRResult` and processing
        continues.

        Parameters
        ----------
        images : sequence of ImageInput
            Input images.

        Returns
        -------
        list[OCRResult]
            One result per image (fallback on error).
        """
        results: List[OCRResult] = []
        for idx, img in enumerate(images):
            self._logger.debug(
                "Processing batch image %d/%d with '%s'.",
                idx + 1, len(images), self.engine_name,
            )
            result = self.safe_ocr(img)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Availability checks
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the engine's backend is installed and ready.

        Caches the result after the first call.

        Returns
        -------
        bool
        """
        if self._available is not None:
            return self._available
        try:
            self._check_availability()
            self._available = True
        except Exception as exc:
            self._available = False
            self._logger.warning(
                "Engine '%s' is not available: %s", self.engine_name, exc,
            )
        return self._available

    def _check_availability(self) -> None:
        """Override in subclasses to verify dependencies are installed.

        Raise an exception (e.g. ``ImportError``) if a required
        dependency is missing.

        Raises
        ------
        ImportError
            If a required package is not installed.
        RuntimeError
            If the engine binary / model is not found.
        """
        raise NotImplementedError(
            f"Subclasses must implement _check_availability()."
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release resources (models, GPU memory, file handles).

        Subclasses should override this to clean up engine-specific
        resources.
        """
        self._logger.debug("Engine '%s' closed.", self.engine_name)

    def __enter__(self) -> OCREngine:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(engine_name={self.engine_name!r})"
        )