"""
HandwrittenOCR - مشروع استخراج وتصحيح النصوص من الخط اليدوي
================================================================

v2.0 - نظام التحسين المستمر:
- Ensemble التعرف (TrOCR + EasyOCR)
- قاموس تصحيح يتعلم من مراجعات المستخدم
- تصدير بيانات Fine-tuning + رفع إلى HuggingFace
- تدريب LoRA على TrOCR
- إعادة تجميع الجمل (RTL)
"""

from config import Config
from src.correction import (
    apply_correction_dict,
    build_correction_dict,
    correct_text,
    init_correctors,
)
from src.database import HandwritingDB
from src.export import export_finetuning_dataset, push_to_huggingface
from src.finetuning import finetune_trocr_lora
from src.pdf_processor import PDFProcessor
from src.preprocessing import preprocess_image, smart_word_segmentation
from src.recognition import OCREngine
from src.reconstruction import reconstruct_sentences
from src.review_ui import ReviewUI

__version__ = "2.1.0"
