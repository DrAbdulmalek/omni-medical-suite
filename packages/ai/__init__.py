"""
OmniFile AI Processor — AI Module (Self-Learning & AI Refinement)
===================================================================
القدرات:
- مطابقة الأنماط البصرية باستخدام SSIM (Pattern Matching)
- قاعدة بيانات التصحيحات الذاتية (Pattern Database)
- تحسين النصوص عبر Google Gemini API (Gemini Refiner)
- التعلم النشط وتحسين النماذج عبر تصحيحات المستخدم (Active Learning)
"""
from packages.ai.pattern_db import PatternDatabase
from packages.ai.pattern_matcher import PatternMatcher, PatternMatch
from packages.ai.gemini_refiner import GeminiRefiner
from packages.ai.active_learning import ActiveLearningDB, ActiveLearner

__all__ = [
    "PatternDatabase",
    "PatternMatcher",
    "PatternMatch",
    "GeminiRefiner",
    "ActiveLearningDB",
    "ActiveLearner",
]
