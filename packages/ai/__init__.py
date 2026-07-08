"""
OmniFile AI Processor — AI Module (Self-Learning & AI Refinement)
===================================================================
القدرات:
- مطابقة الأنماط البصرية باستخدام SSIM (Pattern Matching)
- قاعدة بيانات التصحيحات الذاتية (Pattern Database)
- تحسين النصوص عبر Google Gemini API (Gemini Refiner)
- التعلم النشط وتحسين النماذج عبر تصحيحات المستخدم (Active Learning)
"""
from packages.ai.active_learning import ActiveLearner, ActiveLearningDB
from packages.ai.gemini_refiner import GeminiRefiner
from packages.ai.pattern_matcher import PatternMatch, PatternMatcher
from packages.learning.pattern_db import PatternDB as PatternDatabase

__all__ = [
    "ActiveLearner",
    "ActiveLearningDB",
    "GeminiRefiner",
    "PatternDatabase",
    "PatternMatch",
    "PatternMatcher",
]
