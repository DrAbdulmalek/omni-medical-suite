"""
normalize.py
Full normalization pipeline for scanned medical document images.

Pipeline steps (in order):
1. Deskew — correct small rotation angles
2. Auto-crop — remove scanner borders and excess whitespace
3. Resolution normalization — resize to fixed height (preserving aspect ratio)
4. Color mode standardization — convert to grayscale for OCR consistency
"""

import logging
import cv2
import numpy as np

from scanner_fixer.deskew import deskew
from scanner_fixer.crop import auto_crop
from scanner_fixer.enhance import get_estimated_dpi

logger = logging.getLogger(__name__)


def normalize_scanned_image(
    image: np.ndarray,
    target_height: int = 1600,
    crop_padding: int = 10,
    output_grayscale: bool = True,
) -> np.ndarray:
    """Full normalization pipeline for scanned documents.

    Applies deskew, auto-crop, resolution normalization, and optional
    grayscale conversion in sequence.  Returns a numpy array the caller
    can save as PNG (see :func:`save_normalized`).

    Args:
        image: Input image as a numpy array (BGR color or grayscale).
        target_height: Fixed output height in pixels.  Width is scaled
            proportionally to preserve the original aspect ratio.
        crop_padding: Padding in pixels passed to :func:`auto_crop`.
        output_grayscale: When True (default) the result is converted to
            single-channel grayscale, which is optimal for OCR and
            eliminates colour variation between scans.

    Returns:
        Normalized image as a numpy array (grayscale if *output_grayscale*
        is True, otherwise same colour mode as the resized intermediate).
    """
    if image is None or image.size == 0:
        raise ValueError("Input image is empty or None")

    # Log estimated DPI for debugging / provenance (no functional effect)
    estimated_dpi = get_estimated_dpi(image)
    if estimated_dpi is not None:
        logger.info("Estimated source DPI: %s", estimated_dpi)

    # ── Step 1: Deskew ─────────────────────────────────────────────────────
    image, skew_angle, skew_meta = deskew(image)
    logger.debug("Deskew: corrected %.2f° (uncertain=%s)", skew_angle, skew_meta.get("uncertain"))

    # ── Step 2: Auto-crop ──────────────────────────────────────────────────
    image = auto_crop(image, padding=crop_padding)
    logger.debug("Auto-crop: output size %dx%d", image.shape[1], image.shape[0])

    # ── Step 3: Resolution normalization (relative resize) ─────────────────
    h, w = image.shape[:2]
    if h != target_height:
        scale = target_height / h
        new_w = int(round(w * scale))
        # Use INTER_AREA for downscaling, INTER_LINEAR for upscaling
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        image = cv2.resize(image, (new_w, target_height), interpolation=interpolation)
        logger.debug(
            "Resized from %dx%d to %dx%d (scale=%.3f)",
            w, h, new_w, target_height, scale,
        )

    # ── Step 4: Color mode standardization ─────────────────────────────────
    if output_grayscale:
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            logger.debug("Converted BGR → grayscale")

    return image


def save_normalized(image: np.ndarray, output_path: str) -> str:
    """Save normalized image as lossless PNG.

    Args:
        image: Normalized image array (as returned by
            :func:`normalize_scanned_image`).
        output_path: Filesystem path for the output PNG file.  Parent
            directories are created automatically if they do not exist.

    Returns:
        The absolute path of the written file.
    """
    import os

    abs_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)

    success = cv2.imwrite(abs_path, image)
    if not success:
        raise IOError(f"cv2.imwrite failed for path: {abs_path}")

    logger.info("Saved normalized image to %s", abs_path)
    return abs_path
