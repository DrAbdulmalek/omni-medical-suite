"""
وحدة الرؤية الحاسوبية والتعرف على الملفات (CV & OCR)
======================================================
القدرات:
- استخراج النصوص من PDF والصور (TrOCR + EasyOCR + Tesseract + PaddleOCR)
- معالجة المخطوطات العربية اليدوية
- تحليل تخطيط المستندات واكتشاف الجداول
- تجزئة الصور إلى كلمات
- المعالجة المسبقة (CLAHE, denoise, deskew)
- إعادة تجميع النصوص RTL
- دمج نتائج عدة محركات OCR
- استخراج النصوص من الفيديو (Video OCR)
- توسيع بيانات التدريب للكتابة اليدوية (Data Augmentation)

OmniFile AI Processor - وحدة معالجة الملفات الذكية

.. note::
    جميع الاستيرادات تأخيرية (lazy) لتجنب فشل الاختبارات الخفيفة
    عند عدم توفر تبعيات ثقيلة مثل torch أو gradio.
    استخدم ``from packages.vision.text_reconstructor import TextReconstructor``
    (استيراد مباشر) بدلاً من ``from packages.vision import TextReconstructor``
    في الاختبارات والسكربتات الخفيفة.
"""

import importlib
import sys
from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import for all vision submodules.

    This prevents ImportError cascades when only a lightweight module
    (e.g. text_reconstructor) is needed but a heavy dependency
    (torch, gradio, paddleocr) is not installed.
    """
    _LAZY_MAP = {
        "BatchMedicalOCR": ("packages.vision.batch_ocr", "BatchMedicalOCR"),
        "DataAugmentor": ("packages.vision.data_augmentation", "DataAugmentor"),
        "DatasetBuilder": ("packages.vision.dataset_builder", "DatasetBuilder"),
        "DualOCRVerifier": ("packages.vision.dual_ocr_verifier", "DualOCRVerifier"),
        "ImagePreprocessor": ("packages.vision.image_preprocessor", "ImagePreprocessor"),
        "LayoutAnalyzer": ("packages.vision.layout_analyzer", "LayoutAnalyzer"),
        "MedicalOCRProcessor": ("packages.vision.medical_ocr", "MedicalOCRProcessor"),
        "process_medical_pdf": ("packages.vision.medical_ocr", "process_medical_pdf"),
        "create_medical_ocr_tab": ("packages.vision.medical_ocr_gradio", "create_medical_ocr_tab"),
        "OCREngine": ("packages.vision.ocr_engine", "OCREngine"),
        "PDFProcessor": ("packages.vision.pdf_processor", "PDFProcessor"),
        "FusionStrategy": ("packages.vision.result_fusion", "FusionStrategy"),
        "ResultFusion": ("packages.vision.result_fusion", "ResultFusion"),
        "TableExtractor": ("packages.vision.table_extractor", "TableExtractor"),
        "TextReconstructor": ("packages.vision.text_reconstructor", "TextReconstructor"),
        "VideoOCR": ("packages.vision.video_ocr", "VideoOCR"),
        "VideoTimeline": ("packages.vision.video_ocr", "VideoTimeline"),
        "FrameResult": ("packages.vision.video_ocr", "FrameResult"),
    }

    entry = _LAZY_MAP.get(name)
    if entry is None:
        raise AttributeError(f"module 'packages.vision' has no attribute {name!r}")

    module_path, attr = entry
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        raise AttributeError(
            f"Cannot import {name!r} from {module_path}: {exc}. "
            f"Install the required extras for this module."
        ) from exc

    obj = getattr(mod, attr)
    sys.modules[__name__].__dict__[name] = obj  # cache on first access
    return obj


__all__ = [
    "BatchMedicalOCR",
    "DataAugmentor",
    "DatasetBuilder",
    "DualOCRVerifier",
    "FrameResult",
    "FusionStrategy",
    "ImagePreprocessor",
    "LayoutAnalyzer",
    "MedicalOCRProcessor",
    "OCREngine",
    "PDFProcessor",
    "ResultFusion",
    "TableExtractor",
    "TextReconstructor",
    "VideoOCR",
    "VideoTimeline",
    "create_medical_ocr_tab",
    "process_medical_pdf",
]