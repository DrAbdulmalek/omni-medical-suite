"""
OmniFile AI Processor — AI Module (Self-Learning & AI Refinement)
===================================================================
القدرات:
- مطابقة الأنماط البصرية باستخدام SSIM (Pattern Matching)
- قاعدة بيانات التصحيحات الذاتية (Pattern Database)
- تحسين النصوص عبر Google Gemini API (Gemini Refiner)
- التعلم النشط وتحسين النماذج عبر تصحيحات المستخدم (Active Learning)

.. note::
    جميع الاستيرادات تأخيرية (lazy) لتجنب فشل الاستيراد عند عدم
    توفر تبعيات ثقيلة مثل torch.
"""

import importlib
import sys
from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import for AI submodules to avoid torch dependency cascade."""
    _LAZY_MAP = {
        "ActiveLearner": ("packages.ai.active_learning", "ActiveLearner"),
        "ActiveLearningDB": ("packages.ai.active_learning", "ActiveLearningDB"),
        "GeminiRefiner": ("packages.ai.gemini_refiner", "GeminiRefiner"),
        "PatternMatch": ("packages.ai.pattern_matcher", "PatternMatch"),
        "PatternMatcher": ("packages.ai.pattern_matcher", "PatternMatcher"),
        "PatternDatabase": ("packages.learning.pattern_db", "PatternDB"),
    }
    entry = _LAZY_MAP.get(name)
    if entry is None:
        raise AttributeError(f"module 'packages.ai' has no attribute {name!r}")
    module_path, attr = entry
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        raise AttributeError(
            f"Cannot import {name!r} from {module_path}: {exc}"
        ) from exc
    obj = getattr(mod, attr)
    sys.modules[__name__].__dict__[name] = obj
    return obj


__all__ = [
    "ActiveLearner",
    "ActiveLearningDB",
    "GeminiRefiner",
    "PatternDatabase",
    "PatternMatch",
    "PatternMatcher",
]