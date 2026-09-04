# src/processors/image_processor.py
"""
Medical image preprocessing pipeline.

Goal: produce a clean binary image suitable for OCR (Tesseract / EasyOCR)
from raw medical document scans (EHR screenshots, lab reports, referral
letters, etc.).

Pipeline stages:
  1. Grayscale conversion (with BGRA→BGR fallback)
  2. Denoising (Non-local Means)
  3. Skew estimation + deskew (min-area rect on inverted threshold)
  4. Contrast enhancement (CLAHE)
  5. Adaptive thresholding (Gaussian)
  6. Optional upscaling for low-resolution inputs
  7. Hard cap on maximum dimension to keep OCR memory bounded

Each stage is idempotent and order-independent for the static helpers
(`to_grayscale`, `denoise`, `deskew`, `enhance_contrast`, `binarize`),
and `full_pipeline` applies them in the documented order.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class MedicalImageProcessor:
    """Preprocessing utilities for OCR-oriented medical images."""

    # ── Static helpers ─────────────────────────────────────────────────

    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        if image is None:
            raise ValueError("Image is None")
        if image.ndim == 2:
            return image
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return cv2.fastNlMeansDenoising(
                image,
                None,
                h=20,
                templateWindowSize=7,
                searchWindowSize=21,
            )
        return cv2.fastNlMeansDenoisingColored(
            image,
            None,
            h=20,
            hColor=20,
            templateWindowSize=7,
            searchWindowSize=21,
        )

    @staticmethod
    def _estimate_skew_angle(gray: np.ndarray, max_angle: float = 15.0) -> float:
        try:
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, binary = cv2.threshold(
                blurred,
                0,
                255,
                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
            )
            coords = np.column_stack(np.where(binary > 0))
            if len(coords) < 50:
                return 0.0
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            elif angle > 45:
                angle = -(90 - angle)
            angle = float(angle)
            if abs(angle) > max_angle:
                return 0.0
            return angle
        except Exception:
            return 0.0

    @classmethod
    def deskew(cls, image: np.ndarray) -> np.ndarray:
        gray = cls.to_grayscale(image)
        angle = cls._estimate_skew_angle(gray)
        if abs(angle) < 0.05:
            return image
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    @classmethod
    def enhance_contrast(cls, image: np.ndarray) -> np.ndarray:
        gray = cls.to_grayscale(image)
        clahe = cv2.createCLAHE(
            clipLimit=2.5,
            tileGridSize=(8, 8),
        )
        return clahe.apply(gray)

    @classmethod
    def binarize(cls, image: np.ndarray) -> np.ndarray:
        gray = cls.to_grayscale(image)
        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            21,
            10,
        )

    # ── Full pipeline ───────────────────────────────────────────────────

    @classmethod
    def full_pipeline(
        cls,
        image_path: str | Path,
        upscale: float = 1.5,
        max_side: int = 4000,
    ) -> np.ndarray:
        image_path = Path(image_path)
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")

        img = cls.to_grayscale(image)
        img = cls.denoise(img)
        img = cls.deskew(img)
        img = cls.enhance_contrast(img)
        img = cls.binarize(img)

        height, width = img.shape[:2]
        if max(height, width) < 1200:
            img = cv2.resize(
                img,
                None,
                fx=upscale,
                fy=upscale,
                interpolation=cv2.INTER_CUBIC,
            )

        height, width = img.shape[:2]
        if max(height, width) > max_side:
            scale = max_side / max(height, width)
            img = cv2.resize(
                img,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_AREA,
            )
        return img
