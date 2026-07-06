"""
OCR Engines Package
====================

Provides a unified interface to multiple OCR backends for the
omni-medical-ocr-pipeline project.

Available engines
-----------------
- :class:`~src.engines.base_engine.OCREngine` — abstract base class.
- :class:`~src.engines.base_engine.OCRResult` — standardised result
  dataclass.
- :class:`~src.engines.base_engine.BBox` — axis-aligned bounding box.
- :class:`~src.engines.tesseract_engine.TesseractEngine` — Tesseract
  OCR with Arabic/English support and hOCR parsing.
- :class:`~src.engines.easyocr_engine.EasyOCREngine` — EasyOCR with
  GPU auto-detection and paragraph mode.
- :class:`~src.engines.paddleocr_engine.PaddleOCREngine` — PaddleOCR
  with table recognition and layout analysis.
- :class:`~src.engines.trocr_engine.TrOCREngine` — Microsoft TrOCR
  via HuggingFace transformers.
- :class:`~src.engines.ensemble.EnsembleOCR` — multi-engine fusion
  with weighted voting and text alignment.

Quick start
-----------
>>> from src.engines import TesseractEngine, EasyOCREngine, EnsembleOCR
>>> tesseract = TesseractEngine(lang="ara+eng")
>>> easyocr = EasyOCREngine(languages=["ar", "en"])
>>> ensemble = EnsembleOCR(
...     engines=[tesseract, easyocr],
...     weights={"tesseract": 0.4, "easyocr": 0.6},
... )
>>> result = ensemble.ocr("prescription.png")
>>> print(result.text)
"""

# Base classes and data structures
from src.engines.base_engine import BBox, OCRResult, OCREngine

# Concrete engine implementations
from src.engines.tesseract_engine import TesseractEngine
from src.engines.easyocr_engine import EasyOCREngine
from src.engines.paddleocr_engine import PaddleOCREngine
from src.engines.trocr_engine import TrOCREngine

# Ensemble / fusion
from src.engines.ensemble import EnsembleOCR

__all__ = [
    # Base
    "OCREngine",
    "OCRResult",
    "BBox",
    # Engines
    "TesseractEngine",
    "EasyOCREngine",
    "PaddleOCREngine",
    "TrOCREngine",
    # Ensemble
    "EnsembleOCR",
]