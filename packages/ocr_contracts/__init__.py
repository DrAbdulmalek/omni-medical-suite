"""Data-integrity contracts for OCR provenance and training export."""

from .confidence import ConfidenceEvidence, combine_calibrated
from .normalization import normalize_for_matching, preserve_reference
from .training import ReviewStatus, TrainingSample, validate_training_sample

__all__ = [
    "ConfidenceEvidence", "combine_calibrated",
    "normalize_for_matching", "preserve_reference",
    "ReviewStatus", "TrainingSample", "validate_training_sample",
]
