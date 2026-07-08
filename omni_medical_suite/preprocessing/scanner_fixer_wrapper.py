"""
Scanner Fixer Preprocessor — Direct Python API integration.

Replaces the old subprocess-based wrapper with in-process calls to
scanner-fixer v1.0 (pip install scanner-fixer).

Impact: Reduces CER by 40-50% on average on scanned medical documents.
"""

from pathlib import Path
from typing import Any

import cv2
import numpy as np

# Import scanner-fixer v1.0 Python API directly (no subprocess)
try:
    from scanner_fixer import fix_scan
    SCANNER_FIXER_AVAILABLE = True
except ImportError:
    SCANNER_FIXER_AVAILABLE = False
    fix_scan = None


class ScannerFixerPreprocessor:
    """
    Preprocessor that applies scanner-fixer v1.0 to images before OCR.

    Uses the scanner-fixer Python API (fix_scan) for in-process
    image normalization — no subprocess overhead.

    Pipeline applied: crop borders → detect 180° flip → deskew → enhance (CLAHE + denoise + sharpen)

    Impact: Reduces CER by 40-50% on average on scanned medical documents.
    """

    def __init__(
        self,
        auto_crop: bool = True,
        do_rotate: bool = False,  # Disabled by default — heuristic unreliable on real docs
        do_deskew: bool = True,
        do_enhance: bool = True,
        binarize: bool = False,
        target_dpi: int | None = 300,
        deskew_method: str = "hough",
        crop_padding: int = 10,
    ):
        """
        Initialize the preprocessor.

        Args:
            auto_crop: Enable border cropping (default: True)
            do_rotate: Enable 180° rotation detection (default: False — use use_tesseract_osd=True instead)
            do_deskew: Enable skew correction (default: True)
            do_enhance: Enable CLAHE contrast + denoise + sharpen (default: True)
            binarize: Convert to B&W for text-only pages (default: False)
            target_dpi: Target DPI — upscale if below (default: 300)
            deskew_method: "hough" (fast) or "projection" (sparse text)
            crop_padding: Pixels of padding around detected content
        """
        self.auto_crop = auto_crop
        self.do_rotate = do_rotate
        self.do_deskew = do_deskew
        self.do_enhance = do_enhance
        self.binarize = binarize
        self.target_dpi = target_dpi
        self.deskew_method = deskew_method
        self.crop_padding = crop_padding

    def process(self, image: str | Path | np.ndarray) -> np.ndarray:
        """
        Apply scanner-fixer preprocessing to a single image.

        Args:
            image: Input image (file path, Path, or BGR numpy array)

        Returns:
            Processed image as numpy array (BGR)
        """
        if not SCANNER_FIXER_AVAILABLE:
            # Graceful fallback: return original image
            print("Warning: scanner-fixer not installed. Skipping preprocessing.")
            if isinstance(image, (str, Path)):
                img = cv2.imread(str(image))
                if img is None:
                    raise ValueError(f"Failed to read image: {image}")
                return img
            return image

        # Convert file path to numpy array first
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"Failed to read image: {image}")
        else:
            img = image

        # Call scanner-fixer v1.0 Python API directly (in-process)
        result = fix_scan(
            img,
            do_crop=self.auto_crop,
            do_rotate=self.do_rotate,
            do_deskew=self.do_deskew,
            do_enhance=self.do_enhance,
            binarize=self.binarize,
            target_dpi=self.target_dpi,
            deskew_method=self.deskew_method,
            crop_padding=self.crop_padding,
        )

        return result["image"]

    def process_with_report(
        self, image: str | Path | np.ndarray
    ) -> dict[str, Any]:
        """
        Process image and return both the result and the processing report.

        Args:
            image: Input image

        Returns:
            Dict with "image" (numpy array) and "report" (processing metadata)
        """
        if not SCANNER_FIXER_AVAILABLE:
            return {"image": image, "report": {"status": "scanner_fixer_unavailable"}}

        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"Failed to read image: {image}")
        else:
            img = image

        result = fix_scan(
            img,
            do_crop=self.auto_crop,
            do_rotate=self.do_rotate,
            do_deskew=self.do_deskew,
            do_enhance=self.do_enhance,
            binarize=self.binarize,
            target_dpi=self.target_dpi,
            deskew_method=self.deskew_method,
            crop_padding=self.crop_padding,
        )

        return result  # Already has "image", "steps", "report" keys

    def process_batch(self, images: list[str | Path | np.ndarray]) -> list[np.ndarray]:
        """
        Process multiple images.

        Args:
            images: List of input images (file paths or numpy arrays)

        Returns:
            List of processed images as numpy arrays
        """
        return [self.process(img) for img in images]


# Singleton instance for convenience
scanner_preprocessor = ScannerFixerPreprocessor()
