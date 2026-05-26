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
"""
from packages.vision.ocr_engine import OCREngine
from packages.vision.pdf_processor import PDFProcessor
from packages.vision.image_preprocessor import ImagePreprocessor
from packages.vision.text_reconstructor import TextReconstructor
from packages.vision.result_fusion import ResultFusion, FusionStrategy
from packages.vision.layout_analyzer import LayoutAnalyzer
from packages.vision.table_extractor import TableExtractor
from packages.vision.video_ocr import VideoOCR, FrameResult, VideoTimeline
from packages.vision.data_augmentation import DataAugmentor
from packages.vision.dual_ocr_verifier import DualOCRVerifier
from packages.vision.batch_ocr import BatchMedicalOCR
from packages.vision.dataset_builder import DatasetBuilder
from packages.vision.medical_ocr import MedicalOCRProcessor, process_medical_pdf
from packages.vision.medical_ocr_gradio import create_medical_ocr_tab

__all__ = [
    "OCREngine",
    "PDFProcessor",
    "ImagePreprocessor",
    "TextReconstructor",
    "ResultFusion",
    "FusionStrategy",
    "LayoutAnalyzer",
    "TableExtractor",
    "VideoOCR",
    "FrameResult",
    "VideoTimeline",
    "DataAugmentor",
    "DualOCRVerifier",
    "BatchMedicalOCR",
    "DatasetBuilder",
    "MedicalOCRProcessor",
    "process_medical_pdf",
    "create_medical_ocr_tab",
]
