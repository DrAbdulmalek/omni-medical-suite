"""
Unified OCR Adapter for OmniMedical Suite
==========================================

Consolidates OCR capabilities from two upstream projects into a single
configurable fallback chain:

  1. OmniFile Mixed Engine  (Tesseract + EasyOCR + Surya + TrOCR via PatternDB)
  2. Tesseract Direct       (pytesseract standalone)
  3. Mistral AI             (cloud-based Mistral OCR 3)
  4. EasyOCR                (standalone reader)

The engine priority is fully configurable through the ``OCR_ENGINE_ORDER``
environment variable.  A built-in LRU cache (max 50 entries) avoids
re-processing identical images within the same process lifetime.

Example::

    from packages.omni_ocr.adapter import UnifiedOCR

    ocr = UnifiedOCR()
    result = ocr.process_image("document.png")
    print(result.text, result.engine, result.confidence)

Authors:
    Dr Abdulmalek Tamer Al-husseini
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

ImagePath = str
ImageInput = Union[ImagePath, "np.ndarray", "PIL.Image.Image"]


# ---------------------------------------------------------------------------
# Unified result dataclass
# ---------------------------------------------------------------------------


@dataclass
class OCRResult:
    """Normalized result produced by every OCR engine.

    Attributes:
        text: The full extracted text (may be empty on failure).
        confidence: Average confidence in ``[0.0, 1.0]``.  ``0.0`` means
            the engine failed to produce any text.
        engine: Human-readable name of the engine that produced this result
            (e.g. ``"mixed_engine"``, ``"tesseract"``, ``"mistral"``,
            ``"easyocr"``).
        word_count: Number of recognised words / tokens.
        processing_time: Wall-clock seconds spent inside the engine.
        words: Optional list of per-word dicts with keys ``text``,
            ``confidence``, ``x``, ``y``, ``w``, ``h``.
        raw_result: Opaque engine-specific payload kept for debugging or
            downstream consumers that need extra metadata.
        error: Non-empty string when the engine raised an exception;
            empty string on success.
    """

    text: str = ""
    confidence: float = 0.0
    engine: str = ""
    word_count: int = 0
    processing_time: float = 0.0
    words: List[Dict[str, Any]] = field(default_factory=list)
    raw_result: Optional[Dict[str, Any]] = None
    error: str = ""

    # -- convenience helpers ------------------------------------------------

    @property
    def success(self) -> bool:
        """Return ``True`` when the engine produced at least one character."""
        return bool(self.text.strip()) and not self.error

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the result to a plain dictionary."""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "engine": self.engine,
            "word_count": self.word_count,
            "processing_time": self.processing_time,
            "words": self.words,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Supported engine identifiers
# ---------------------------------------------------------------------------


class OCREngineID(str, Enum):
    """Canonical identifiers for every supported OCR backend."""

    MIXED_ENGINE = "mixed_engine"
    TESSERACT = "tesseract"
    MISTRAL = "mistral"
    EASYOCR = "easyocr"

    @classmethod
    def all_ids(cls) -> List[str]:
        """Return every engine identifier in the default priority order."""
        return [e.value for e in cls]


# Default fallback chain when ``OCR_ENGINE_ORDER`` is not set.
_DEFAULT_ENGINE_ORDER: List[str] = [
    OCREngineID.MIXED_ENGINE,
    OCREngineID.TESSERACT,
    OCREngineID.MISTRAL,
    OCREngineID.EASYOCR,
]

# Environment variable that overrides the default order.
_ENV_ENGINE_ORDER = "OCR_ENGINE_ORDER"

# Maximum number of cached results.
_CACHE_MAX_SIZE = 50


# ---------------------------------------------------------------------------
# Lazy engine availability checks
# ---------------------------------------------------------------------------


def _is_mixed_engine_available() -> bool:
    """Check whether the OmniFile ``MixedLanguageOCR`` can be imported."""
    try:
        from packages.omni_ocr.mixed_engine import MixedLanguageOCR  # noqa: F401

        return True
    except Exception:  # ImportError, ModuleNotFoundError, etc.
        return False


