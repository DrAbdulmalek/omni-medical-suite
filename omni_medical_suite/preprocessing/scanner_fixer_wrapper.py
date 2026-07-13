"""Thin wrapper that re-exports scanner-fixer normalization for the
``omni_medical_suite.preprocessing`` public API.

All real logic lives in
``packages/scanner_fixer/src/scanner_fixer/normalize.py`` — this module
only adapts the function signature so that downstream code can import
without reaching into the ``packages/`` sub-tree directly.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _import_normalize():
    """Lazy import so the package is importable even when scanner_fixer
    is not installed (e.g. in minimal CI environments)."""
    from packages.scanner_fixer.src.scanner_fixer.normalize import (
        normalize_scanned_image,
        save_normalized,
    )
    return normalize_scanned_image, save_normalized


class ScannerFixerPreprocessor:
    """Wraps :func:`normalize_scanned_image` as a stateless preprocessor.

    Usage::

        prep = ScannerFixerPreprocessor(target_height=1600)
        gray = prep.preprocess(bgr_image)
    """

    def __init__(
        self,
        target_height: int = 1600,
        crop_padding: int = 10,
        output_grayscale: bool = True,
        fit_mode: str = "aspect_resize",
        canvas_width: int = 1200,
        canvas_height: int = 1600,
    ) -> None:
        self.target_height = target_height
        self.crop_padding = crop_padding
        self.output_grayscale = output_grayscale
        self.fit_mode = fit_mode
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Normalize a scanned document image for OCR.

        Delegates to :func:`normalize_scanned_image` with the parameters
        configured at construction time.
        """
        normalize_fn, _save_fn = _import_normalize()
        return normalize_fn(
            image,
            target_height=self.target_height,
            crop_padding=self.crop_padding,
            output_grayscale=self.output_grayscale,
            fit_mode=self.fit_mode,
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
        )

    def preprocess_and_save(self, image: np.ndarray, output_path: str) -> str:
        """Normalize and save to *output_path*, returning the absolute path."""
        normalize_fn, save_fn = _import_normalize()
        result = normalize_fn(
            image,
            target_height=self.target_height,
            crop_padding=self.crop_padding,
            output_grayscale=self.output_grayscale,
            fit_mode=self.fit_mode,
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
        )
        return save_fn(result, output_path)


#: Convenience instance with default parameters.
scanner_preprocessor = ScannerFixerPreprocessor()