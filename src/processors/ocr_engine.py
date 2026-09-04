# src/processors/ocr_engine.py
"""
Medical OCR engine with EasyOCR-first / Tesseract-fallback strategy.

Design:
  * Lazy-loads EasyOCR only if it is installed and `use_easyocr=True`.
  * Falls back to Tesseract (via ``pytesseract``) when EasyOCR is
    unavailable or returns an empty result.
  * Both backends accept a 2-D numpy array (grayscale) or a 3-D BGR array.
  * No network access. Both engines must be installed on the host.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Union

import numpy as np


class OCRError(RuntimeError):
    """Raised when no OCR backend is available."""


class MedicalOCREngine:
    """EasyOCR-first / Tesseract-fallback OCR engine."""

    def __init__(
        self,
        languages: Iterable[str] = ("ar", "en"),
        use_easyocr: bool = True,
        tesseract_lang: str = "ara+eng",
        psm: int = 6,
    ) -> None:
        self.languages = list(languages)
        self.use_easyocr = use_easyocr
        self._easyocr_reader = None
        self.tesseract_lang = tesseract_lang
        self.tesseract_config = f"--oem 3 --psm {psm}"

    # ── EasyOCR backend ─────────────────────────────────────────────────

    def _load_easyocr(self):
        if not self.use_easyocr:
            return None
        if self._easyocr_reader is None:
            try:
                import easyocr

                self._easyocr_reader = easyocr.Reader(self.languages, gpu=False)
            except Exception:
                self.use_easyocr = False
                return None
        return self._easyocr_reader

    def _extract_with_easyocr(self, image: np.ndarray) -> str:
        reader = self._load_easyocr()
        if reader is None:
            return ""
        result = reader.readtext(image, detail=0)
        return " ".join(result).strip()

    # ── Tesseract backend ───────────────────────────────────────────────

    def _extract_with_tesseract(self, image: np.ndarray) -> str:
        try:
            import pytesseract
        except Exception as exc:
            raise OCRError(
                "pytesseract is not installed. Install pytesseract and tesseract-ocr."
            ) from exc
        return pytesseract.image_to_string(
            image,
            lang=self.tesseract_lang,
            config=self.tesseract_config,
        ).strip()

    # ── Public API ─────────────────────────────────────────────────────

    def extract_text(self, image_input: Union[str, Path, np.ndarray]) -> str:
        image = image_input
        if isinstance(image_input, (str, Path)):
            import cv2

            image = cv2.imread(str(image_input))
            if image is None:
                raise ValueError(f"Cannot read image: {image_input}")

        if self.use_easyocr:
            try:
                text = self._extract_with_easyocr(image)
                if text:
                    return text
            except Exception:
                pass

        return self._extract_with_tesseract(image)
