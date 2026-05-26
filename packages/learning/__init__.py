"""Unified Learning package for OmniMedical Suite.

Provides the :class:`UnifiedLearning` adapter that combines KNN
classification (30 features), active learning, pattern storage, and
feedback collection from both the medical-doc-processor and OmniFile
Processor projects.
"""

from modules.learning.pattern_db import PatternDB
from modules.learning.unified_learning import (
    ActiveLearningStrategy,
    FeatureExtractor,
    FeatureVector,
    FeedbackRecord,
    FeedbackStatus,
    ModelMetadata,
    PatternRecord,
    PredictionResult,
    TrainingEntry,
    UnifiedLearning,
    NUM_FEATURES,
    FEATURE_KEYS,
    DEFAULT_K,
)

__all__ = [
    "PatternDB",
    "UnifiedLearning",
    "ActiveLearningStrategy",
    "FeedbackStatus",
    "FeatureExtractor",
    "FeatureVector",
    "TrainingEntry",
    "PredictionResult",
    "PatternRecord",
    "FeedbackRecord",
    "ModelMetadata",
    "NUM_FEATURES",
    "FEATURE_KEYS",
    "DEFAULT_K",
]
