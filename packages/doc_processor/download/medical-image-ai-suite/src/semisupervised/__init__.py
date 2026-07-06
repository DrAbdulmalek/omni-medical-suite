"""
وحدة التعلّم شبه الخاضع للإشراف - Semi-Supervised Learning
استخراج إشارات تدريب ضعيفة من التقارير وتدريب النماذج
"""

from .weak_labels import WeakLabelExtractor, BinaryLabelExtractor, SegmentationLabelExtractor
from .trainer import SemiSupervisedTrainer

__all__ = [
    "WeakLabelExtractor",
    "BinaryLabelExtractor",
    "SegmentationLabelExtractor",
    "SemiSupervisedTrainer",
]
