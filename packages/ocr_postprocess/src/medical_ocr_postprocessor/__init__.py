"""
Medical OCR Postprocessor — معالج ما بعد OCR للأ نصوص الطبية
==============================================================

A post-processing engine for correcting and validating OCR output
from medical documents, with special support for Arabic script.

محرك لمعالجة وتصحيح مخرجات OCR للمستندات الطبية مع دعم خاص للنص العربي.
"""

__version__ = "0.1.0"
__author__ = "Dr. Abdulmalek"

from medical_ocr_postprocessor.core import PostProcessor

__all__ = ["PostProcessor", "__version__"]
