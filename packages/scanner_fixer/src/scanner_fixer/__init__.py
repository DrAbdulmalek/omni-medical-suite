"""
scanner-fixer: Pre-OCR image normalization for scanned documents.
Pipeline: crop → deskew → rotate → denoise → enhance contrast
"""

from .pipeline import fix_scan, fix_scan_batch
from .crop import auto_crop
from .deskew import deskew
from .rotate import auto_rotate
from .enhance import enhance_for_ocr
from .enhanced_preprocessor import DocumentPreprocessor as EnhancedPreprocessor
from .batch_pipeline import BatchProcessor
from .pdf_ocr_processor import PDFOCRProcessor

__version__ = "1.2.0"
__all__ = [
    "fix_scan",
    "fix_scan_batch",
    "auto_crop",
    "deskew",
    "auto_rotate",
    "enhance_for_ocr",
    "EnhancedPreprocessor",
    "BatchProcessor",
    "PDFOCRProcessor",
]