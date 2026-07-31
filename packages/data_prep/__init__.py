"""
Data Preparation Layer for Medical OCR Ecosystem
==================================================
Adapted from ai-fuel-engine, focused on medical document data preparation.

Modules:
    segmenter    — Smart document segmentation (hybrid strategy)
    dedup        — Medical-safe deduplication (exact + semantic + context protection)
    classifier   — Medical document classification (keyword + semantic layers)

Author: Dr. Abdulmalek
Version: 1.0.0
"""

from packages.data_prep.classifier import MedicalDocumentClassifier
from packages.data_prep.dedup import MedicalDeduplicationEngine
from packages.data_prep.segmenter import MedicalDocumentSegmenter

__all__ = [
    "MedicalDeduplicationEngine",
    "MedicalDocumentClassifier",
    "MedicalDocumentSegmenter",
]
