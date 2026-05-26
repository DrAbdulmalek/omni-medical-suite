"""
وحدة المعالجة النصية واللغوية (NLP & Translation)
===================================================
القدرات:
- تصنيف النصوص العربية والإنجليزية
- استخراج الكيانات المسماة (NER)
- الترجمة التقنية EN→AR
- التصحيح الإملائي الذكي (عربي + إنجليزي)
- كشف اللغة تلقائياً
- حماية المصطلحات التقنية من التصحيح
- معالجة النصوص العربية من اليمين لليسار (RTL)
- معالجة النصوص المختلطة (عربي + إنجليزي + أرقام)
- تصحيح النصوص باستخدام الذكاء الاصطناعي (GPT)
- نظام الكلمات المحمية الشامل (Protected Words)
- مولّد المراجع الدراسية (Study Guide Generator)
- خط أنابيب NLP الطبي الموحّد (Medical NLP Pipeline)
"""
from packages.nlp.text_classifier import TextClassifier
from packages.nlp.entity_extractor import EntityExtractor
from packages.nlp.translator import TechnicalTranslator
from packages.nlp.spell_corrector import SpellCorrector
from packages.nlp.language_detector import LanguageDetector
from packages.nlp.arabic_rtl import RTLFixer, is_rtl_text, get_text_direction
from packages.nlp.mixed_text import (
    detect_language,
    optimize_mixed_text,
    separate_text_components,
)
from packages.nlp.protected_words import ProtectedWordsManager
from packages.nlp.study_guide import StudyGuideGenerator
try:
    from packages.nlp.ai_corrector import AICorrector
except ImportError:  # تبعيات اختيارية مثل python-dotenv / openai
    AICorrector = None

from packages.nlp.pipeline import (
    MedicalNLPPipeline,
    NLPPipelineResult,
    StageResult,
    PipelineStage,
)

__all__ = [
    "TextClassifier", "EntityExtractor", "TechnicalTranslator",
    "SpellCorrector", "LanguageDetector",
    "RTLFixer", "is_rtl_text", "get_text_direction",
    "detect_language", "optimize_mixed_text", "separate_text_components",
    "ProtectedWordsManager",
    "StudyGuideGenerator",
    # Pipeline
    "MedicalNLPPipeline",
    "NLPPipelineResult",
    "StageResult",
    "PipelineStage",
]

if AICorrector is not None:
    __all__.append("AICorrector")
