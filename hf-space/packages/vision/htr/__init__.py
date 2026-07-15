"""
وحدة التعرف على النصوص اليدوية (HTR) المتخصصة.
توفر: ArabicHandwrittenHTR, LineSegmenter, WordSegmenter, DottedRecovery
"""

from .arabic_htr import ArabicHandwrittenHTR, HTRResult
from .dotted_recovery import ArabicDottedRecovery
from .line_segmenter import ContourLineSegmenter, ProjectionProfileSegmenter, UNetLineSegmenter
from .trocr_finetuned import FineTunedTrOCR
from .word_segmenter import ArabicWordSegmenter

__all__ = [
    'ArabicDottedRecovery',
    'ArabicHandwrittenHTR',
    'ArabicWordSegmenter',
    'ContourLineSegmenter',
    'FineTunedTrOCR',
    'HTRResult',
    'ProjectionProfileSegmenter',
    'UNetLineSegmenter',
]
