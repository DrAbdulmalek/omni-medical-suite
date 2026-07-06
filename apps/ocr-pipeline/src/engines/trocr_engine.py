"""
TrOCR Engine
============

Wraps Microsoft TrOCR (Transformer-based OCR) via HuggingFace
``transformers``.  Supports handwritten text recognition with
``microsoft/trocr-base-handwritten`` or ``microsoft/trocr-large-handwritten``,
and printed Arabic text with an Arabic-language processor.

Key features:

* GPU memory management with explicit cache clearing.
* Fallback from fine-tuned Arabic model to the base handwritten model.
* Batch inference support for processing multiple images at once.
* Configurable generation parameters (beam search, max length).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
from PIL import Image

from src.engines.base_engine import BBox, OCREngine, OCRResult, ImageInput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known model identifiers
# ---------------------------------------------------------------------------

TROCR_HANDWRITTEN_BASE = "microsoft/trocr-base-handwritten"
TROCR_HANDWRITTEN_LARGE = "microsoft/trocr-large-handwritten"
TROCR_PRINTED_BASE = "microsoft/trocr-base-printed"
TROCR_PRINTED_LARGE = "microsoft/trocr-large-printed"

# Arabic-specific fine-tuned models (community / custom).
# If these are not available locally, the engine falls back gracefully.
ARABIC_TROCR_MODELS: List[str] = [
    "microsoft/trocr-base-handwritten",  # default fallback
]


# ---------------------------------------------------------------------------
# TrOCREngine
# ---------------------------------------------------------------------------

class TrOCREngine(OCREngine):
    """Microsoft TrOCR engine for handwritten and printed text.

    TrOCR uses a vision encoder (ViT) and a text decoder (GPT-2) to
    perform end-to-end OCR.  It excels at handwritten text and can be
    fine-tuned for specific languages or domains.

    Parameters
    ----------
    model_name : str
        HuggingFace model identifier or local path.  Defaults to
        ``microsoft/trocr-base-handwritten``.
    processor_name : str | None
        Processor model identifier.  If *None*, defaults to
        *model_name*.
    arabic_model_name : str | None
        A fine-tuned Arabic TrOCR model path/identifier.  If the model
        cannot be loaded, the engine falls back to the base *model_name*.
    device : str
        ``"cuda"``, ``"cpu"``, or ``"mps"``.
    use_fp16 : bool
        Use half-precision (float16) on CUDA for faster inference.
    max_length : int
        Maximum number of tokens to generate.
    num_beams : int
        Beam width for beam-search decoding.
    early_stopping : bool
        Stop beam search when all beams are finished.
    batch_size : int
        Number of images per batch during ``ocr_batch``.
    min_image_width : int
        Minimum image width in pixels (smaller images are up-scaled).
    min_image_height : int
        Minimum image height in pixels.
    """

    def __init__(
        self,
        model_name: str = TROCR_HANDWRITTEN_BASE,
        processor_name: Optional[str] = None,
        arabic_model_name: Optional[str] = None,
        device: Optional[str] = None,
        use_fp16: bool = True,
        max_length: int = 512,
        num_beams: int = 4,
        early_stopping: bool = True,
        batch_size: int = 4,
        min_image_width: int = 384,
        min_image_height: int = 384,
    ) -> None:
        super().__init__(engine_name="trocr")
        self._model_name = model_name
        self._processor_name = processor_name or model_name
        self._arabic_model_name = arabic_model_name
        self._max_length = max_length
        self._num_beams = num_beams
        self._early_stopping = early_stopping
        self._batch_size = batch_size
        self._min_image_width = min_image_width
        self._min_image_height = min_image_height

        # Resolve device
        self._device = device or self._auto_detect_device()
        self._use_fp16 = use_fp16 and (self._device == "cuda")

        # Lazy-loaded components
        self._processor: Any = None
        self._model: Any = None
        self._using_arabic_model: bool = False

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_detect_device() -> str:
        """Detect the best available compute device."""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        except ImportError:
            return "cpu"

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_model(self) -> None:
        """Initialise the TrOCR model and processor with fallback logic.

        Priority:
        1. Load the Arabic fine-tuned model if specified and available.
        2. Fall back to the base model.
        """
        if self._model is not None:
            return

        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        # Determine dtype
        import torch
        torch_dtype = torch.float16 if self._use_fp16 else torch.float32

        # Try Arabic fine-tuned model first
        if self._arabic_model_name is not None:
            self._using_arabic_model = self._try_load_model(
                self._arabic_model_name, torch_dtype,
            )
            if self._using_arabic_model:
                self._logger.info(
                    "Loaded Arabic TrOCR model: %s.", self._arabic_model_name,
                )
                return
            else:
                self._logger.warning(
                    "Arabic model '%s' could not be loaded; "
                    "falling back to base model.",
                    self._arabic_model_name,
                )

        # Load base model
        self._try_load_model(self._model_name, torch_dtype)
        self._logger.info(
            "Loaded base TrOCR model: %s on %s.",
            self._model_name, self._device,
        )

    def _try_load_model(
        self,
        model_name: str,
        torch_dtype: Any,
    ) -> bool:
        """Attempt to load a model; return *True* on success."""
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        try:
            processor = TrOCRProcessor.from_pretrained(model_name)
            model = VisionEncoderDecoderModel.from_pretrained(
                model_name, torch_dtype=torch_dtype,
            )
            model.to(self._device)
            model.eval()

            self._processor = processor
            self._model = model
            return True

        except Exception as exc:
            self._logger.debug(
                "Failed to load model '%s': %s", model_name, exc,
            )
            return False

    def _check_availability(self) -> None:
        """Verify transformers and torch are installed."""
        import torch  # noqa: F401
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel  # noqa: F401
        self._init_model()

    # ------------------------------------------------------------------
    # Core OCR
    # ------------------------------------------------------------------

    def ocr(self, image: ImageInput) -> OCRResult:
        """Run TrOCR on a single image.

        Parameters
        ----------
        image : ImageInput
            File path, numpy array, or PIL Image.

        Returns
        -------
        OCRResult
            TrOCR produces a single text block without spatial
            information, so ``bbox`` is *None*.
        """
        self._init_model()
        assert self._processor is not None and self._model is not None

        validated = self.validate_image(image) if not isinstance(image, np.ndarray) else image
        preprocessed = self.preprocess(validated)

        # Convert to PIL RGB
        pil_img = self._to_pil_rgb(preprocessed)

        # Ensure minimum image size for ViT
        pil_img = self._ensure_min_size(pil_img)

        import torch

        t0 = time.perf_counter()

        # Prepare pixel values
        pixel_values = self._processor(
            pil_img, return_tensors="pt",
        ).pixel_values.to(self._device)

        # Generate text
        with torch.inference_mode():
            generated_ids = self._model.generate(
                pixel_values,
                max_length=self._max_length,
                num_beams=self._num_beams,
                early_stopping=self._early_stopping,
            )

        inference_time = time.perf_counter() - t0

        # Decode
        generated_text = self._processor.batch_decode(
            generated_ids, skip_special_tokens=True,
        )[0].strip()

        # TrOCR does not provide per-token confidence natively.
        # We assign a high default confidence when text is produced.
        confidence = 0.9 if generated_text else 0.0

        return OCRResult(
            text=generated_text,
            confidence=confidence,
            bbox=None,  # TrOCR has no spatial output
            engine_name=self.engine_name,
            processing_time=inference_time,
            word_level=None,
            metadata={
                "model": self._arabic_model_name if self._using_arabic_model else self._model_name,
                "device": self._device,
                "fp16": self._use_fp16,
                "num_beams": self._num_beams,
                "arabic_model": self._using_arabic_model,
                "image_size": pil_img.size,
            },
        )

    def ocr_batch(self, images: Sequence[ImageInput]) -> List[OCRResult]:
        """Run TrOCR on a batch of images with explicit batch inference.

        Images are grouped into batches of ``batch_size`` and processed
        together on the GPU for better throughput.

        Parameters
        ----------
        images : sequence of ImageInput

        Returns
        -------
        list[OCRResult]
        """
        self._init_model()
        assert self._processor is not None and self._model is not None

        import torch

        # Prepare all images
        pil_images: List[Image.Image] = []
        for img in images:
            validated = self.validate_image(img) if not isinstance(img, np.ndarray) else img
            preprocessed = self.preprocess(validated)
            pil_images.append(self._ensure_min_size(self._to_pil_rgb(preprocessed)))

        results: List[OCRResult] = []

        for batch_start in range(0, len(pil_images), self._batch_size):
            batch = pil_images[batch_start : batch_start + self._batch_size]
            t0 = time.perf_counter()

            # Prepare batch pixel values
            pixel_values = self._processor(
                batch, return_tensors="pt", padding=True,
            ).pixel_values.to(self._device)

            # Generate
            with torch.inference_mode():
                generated_ids = self._model.generate(
                    pixel_values,
                    max_length=self._max_length,
                    num_beams=self._num_beams,
                    early_stopping=self._early_stopping,
                )

            inference_time = time.perf_counter() - t0
            per_image_time = inference_time / len(batch)

            # Decode
            texts = self._processor.batch_decode(
                generated_ids, skip_special_tokens=True,
            )

            for text in texts:
                text = text.strip()
                confidence = 0.9 if text else 0.0
                results.append(OCRResult(
                    text=text,
                    confidence=confidence,
                    bbox=None,
                    engine_name=self.engine_name,
                    processing_time=per_image_time,
                    word_level=None,
                    metadata={
                        "model": self._arabic_model_name if self._using_arabic_model else self._model_name,
                        "device": self._device,
                        "fp16": self._use_fp16,
                        "num_beams": self._num_beams,
                        "arabic_model": self._using_arabic_model,
                    },
                ))

            # Clear GPU cache between batches to avoid OOM
            if self._device == "cuda":
                torch.cuda.empty_cache()

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_pil_rgb(image: np.ndarray) -> Image.Image:
        """Convert a numpy array (BGR or grayscale) to PIL RGB Image."""
        if image.ndim == 2:
            return Image.fromarray(image, mode="L").convert("RGB")
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        elif image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(image)

    def _ensure_min_size(self, pil_img: Image.Image) -> Image.Image:
        """Resize image if below minimum dimensions.

        TrOCR's ViT encoder works best with images of at least
        ``384 x 384`` pixels.  Smaller images are upscaled with
        Lanczos resampling.

        Parameters
        ----------
        pil_img : PIL.Image.Image

        Returns
        -------
        PIL.Image.Image
        """
        w, h = pil_img.size
        needs_resize = False
        new_w, new_h = w, h

        if w < self._min_image_width:
            scale = self._min_image_width / w
            new_w = self._min_image_width
            new_h = max(int(h * scale), self._min_image_height)
            needs_resize = True
        elif h < self._min_image_height:
            scale = self._min_image_height / h
            new_h = self._min_image_height
            new_w = max(int(w * scale), self._min_image_width)
            needs_resize = True

        if needs_resize:
            self._logger.debug(
                "Upscaling image from (%d, %d) to (%d, %d).",
                w, h, new_w, new_h,
            )
            return pil_img.resize((new_w, new_h), Image.LANCZOS)

        return pil_img

    # ------------------------------------------------------------------
    # GPU memory management
    # ------------------------------------------------------------------

    def clear_gpu_cache(self) -> None:
        """Explicitly free GPU memory.

        Call this after large batch operations or when switching
        between models to prevent out-of-memory errors.
        """
        try:
            import torch
            if self._device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
                allocated = torch.cuda.memory_allocated() / (1024 ** 2)
                reserved = torch.cuda.memory_reserved() / (1024 ** 2)
                self._logger.debug(
                    "GPU cache cleared. Allocated: %.1f MB, Reserved: %.1f MB.",
                    allocated, reserved,
                )
        except ImportError:
            pass

    def get_gpu_memory_usage(self) -> Dict[str, float]:
        """Return current GPU memory usage in MB.

        Returns
        -------
        dict[str, float]
            Keys: ``"allocated"``, ``"reserved"``, ``"max_allocated"``.
            Values in megabytes.  Returns zeros on CPU.
        """
        try:
            import torch
            if self._device == "cuda" and torch.cuda.is_available():
                return {
                    "allocated": torch.cuda.memory_allocated() / (1024 ** 2),
                    "reserved": torch.cuda.memory_reserved() / (1024 ** 2),
                    "max_allocated": torch.cuda.max_memory_allocated() / (1024 ** 2),
                }
        except ImportError:
            pass

        return {"allocated": 0.0, "reserved": 0.0, "max_allocated": 0.0}

    # ------------------------------------------------------------------
    # Switch model at runtime
    # ------------------------------------------------------------------

    def switch_to_arabic_model(self) -> bool:
        """Attempt to switch to the Arabic fine-tuned model.

        Returns
        -------
        bool
            *True* if the switch succeeded.
        """
        if self._arabic_model_name is None:
            self._logger.warning("No Arabic model name configured.")
            return False

        import torch
        torch_dtype = torch.float16 if self._use_fp16 else torch.float32

        # Free current model
        self._model = None
        self._processor = None
        self.clear_gpu_cache()

        success = self._try_load_model(self._arabic_model_name, torch_dtype)
        if success:
            self._using_arabic_model = True
            self._logger.info("Switched to Arabic model: %s.", self._arabic_model_name)
        else:
            # Reload base model
            self._try_load_model(self._model_name, torch_dtype)
            self._using_arabic_model = False
            self._logger.warning(
                "Failed to load Arabic model, re-loaded base model: %s.",
                self._model_name,
            )
        return success

    def switch_to_base_model(self) -> None:
        """Switch back to the base model."""
        if not self._using_arabic_model:
            return

        import torch
        torch_dtype = torch.float16 if self._use_fp16 else torch.float32

        self._model = None
        self._processor = None
        self.clear_gpu_cache()

        self._try_load_model(self._model_name, torch_dtype)
        self._using_arabic_model = False
        self._logger.info("Switched to base model: %s.", self._model_name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release model, processor, and GPU memory."""
        self._model = None
        self._processor = None
        self.clear_gpu_cache()
        super().close()