def _is_tesseract_available() -> bool:
    """Check whether ``pytesseract`` (and the system binary) is usable."""
    try:
        import pytesseract  # noqa: F401
        import subprocess

        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _is_mistral_available() -> bool:
    """Check whether the ``MistralOCR`` client can be instantiated."""
    try:
        from packages.core.mistral_integration import MistralOCR

        ocr = MistralOCR()
        return ocr.is_available()
    except Exception:
        return False


def _is_easyocr_available() -> bool:
    """Check whether ``easyocr`` is importable."""
    try:
        import easyocr  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# UnifiedOCR
# ---------------------------------------------------------------------------


class UnifiedOCR:
    """Adapter that unifies multiple OCR backends behind a single API.

    The adapter walks through a configurable *fallback chain*: the first
    engine that returns non-empty text wins.  If every engine fails, the
    result carries an ``error`` string explaining what went wrong.

    Configuration (environment variable)::

        export OCR_ENGINE_ORDER=mixed_engine,tesseract,mistral,easyocr

    Caching:
        Results are cached in an LRU dict keyed on the SHA-256 of the
        input image bytes (or file path for file-based inputs).  The cache
        holds at most 50 entries by default.  Call :meth:`clear_cache` to
        evict everything.

    Usage::

        ocr = UnifiedOCR()

        # From a file path
        result = ocr.process_image("prescription.png")
        if result.success:
            print(result.text)

        # From a PIL Image
        from PIL import Image
        img = Image.open("scan.jpg")
        result = ocr.process_image(img)

        # From a numpy array
        import cv2
        arr = cv2.imread("scan.jpg")
        result = ocr.process_image(arr)
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        engine_order: Optional[Sequence[str]] = None,
        cache_max_size: int = _CACHE_MAX_SIZE,
        mistral_api_key: Optional[str] = None,
        tesseract_langs: str = "eng+ara",
        tesseract_config: str = "--oem 3 --psm 6",
        easyocr_languages: Optional[List[str]] = None,
    ) -> None:
        """Initialise the unified OCR adapter.

        Args:
            engine_order: Ordered list of engine identifiers to try.  When
                ``None`` the value is read from the ``OCR_ENGINE_ORDER``
                environment variable; if that is also unset the built-in
                default chain is used.
            cache_max_size: Maximum number of results to keep in the LRU
                cache.  Set to ``0`` to disable caching entirely.
            mistral_api_key: Override for the Mistral API key.  When
                ``None`` the key is read from ``MISTRAL_API_KEY`` env var
                inside ``MistralOCR``.
            tesseract_langs: Tesseract language string (default
                ``"eng+ara"``).
            tesseract_config: Tesseract configuration flags.
            easyocr_languages: Languages for the standalone EasyOCR reader.
                Defaults to ``["en", "ar"]``.
        """
        # Resolve engine order
        if engine_order is not None:
            self._engine_order: List[str] = list(engine_order)
        else:
            env_val = os.environ.get(_ENV_ENGINE_ORDER, "").strip()
            if env_val:
                self._engine_order = [
                    e.strip() for e in env_val.split(",") if e.strip()
                ]
            else:
                self._engine_order = list(_DEFAULT_ENGINE_ORDER)

        self._cache_max_size = cache_max_size
        self._tesseract_langs = tesseract_langs
        self._tesseract_config = tesseract_config
        self._easyocr_languages = easyocr_languages or ["en", "ar"]
        self._mistral_api_key = mistral_api_key

        # Internal caches & lazy-loaded engines
        self._result_cache: Dict[str, OCRResult] = {}
        self._cache_key_order: List[str] = []  # for manual LRU eviction
        self._mixed_engine: Any = None
        self._mixed_engine_loaded = False
        self._easyocr_reader: Any = None
        self._easyocr_loaded = False
        self._mistral_ocr: Any = None
        self._mistral_loaded = False

        # Log the resolved configuration
        logger.info("UnifiedOCR initialized with engine order: %s", self._engine_order)
        self._log_availability()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_image(
        self,
        image: ImageInput,
        languages: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> OCRResult:
        """Run OCR on *image* using the configured fallback chain.

        Args:
            image: A file path (``str``), a ``PIL.Image.Image``, or a
                ``numpy.ndarray`` (BGR or grayscale).  File paths are
                preferred when Mistral OCR is in the chain because that
                engine requires a file on disk.
            languages: Optional hint for language-aware engines.  When
                ``None`` the engine defaults are used (typically
                ``["en", "ar"]``).
            use_cache: Whether to consult / populate the LRU cache.

        Returns:
            An :class:`OCRResult` with the best available text.  If every
            engine in the chain fails, ``result.error`` will contain a
            summary and ``result.text`` will be empty.
        """
        # --- Caching ---------------------------------------------------
        cache_key: Optional[str] = None
        if use_cache and self._cache_max_size > 0:
            cache_key = self._make_cache_key(image)
            if cache_key and cache_key in self._result_cache:
                logger.debug("Cache hit for key %s", cache_key[:12])
                return self._result_cache[cache_key]

        # --- Resolve to a PIL image (and optionally a temp file) -------
        pil_image, temp_file_path = self._resolve_input(image)

        # --- Track errors across the chain ----------------------------
        errors: List[str] = []

        for engine_id in self._engine_order:
            try:
                result = self._dispatch(
                    engine_id=engine_id,
                    pil_image=pil_image,
                    file_path=temp_file_path or (image if isinstance(image, str) else None),
                    languages=languages,
                )

                if result.success:
                    # Cache the successful result
                    if use_cache and cache_key and self._cache_max_size > 0:
                        self._put_cache(cache_key, result)
                    return result

                # Engine returned but with no usable text
                msg = f"{engine_id}: no text produced"
                if result.error:
                    msg = f"{engine_id}: {result.error}"
                errors.append(msg)
                logger.debug("Engine %s returned no usable text", engine_id)

            except Exception as exc:
                errors.append(f"{engine_id}: {exc}")
                logger.warning(
                    "Engine %s raised an exception: %s", engine_id, exc,
                    exc_info=True,
                )

        # --- All engines failed ----------------------------------------
        error_summary = "; ".join(errors)
        logger.error("All OCR engines failed. Details: %s", error_summary)

        failure = OCRResult(
            engine="none",
            error=f"All engines failed. [{error_summary}]",
        )

        if use_cache and cache_key and self._cache_max_size > 0:
            self._put_cache(cache_key, failure)

        return failure

    def get_available_engines(self) -> List[str]:
        """Return a list of engines that are currently importable / usable.

        This performs lightweight checks and does **not** download models
        or make network calls.

        Returns:
            Sorted list of engine identifiers (e.g. ``["easyocr",
            "tesseract"]``).
        """
        checks = {
            OCREngineID.MIXED_ENGINE: _is_mixed_engine_available,
            OCREngineID.TESSERACT: _is_tesseract_available,
            OCREngineID.MISTRAL: _is_mistral_available,
            OCREngineID.EASYOCR: _is_easyocr_available,
        }
        available = [eid for eid, check in checks.items() if check()]
        return available

    def clear_cache(self) -> None:
        """Evict all entries from the LRU cache."""
        self._result_cache.clear()
        self._cache_key_order.clear()
        logger.debug("OCR result cache cleared")

    @property
    def engine_order(self) -> List[str]:
        """Return a copy of the current engine priority list."""
        return list(self._engine_order)

    # ------------------------------------------------------------------
    # Internal: engine dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        engine_id: str,
        pil_image: "PIL.Image.Image",
        file_path: Optional[str],
        languages: Optional[List[str]],
    ) -> OCRResult:
        """Route to the appropriate engine implementation.

        Args:
            engine_id: One of the values in :class:`OCREngineID`.
            pil_image: Normalised PIL RGB image.
            file_path: On-disk path (required by Mistral).
            languages: Optional language hints.

        Returns:
            An :class:`OCRResult`.

        Raises:
            RuntimeError: If the engine identifier is unknown.
        """
        dispatch_map = {
            OCREngineID.MIXED_ENGINE: self._run_mixed_engine,
            OCREngineID.TESSERACT: self._run_tesseract,
            OCREngineID.MISTRAL: self._run_mistral,
            OCREngineID.EASYOCR: self._run_easyocr,
        }

        handler = dispatch_map.get(engine_id)
        if handler is None:
            raise RuntimeError(f"Unknown OCR engine: {engine_id}")

        return handler(pil_image=pil_image, file_path=file_path, languages=languages)

    # ------------------------------------------------------------------
    # Engine: Mixed Engine (OmniFile MixedLanguageOCR)
    # ------------------------------------------------------------------

    def _run_mixed_engine(
        self,
        pil_image: "PIL.Image.Image",
        file_path: Optional[str],
        languages: Optional[List[str]],
    ) -> OCRResult:
        """Run the OmniFile ``MixedLanguageOCR`` on the image.

        The mixed engine operates on numpy arrays internally, so the PIL
        image is converted.  It combines TrOCR, EasyOCR, and pattern-based
        correction.

        Args:
            pil_image: Input PIL image.
            file_path: Ignored (used only for Mistral).
            languages: Language hint for the engine.

        Returns:
            Normalised :class:`OCRResult`.
        """
        import numpy as np

        start = time.time()

        engine = self._load_mixed_engine()
        if engine is None:
            return OCRResult(
                engine=OCREngineID.MIXED_ENGINE,
                error="MixedLanguageOCR could not be loaded",
            )

        img_array = np.array(pil_image)
        lang_hint = (languages[0] if languages else "en").split("-")[0]

        # Handle grayscale / RGB conversion
        if img_array.ndim == 2:
            img_array = cv2_color_gray_to_bgr(img_array)
        elif img_array.shape[2] == 4:
            img_array = img_array[:, :, :3]

        try:
            word_results = engine.extract_from_column(
                column_image=img_array,
                language_hint=lang_hint,
            )
        except Exception as exc:
            return OCRResult(
                engine=OCREngineID.MIXED_ENGINE,
                error=str(exc),
                processing_time=time.time() - start,
            )

        # Aggregate word results
        texts: List[str] = []
        confidences: List[float] = []
        words: List[Dict[str, Any]] = []

        for wr in word_results:
            if not wr.text.strip():
                continue
            texts.append(wr.text)
            confidences.append(wr.confidence)
            bbox = wr.bbox
            words.append(
                {
                    "text": wr.text,
                    "confidence": wr.confidence,
                    "x": bbox[0],
                    "y": bbox[1],
                    "w": bbox[2] - bbox[0],
                    "h": bbox[3] - bbox[1],
                    "language": wr.language,
                }
            )

        full_text = " ".join(texts) if texts else ""
        avg_conf = float(np.mean(confidences)) if confidences else 0.0

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            engine=OCREngineID.MIXED_ENGINE,
            word_count=len(texts),
            processing_time=time.time() - start,
            words=words,
        )

    def _load_mixed_engine(self) -> Any:
        """Lazily load and cache ``MixedLanguageOCR``."""
        if self._mixed_engine_loaded:
            return self._mixed_engine

        try:
            from packages.omni_ocr.mixed_engine import MixedLanguageOCR

            self._mixed_engine = MixedLanguageOCR(
                use_trocr=True,
                use_easyocr_fallback=True,
                min_confidence=0.5,
            )
            self._mixed_engine_loaded = True
            logger.info("MixedLanguageOCR loaded successfully")
        except Exception as exc:
            logger.warning("Failed to load MixedLanguageOCR: %s", exc)
            self._mixed_engine = None
            self._mixed_engine_loaded = True  # don't retry

        return self._mixed_engine

    # ------------------------------------------------------------------
    # Engine: Tesseract Direct
    # ------------------------------------------------------------------

    def _run_tesseract(
        self,
        pil_image: "PIL.Image.Image",
        file_path: Optional[str],
        languages: Optional[List[str]],
    ) -> OCRResult:
        """Run Tesseract OCR directly via ``pytesseract``.

        Args:
            pil_image: Input PIL image.
            file_path: Ignored.
            languages: Optional language hint (maps to Tesseract lang
                string).

        Returns:
            Normalised :class:`OCRResult`.
        """
        start = time.time()

        try:
            import pytesseract
        except ImportError:
            return OCRResult(
                engine=OCREngineID.TESSERACT,
                error="pytesseract is not installed",
            )

        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        langs = self._tesseract_langs
        if languages:
            # Map common codes to Tesseract language codes
            lang_map = {"ar": "ara", "en": "eng", "fr": "fra"}
            langs = "+".join(lang_map.get(l.split("-")[0], l) for l in languages)

        try:
            data = pytesseract.image_to_data(
                pil_image,
                lang=langs,
                config=self._tesseract_config,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as exc:
            return OCRResult(
                engine=OCREngineID.TESSERACT,
                error=str(exc),
                processing_time=time.time() - start,
            )

        texts: List[str] = []
        confidences: List[float] = []
        words: List[Dict[str, Any]] = []

        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text:
                continue
            try:
                conf = int(data["conf"][i]) / 100.0
            except (ValueError, TypeError):
                conf = 0.0
            if conf < 0.3:
                continue

            texts.append(text)
            confidences.append(conf)
            words.append(
                {
                    "text": text,
                    "confidence": conf,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                }
            )

        full_text = " ".join(texts) if texts else ""
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            engine=OCREngineID.TESSERACT,
            word_count=len(texts),
            processing_time=time.time() - start,
            words=words,
        )

    # ------------------------------------------------------------------
    # Engine: Mistral AI
    # ------------------------------------------------------------------

    def _run_mistral(
        self,
        pil_image: "PIL.Image.Image",
        file_path: Optional[str],
        languages: Optional[List[str]],
    ) -> OCRResult:
        """Run Mistral OCR 3 (cloud API).

        Mistral requires a file on disk, so if *file_path* is ``None``
        the PIL image is written to a temporary file and cleaned up
        afterwards.

        Args:
            pil_image: Input PIL image (used as fallback when *file_path*
                is ``None``).
            file_path: Path to the source file.
            languages: Ignored (Mistral auto-detects).

        Returns:
            Normalised :class:`OCRResult`.
        """
        start = time.time()
        cleanup = False

        engine = self._load_mistral()
        if engine is None:
            return OCRResult(
                engine=OCREngineID.MISTRAL,
                error="MistralOCR is not available (missing API key or package)",
            )

        # Ensure we have a file on disk
        if file_path is None or not os.path.isfile(file_path):
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            pil_image.save(tmp.name, "PNG")
            file_path = tmp.name
            cleanup = True

        try:
            mistral_result = engine.ocr_document(file_path)
        except Exception as exc:
            if cleanup:
                os.unlink(file_path)
            return OCRResult(
                engine=OCREngineID.MISTRAL,
                error=str(exc),
                processing_time=time.time() - start,
            )

        if cleanup:
            os.unlink(file_path)

        if mistral_result.get("error"):
            return OCRResult(
                engine=OCREngineID.MISTRAL,
                error=mistral_result["error"],
                processing_time=time.time() - start,
            )

        # Extract text from pages
        pages = mistral_result.get("pages", [])
        all_texts: List[str] = []
        for page in pages:
            md = page.get("markdown", "")
            if md.strip():
                all_texts.append(md.strip())

        full_text = "\n\n".join(all_texts) if all_texts else ""
        word_count = len(full_text.split()) if full_text else 0

        # Mistral doesn't provide per-word confidence; use a high default.
        confidence = 0.9 if full_text else 0.0

        return OCRResult(
            text=full_text,
            confidence=confidence,
            engine=OCREngineID.MISTRAL,
            word_count=word_count,
            processing_time=time.time() - start,
            raw_result=mistral_result,
        )

    def _load_mistral(self) -> Any:
        """Lazily load and cache ``MistralOCR``."""
        if self._mistral_loaded:
            return self._mistral_ocr

        try:
            from packages.core.mistral_integration import MistralOCR

            self._mistral_ocr = MistralOCR(api_key=self._mistral_api_key)
            if not self._mistral_ocr.is_available():
                logger.warning("MistralOCR loaded but API key is missing")
                self._mistral_ocr = None
            self._mistral_loaded = True
        except Exception as exc:
            logger.warning("Failed to load MistralOCR: %s", exc)
            self._mistral_ocr = None
            self._mistral_loaded = True

        return self._mistral_ocr

    # ------------------------------------------------------------------
    # Engine: EasyOCR
    # ------------------------------------------------------------------

    def _run_easyocr(
        self,
        pil_image: "PIL.Image.Image",
        file_path: Optional[str],
        languages: Optional[List[str]],
    ) -> OCRResult:
        """Run EasyOCR as a standalone reader.

        Args:
            pil_image: Input PIL image.
            file_path: Ignored.
            languages: Optional language codes.

        Returns:
            Normalised :class:`OCRResult`.
        """
        import numpy as np

        start = time.time()

        reader = self._load_easyocr()
        if reader is None:
            return OCRResult(
                engine=OCREngineID.EASYOCR,
                error="EasyOCR could not be loaded",
            )

        img_array = np.array(pil_image)

        try:
            raw_results = reader.readtext(img_array)
        except Exception as exc:
            return OCRResult(
                engine=OCREngineID.EASYOCR,
                error=str(exc),
                processing_time=time.time() - start,
            )

        if not raw_results:
            return OCRResult(
                engine=OCREngineID.EASYOCR,
                processing_time=time.time() - start,
            )

        texts: List[str] = []
        confidences: List[float] = []
        words: List[Dict[str, Any]] = []

        for bbox, text, conf in raw_results:
            if conf < 0.3 or not text.strip():
                continue
            texts.append(text)
            confidences.append(conf)

            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            x_min, y_min = int(min(x_coords)), int(min(y_coords))
            words.append(
                {
                    "text": text,
                    "confidence": conf,
                    "x": x_min,
                    "y": y_min,
                    "w": int(max(x_coords)) - x_min,
                    "h": int(max(y_coords)) - y_min,
                }
            )

        full_text = " ".join(texts) if texts else ""
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            engine=OCREngineID.EASYOCR,
            word_count=len(texts),
            processing_time=time.time() - start,
            words=words,
        )

    def _load_easyocr(self) -> Any:
        """Lazily load and cache the EasyOCR reader."""
        if self._easyocr_loaded:
            return self._easyocr_reader

        try:
            import easyocr

            self._easyocr_reader = easyocr.Reader(
                lang_list=self._easyocr_languages,
                gpu=False,
                verbose=False,
            )
            self._easyocr_loaded = True
            logger.info("EasyOCR loaded (languages: %s)", self._easyocr_languages)
        except Exception as exc:
            logger.warning("Failed to load EasyOCR: %s", exc)
            self._easyocr_reader = None
            self._easyocr_loaded = True

        return self._easyocr_reader

    # ------------------------------------------------------------------
    # Internal: input resolution & caching helpers
    # ------------------------------------------------------------------

    def _resolve_input(
        self, image: ImageInput
    ) -> Tuple["PIL.Image.Image", Optional[str]]:
        """Normalise *image* into a PIL RGB image and optional temp file.

        Args:
            image: File path, PIL Image, or numpy array.

        Returns:
            A ``(pil_image, temp_file_path)`` tuple.  *temp_file_path*
            is ``None`` unless the input was a file path.
        """
        from PIL import Image

        temp_file_path: Optional[str] = None

        if isinstance(image, str):
            # File path
            temp_file_path = image
            pil_image = Image.open(image).convert("RGB")
        elif _is_pil_image(image):
            pil_image = image.convert("RGB")
        elif _is_numpy_array(image):
            import numpy as np

            if image.ndim == 2:
                pil_image = Image.fromarray(image).convert("RGB")
            elif image.shape[2] == 3:
                # Assume BGR (OpenCV convention) -> RGB
                pil_image = Image.fromarray(image[:, :, ::-1]).convert("RGB")
            elif image.shape[2] == 4:
                pil_image = Image.fromarray(image[:, :, :3]).convert("RGB")
            else:
                pil_image = Image.fromarray(image).convert("RGB")
        else:
            raise TypeError(
                f"Unsupported image type: {type(image).__name__}. "
                "Expected str, PIL.Image.Image, or numpy.ndarray."
            )

        return pil_image, temp_file_path

    def _make_cache_key(self, image: ImageInput) -> Optional[str]:
        """Create a stable SHA-256 cache key for *image*.

        Args:
            image: The same input accepted by :meth:`process_image`.

        Returns:
            A hex digest string, or ``None`` if the key cannot be
            computed (e.g. in-memory array without serialisation).
        """
        try:
            if isinstance(image, str):
                # File path: use path + mtime as key
                mtime = os.path.getmtime(image)
                raw = f"{image}:{mtime}"
                return hashlib.sha256(raw.encode()).hexdigest()
            elif _is_pil_image(image):
                import io

                buf = io.BytesIO()
                image.save(buf, format="PNG")
                return hashlib.sha256(buf.getvalue()).hexdigest()
            elif _is_numpy_array(image):
                return hashlib.sha256(image.tobytes()).hexdigest()
        except Exception:
            logger.debug("Could not compute cache key for image", exc_info=True)
        return None

    def _put_cache(self, key: str, result: OCRResult) -> None:
        """Insert *result* into the LRU cache, evicting the oldest entry
        if the cache is full."""
        if key in self._result_cache:
            # Move to front
            self._cache_key_order.remove(key)

        self._result_cache[key] = result
        self._cache_key_order.insert(0, key)

        # Evict oldest entries when over capacity
        while len(self._cache_key_order) > self._cache_max_size:
            oldest = self._cache_key_order.pop()
            del self._result_cache[oldest]

    # ------------------------------------------------------------------
    # Internal: availability logging
    # ------------------------------------------------------------------

    def _log_availability(self) -> None:
        """Log which engines are importable at startup."""
        available = self.get_available_engines()
        logger.info(
            "OCR engine availability: %s (active order: %s)",
            available,
            self._engine_order,
        )
        unavailable = set(self._engine_order) - set(available)
        if unavailable:
            logger.warning(
                "Engines in chain but NOT available: %s. "
                "They will be skipped at runtime.",
                unavailable,
            )


# ---------------------------------------------------------------------------
# Module-level helpers (private)
# ---------------------------------------------------------------------------


def _is_pil_image(obj: Any) -> bool:
    """Return ``True`` if *obj* is a ``PIL.Image.Image`` instance."""
    try:
        from PIL import Image

        return isinstance(obj, Image.Image)
    except ImportError:
        return False


def _is_numpy_array(obj: Any) -> bool:
    """Return ``True`` if *obj* is a ``numpy.ndarray`` instance."""
    try:
        import numpy as np

        return isinstance(obj, np.ndarray)
    except ImportError:
        return False


def cv2_color_gray_to_bgr(gray: "np.ndarray") -> "np.ndarray":
    """Convert a grayscale ``numpy`` array to BGR (OpenCV convention).

    This helper avoids a hard dependency on ``cv2`` at module level.

    Args:
        gray: 2-D uint8 numpy array.

    Returns:
        3-D BGR numpy array.
    """
    try:
        import cv2

        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    except ImportError:
        import numpy as np

        return np.stack([gray, gray, gray], axis=-1)
