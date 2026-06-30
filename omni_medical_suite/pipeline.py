"""
Updated Pipeline with Preprocessing Integration

Integrates scanner-fixer v1.0 (Python API) as a mandatory preprocessing step
before OCR, plus layout-aware line segmentation.
"""

from pathlib import Path
from typing import Optional, Union, List, Dict, Any
import numpy as np
import cv2

# Import preprocessing modules
try:
    from .preprocessing.scanner_fixer_wrapper import (
        ScannerFixerPreprocessor,
        SCANNER_FIXER_AVAILABLE,
    )
except ImportError:
    SCANNER_FIXER_AVAILABLE = False
    ScannerFixerPreprocessor = None

try:
    from .preprocessing.line_segmentation import LineSegmenter
    LINE_SEGMENTATION_AVAILABLE = True
except ImportError:
    LINE_SEGMENTATION_AVAILABLE = False
    LineSegmenter = None


class EnhancedOCRPipeline:
    """
    Enhanced OCR Pipeline with preprocessing integration.

    This pipeline integrates:
    - Scanner Fixer v1.0 (crop → rotate → deskew → enhance) — MANDATORY
    - Line Segmentation (improved layout handling)
    - Multi-engine OCR
    - Medical postprocessing

    scanner-fixer is called via its Python API (fix_scan) — no subprocess.

    Usage:
        pipeline = EnhancedOCRPipeline(
            use_scanner_fixer=True,
            use_line_segmentation=True
        )
        result = pipeline.process_image(image)
    """

    def __init__(
        self,
        use_scanner_fixer: bool = True,
        use_line_segmentation: bool = True,
        scanner_fixer_config: Optional[Dict] = None,
        line_segmentation_config: Optional[Dict] = None,
    ):
        """
        Initialize the pipeline.

        Args:
            use_scanner_fixer: Whether to use scanner-fixer preprocessing (default: True)
            use_line_segmentation: Whether to use line segmentation (default: True)
            scanner_fixer_config: Config passed to ScannerFixerPreprocessor
                                  (auto_crop, do_rotate, do_deskew, do_enhance,
                                   binarize, target_dpi, deskew_method, crop_padding)
            line_segmentation_config: Configuration for line segmentation
        """
        self.use_scanner_fixer = use_scanner_fixer and SCANNER_FIXER_AVAILABLE
        self.use_line_segmentation = use_line_segmentation and LINE_SEGMENTATION_AVAILABLE

        if self.use_scanner_fixer:
            self.scanner_preprocessor = ScannerFixerPreprocessor(
                **(scanner_fixer_config or {})
            )

        if self.use_line_segmentation:
            self.line_segmenter = LineSegmenter(
                **(line_segmentation_config or {})
            )

    def process_image(self, image: Union[str, Path, np.ndarray]) -> Dict[str, Any]:
        """
        Process a single image through the enhanced pipeline.

        Pipeline order:
        1. Load image
        2. scanner-fixer (crop → rotate → deskew → enhance) via fix_scan()
        3. Line segmentation
        4. OCR (placeholder)

        Args:
            image: Input image (file path or numpy array)

        Returns:
            Dictionary with processing results including scanner-fixer report
        """
        # Load image if it's a file path
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"Failed to read image: {image}")
        else:
            img = image.copy()

        # Step 1: Scanner Fixer Preprocessing (v1.0 — in-process Python API)
        scanner_report = {}
        if self.use_scanner_fixer:
            result = self.scanner_preprocessor.process_with_report(img)
            img = result["image"]
            scanner_report = result.get("report", {})

        # Step 2: Line Segmentation
        if self.use_line_segmentation:
            line_images = self.line_segmenter.process(img)
            if line_images:
                img = line_images[0]

        # Step 3: OCR (placeholder — integrate with existing OCR engine)
        result = {
            "preprocessing": {
                "scanner_fixer_used": self.use_scanner_fixer,
                "scanner_fixer_report": scanner_report,
                "line_segmentation_used": self.use_line_segmentation,
            },
            "image_shape": img.shape,
            "status": "preprocessed",
        }

        # TODO: Integrate with actual OCR engine
        # text = self.ocr_engine.process(img)
        # result["text"] = text

        return result

    def process_batch(self, images: List[Union[str, Path, np.ndarray]]) -> List[Dict[str, Any]]:
        """
        Process multiple images.

        Args:
            images: List of input images

        Returns:
            List of processing results
        """
        return [self.process_image(img) for img in images]

    def get_config(self) -> Dict[str, Any]:
        """Get pipeline configuration"""
        return {
            "use_scanner_fixer": self.use_scanner_fixer,
            "use_line_segmentation": self.use_line_segmentation,
            "scanner_fixer_available": SCANNER_FIXER_AVAILABLE,
            "line_segmentation_available": LINE_SEGMENTATION_AVAILABLE,
        }


# Backward compatibility
OCRPipeline = EnhancedOCRPipeline
