"""
OmniOCR — Unified OCR package for OmniMedical Suite
====================================================

This package provides a single entry-point for optical character recognition
across multiple backends.  The :class:`UnifiedOCR` adapter orchestrates a
configurable fallback chain so that callers never need to worry about which
engine is installed.

Quick start::

    from packages.omni_ocr import UnifiedOCR, OCRResult

    ocr = UnifiedOCR()
    result: OCRResult = ocr.process_image("document.png")
    print(result.text, result.engine)

Sub-modules
-----------
adapter
    The main :class:`UnifiedOCR` class and :class:`OCRResult` dataclass.
mixed_engine
    OmniFile's ``MixedLanguageOCR`` combining TrOCR + EasyOCR + PatternDB.
"""

from packages.omni_ocr.adapter import OCRResult, UnifiedOCR
from packages.omni_ocr.mixed_engine import MixedLanguageOCR, WordResult

__all__ = [
    "UnifiedOCR",
    "OCRResult",
    "MixedLanguageOCR",
    "WordResult",
]
