"""Unified Learning package for OmniMedical Suite.

Provides the :class:`UnifiedLearning` adapter that combines KNN
classification (30 features), active learning, pattern storage, and
feedback collection from both the medical-doc-processor and OmniFile
Processor projects.
"""

from packages.learning.pattern_db import PatternDB
from packages.learning.unified_learning import (
    DEFAULT_K,
    FEATURE_KEYS,
    NUM_FEATURES,
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
)

__all__ = [
    "DEFAULT_K",
    "FEATURE_KEYS",
    "NUM_FEATURES",
    "ActiveLearningStrategy",
    "FeatureExtractor",
    "FeatureVector",
    "FeedbackRecord",
    "FeedbackStatus",
    "ModelMetadata",
    "PatternDB",
    "PatternRecord",
    "PredictionResult",
    "TrainingEntry",
    "UnifiedLearning",
]
