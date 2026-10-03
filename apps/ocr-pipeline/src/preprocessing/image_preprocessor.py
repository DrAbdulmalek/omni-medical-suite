"""
Image preprocessor for medical document OCR.

Provides a configurable pipeline of image enhancement steps specifically
tuned for scanned medical documents (prescriptions, lab reports, discharge
summaries).  All operations use OpenCV (``cv2``) and Pillow (``PIL``).

Typical pipeline order
----------------------
``resize_for_ocr`` → ``deskew`` → ``denoise`` → ``enhance_contrast`` →
``binarize`` → ``remove_borders``
"""

from __future__ import annotations

import logging
import math
from enum import Enum, auto

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step enum for pipeline configuration
# ---------------------------------------------------------------------------

class PreprocessStep(Enum):
    """Individual preprocessing steps that can be enabled/disabled."""

    DESKEW = auto()
    DENOISE = auto()
    ENHANCE_CONTRAST = auto()
    BINARIZE = auto()
    REMOVE_BORDERS = auto()
    RESIZE = auto()


# ---------------------------------------------------------------------------
# ImagePreprocessor
# ---------------------------------------------------------------------------

class ImagePreprocessor:
    """Configurable image preprocessing pipeline for medical OCR.

    Parameters
    ----------
    enabled_steps : list[PreprocessStep] | None
        Steps to include in the :meth:`preprocess` pipeline.  If *None*,
        all steps are enabled in the default order.
    target_dpi : int
        Target DPI for the resize step (default 300, standard for OCR).
    denoise_h : int
        Diameter of the pixel neighbourhood for non-local means denoising.
    denoise_template_window : int
        Size of the template patch for denoising.
    denoise_search_window : int
        Size of the search window for denoising.
    clahe_clip_limit : float
        CLAHE clip limit (0 = no clipping, higher = more contrast).
    clahe_grid_size : tuple[int, int]
        CLAHE grid size for histogram computation.
    adaptive_block_size : int
        Block size for adaptive thresholding (must be odd).
    adaptive_c : int
        Constant subtracted from the adaptive threshold mean.
    border_margin : int
        Number of pixels to trim when removing dark borders.
    """

    def __init__(
        self,
        enabled_steps: list[PreprocessStep] | None = None,
        target_dpi: int = 300,
        denoise_h: int = 10,
        denoise_template_window: int = 7,
        denoise_search_window: int = 21,
        clahe_clip_limit: float = 2.0,
        clahe_grid_size: tuple[int, int] = (8, 8),
        adaptive_block_size: int = 15,
        adaptive_c: int = 8,
        border_margin: int = 20,
    ) -> None:
        self._target_dpi = target_dpi
        self._denoise_h = denoise_h
        self._denoise_template_window = denoise_template_window
        self._denoise_search_window = denoise_search_window
        self._clahe_clip_limit = clahe_clip_limit
        self._clahe_grid_size = clahe_grid_size
        self._adaptive_block_size = adaptive_block_size
        self._adaptive_c = adaptive_c
        self._border_margin = border_margin

        # Default pipeline order
        self._default_order: list[PreprocessStep] = [
            PreprocessStep.RESIZE,
            PreprocessStep.DESKEW,
            PreprocessStep.DENOISE,
            PreprocessStep.ENHANCE_CONTRAST,
            PreprocessStep.BINARIZE,
            PreprocessStep.REMOVE_BORDERS,
        ]

        if enabled_steps is not None:
            self._steps = [s for s in self._default_order if s in enabled_steps]
        else:
            self._steps = list(self._default_order)

        logger.info(
            "ImagePreprocessor configured with steps: %s",
            [s.name for s in self._steps],
        )

    # ==================================================================
    # Public API
    # ==================================================================

    def preprocess(self, image: Image.Image) -> Image.Image:
        """Run the full preprocessing pipeline on *image*.

        Parameters
        ----------
        image : PIL.Image.Image
            Input document image (RGB or grayscale).

        Returns
        -------
        PIL.Image.Image
            Preprocessed image ready for OCR.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"Expected PIL.Image.Image, got {type(image).__name__}"
            )

        # Convert to numpy (BGR for OpenCV compatibility)
        img_array = self._pil_to_cv2(image)

        for step in self._steps:
            try:
                img_array = self._execute_step(step, img_array)
            except Exception as exc:
                logger.error(
                    "Preprocessing step '%s' failed: %s — continuing with "
                    "current image state.",
                    step.name,
                    exc,
                )

        # Convert back to PIL
        result = self._cv2_to_pil(img_array)
        return result

    # ==================================================================
    # Individual step implementations
    # ==================================================================

    def deskew(self, image: np.ndarray) -> np.ndarray:
        """Correct page rotation using Hough transform on text lines.

        Detects the dominant text-line angle and rotates the image to
        align text horizontally.

        Parameters
        ----------
        image : numpy.ndarray
            Grayscale image (``uint8``).

        Returns
        -------
        numpy.ndarray
            Deskewed image.
        """
        # Ensure grayscale
        gray = self._ensure_grayscale(image)

        # Binarise for line detection
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # Dilate to connect text components into lines
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (30, 5)  # wide horizontal kernel
        )
        dilated = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)

        # Hough line detection
        lines = cv2.HoughLinesP(
            dilated,
            rho=1,
            theta=np.pi / 180,
            threshold=80,
            minLineLength=100,
            maxLineGap=20,
        )

        if lines is None or len(lines) == 0:
            logger.debug("No lines detected for deskew — skipping rotation.")
            return image

        # Calculate median angle of detected lines
        angles: list[float] = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            angles.append(angle)

        median_angle = float(np.median(angles))

        # Only correct small skew angles (within ±15 degrees)
        if abs(median_angle) < 0.5:
            logger.debug("Skew angle %.2f° is negligible — skipping.", median_angle)
            return image
        if abs(median_angle) > 15:
            logger.warning(
                "Skew angle %.2f° exceeds ±15° threshold — skipping rotation "
                "to avoid mangling the image.",
                median_angle,
            )
            return image

        # Rotate the image
        (h, w) = gray.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)

        # Compute new bounding dimensions
        cos_val = abs(rotation_matrix[0, 0])
        sin_val = abs(rotation_matrix[0, 1])
        new_w = int((h * sin_val) + (w * cos_val))
        new_h = int((h * cos_val) + (w * sin_val))

        rotation_matrix[0, 2] += (new_w / 2) - center[0]
        rotation_matrix[1, 2] += (new_h / 2) - center[1]

        rotated = cv2.warpAffine(
            image,
            rotation_matrix,
            (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

        logger.info("Deskewed image by %.2f°.", median_angle)
        return rotated

    def denoise(self, image: np.ndarray) -> np.ndarray:
        """Remove noise using non-local means denoising.

        Uses OpenCV's fastNlMeansDenoising for grayscale or
        fastNlMeansDenoisingColored for colour images.

        Parameters
        ----------
        image : numpy.ndarray
            Input image.

        Returns
        -------
        numpy.ndarray
            Denoised image.
        """
        gray = self._ensure_grayscale(image)
        denoised = cv2.fastNlMeansDenoising(
            gray,
            None,
            h=self._denoise_h,
            templateWindowSize=self._denoise_template_window,
            searchWindowSize=self._denoise_search_window,
        )

        logger.debug("Denoising applied (h=%d).", self._denoise_h)

        # If the original image was colour, propagate to 3 channels
        if len(image.shape) == 3:
            denoised_bgr = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
            return denoised_bgr

        return denoised

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram
        Equalisation).

        Parameters
        ----------
        image : numpy.ndarray
            Input image.

        Returns
        -------
        numpy.ndarray
            Contrast-enhanced image.
        """
        gray = self._ensure_grayscale(image)

        clahe = cv2.createCLAHE(
            clipLimit=self._clahe_clip_limit,
            tileGridSize=self._clahe_grid_size,
        )
        enhanced = clahe.apply(gray)

        logger.debug("CLAHE applied (clip=%.1f, grid=%s).", self._clahe_clip_limit, self._clahe_grid_size)

        if len(image.shape) == 3:
            enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            return enhanced_bgr

        return enhanced

    def binarize(self, image: np.ndarray) -> np.ndarray:
        """Convert image to binary (black-and-white) using a combined
        Otsu + adaptive thresholding approach.

        For uniformly lit documents Otsu's method is sufficient.  For
        documents with uneven illumination (common in medical scans),
        adaptive thresholding produces better results.

        Parameters
        ----------
        image : numpy.ndarray
            Input image (grayscale preferred).

        Returns
        -------
        numpy.ndarray
            Binary image (``uint8``, values 0 or 255).
        """
        gray = self._ensure_grayscale(image)

        # Apply Gaussian blur to reduce noise before thresholding
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Try Otsu first
        _, otsu = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Compute the standard deviation of the grayscale image
        # High std → more uniform → Otsu is likely fine
        # Low std → potential uneven illumination → use adaptive
        std_dev = float(np.std(blurred))

        if std_dev > 50:
            # Relatively uniform illumination: use Otsu
            logger.debug("Binarisation: Otsu (std=%.1f).", std_dev)
            result = otsu
        else:
            # Uneven illumination: use adaptive thresholding
            block = self._adaptive_block_size
            if block % 2 == 0:
                block += 1  # ensure odd
            result = cv2.adaptiveThreshold(
                blurred,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=block,
                C=self._adaptive_c,
            )
            logger.debug(
                "Binarisation: adaptive (std=%.1f, block=%d, C=%d).",
                std_dev, block, self._adaptive_c,
            )

        return result

    def remove_borders(self, image: np.ndarray) -> np.ndarray:
        """Detect and remove dark borders around the document.

        Uses morphological operations to identify the document region
        and crops accordingly.

        Parameters
        ----------
        image : numpy.ndarray
            Input image (binary or grayscale).

        Returns
        -------
        numpy.ndarray
            Cropped image without borders.
        """
        gray = self._ensure_grayscale(image)

        # Threshold to binary
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Dilate to fill gaps
        kernel_size = max(3, min(binary.shape) // 100)
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_size, kernel_size)
        )
        dilated = cv2.dilate(binary, kernel, iterations=1)

        # Find bounding rectangle of the foreground (non-zero pixels)
        coords = cv2.findNonZero(dilated)
        if coords is None:
            logger.debug("No foreground detected — returning image as-is.")
            return image

        x, y, w, h = cv2.boundingRect(coords)

        # Add a small margin
        margin = self._border_margin
        img_h, img_w = image.shape[:2]
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(img_w - x, w + 2 * margin)
        h = min(img_h - y, h + 2 * margin)

        cropped = image[y : y + h, x : x + w]

        logger.debug(
            "Borders removed: cropped from (%d, %d) to (%d, %d).",
            img_w, img_h, w, h,
        )
        return cropped

    def resize_for_ocr(
        self,
        image: np.ndarray,
        target_dpi: int | None = None,
    ) -> np.ndarray:
        """Resize the image to a target DPI, maintaining aspect ratio.

        The function estimates the current DPI from the image dimensions
        (assuming standard A4/Letter physical size) and scales accordingly.

        Parameters
        ----------
        image : numpy.ndarray
            Input image.
        target_dpi : int | None
            Target DPI.  If *None*, uses ``self._target_dpi``.

        Returns
        -------
        numpy.ndarray
            Resized image.
        """
        dpi = target_dpi or self._target_dpi
        h, w = image.shape[:2]

        # Estimate current DPI based on standard page sizes
        # A4: 210 x 297 mm; Letter: 216 x 279 mm
        # Use A4 as reference
        a4_width_mm = 210.0
        a4_height_mm = 297.0
        a4_w_px_at_72dpi = int(a4_width_mm / 25.4 * 72)
        a4_h_px_at_72dpi = int(a4_height_mm / 25.4 * 72)

        # Estimate current DPI by comparing to A4
        est_dpi_w = w / a4_width_mm * 25.4 if w > 0 else 72
        est_dpi_h = h / a4_height_mm * 25.4 if h > 0 else 72

        # If the image is much larger than A4 at 72 DPI, it's likely
        # already scanned at a higher DPI — use a simpler estimate
        if w > a4_w_px_at_72dpi * 1.5 or h > a4_h_px_at_72dpi * 1.5:
            # Assume the image is already at ~150 DPI
            current_dpi = 150.0
        else:
            current_dpi = max(est_dpi_w, est_dpi_h)

        if current_dpi < 1:
            current_dpi = 72.0

        scale = dpi / current_dpi

        # Only upscale or downscale if the difference is significant
        if 0.9 <= scale <= 1.1:
            logger.debug(
                "Image is already near target DPI (%.0f vs %d) — skipping resize.",
                current_dpi,
                dpi,
            )
            return image

        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        # Use INTER_CUBIC for upscaling, INTER_AREA for downscaling
        interpolation = (
            cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
        )
        resized = cv2.resize(image, (new_w, new_h), interpolation=interpolation)

        logger.info(
            "Resized image: %dx%d → %dx%d (%.0f DPI → %d DPI).",
            w, h, new_w, new_h, current_dpi, dpi,
        )
        return resized

    # ==================================================================
    # Step dispatcher
    # ==================================================================

    def _execute_step(self, step: PreprocessStep, image: np.ndarray) -> np.ndarray:
        """Dispatch to the appropriate step method."""
        dispatch = {
            PreprocessStep.DESKEW: self.deskew,
            PreprocessStep.DENOISE: self.denoise,
            PreprocessStep.ENHANCE_CONTRAST: self.enhance_contrast,
            PreprocessStep.BINARIZE: self.binarize,
            PreprocessStep.REMOVE_BORDERS: self.remove_borders,
            PreprocessStep.RESIZE: self.resize_for_ocr,
        }
        method = dispatch.get(step)
        if method is None:
            logger.warning("Unknown preprocess step: %s", step)
            return image
        return method(image)

    # ==================================================================
    # Conversion utilities
    # ==================================================================

    @staticmethod
    def _pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
        """Convert a PIL Image to an OpenCV BGR numpy array."""
        if pil_image.mode == "RGBA":
            pil_image = pil_image.convert("RGB")
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        arr = np.array(pil_image)
        # RGB → BGR
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    @staticmethod
    def _cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
        """Convert an OpenCV BGR numpy array to a PIL Image."""
        if len(cv2_image.shape) == 2:
            # Grayscale
            return Image.fromarray(cv2_image, mode="L")
        # BGR → RGB
        rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    @staticmethod
    def _ensure_grayscale(image: np.ndarray) -> np.ndarray:
        """Convert to grayscale if not already."""
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


