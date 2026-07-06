"""
Promotion pipeline for the Medical OCR Training Hub.

Provides a 4-stage promotion workflow (draft -> candidate -> approved -> production)
with automated readiness scoring, changelog generation, and state management.
"""

from .pipeline import PromotionPipeline
from .readiness import ReadinessScorer
from .changelog import AutoChangelog

__all__ = ["PromotionPipeline", "ReadinessScorer", "AutoChangelog"]