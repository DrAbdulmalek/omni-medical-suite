"""
Unified Learning Adapter for OmniMedical Suite
================================================

Combines learning/training capabilities from both parent projects:

- **medical-doc-processor**: KNN classifier with 30 features, trainable algorithms
- **OmniFile_Processor**: Active Learning, Pattern DB, User Pattern DB,
  TrOCR Arabic Trainer, Finetuning

This adapter provides a single ``UnifiedLearning`` entry-point with:

- ``predict()``           — KNN-based classification / settings prediction
- ``train()``             — ingest labelled data and update the KNN model
- ``active_learn()``      — uncertainty-sampling & query-by-committee loops
- ``store_pattern()``     — persist correction / word patterns
- ``suggest_correction()``— look up previously seen patterns
- ``collect_feedback()``  — record user feedback for downstream learning

All state is serialised to JSON for lightweight persistence.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_FEATURES: int = 30
"""Number of feature dimensions in the KNN classifier.

The original medical-doc-processor used 7 raw image features
(width, height, aspectRatio, blurScore, brightness, edgeDensity, borderNoise).
This adapter expands to 30 dimensions by adding derived / text features so
that the KNN can leverage richer signal (texture histograms, character
n-gram stats, layout ratios, etc.).
"""

FEATURE_KEYS: List[str] = [
    # --- original 7 image features ---
    "width",
    "height",
    "aspect_ratio",
    "blur_score",
    "brightness",
    "edge_density",
    "border_noise",
    # --- extended image features (8-15) ---
    "contrast",
    "sharpness",
    "text_density",
    "whitespace_ratio",
    "horizontal_line_score",
    "vertical_line_score",
    "ink_coverage",
    "skew_score",
    # --- text / OCR features (16-23) ---
    "char_count",
    "word_count",
    "avg_word_length",
    "digit_ratio",
    "arabic_char_ratio",
    "latin_char_ratio",
    "punctuation_ratio",
    "unique_word_ratio",
    # --- layout / medical features (24-30) ---
    "line_spacing_ratio",
    "margin_uniformity",
    "header_score",
    "footer_score",
    "table_score",
    "medical_term_score",
    "confidence_score",
]
"""Ordered list of the 30 feature keys."""

DEFAULT_K: int = 5
"""Default number of nearest neighbours for KNN."""

DEFAULT_CONFIDENCE_FLOOR: float = 0.30
"""Minimum prediction confidence returned."""

DEFAULT_CONFIDENCE_CEIL: float = 0.98
"""Maximum prediction confidence returned."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActiveLearningStrategy(str, Enum):
    """Supported active-learning sampling strategies."""
    UNCERTAINTY = "uncertainty"
    QUERY_BY_COMMITTEE = "query_by_committee"
    DIVERSITY = "diversity"


class FeedbackStatus(str, Enum):
    """Possible statuses for a feedback record."""
    VERIFIED = "verified"
    REJECTED = "rejected"
    PENDING = "pending"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FeatureVector:
    """A 30-dimensional feature vector with typed accessors.

    Attributes:
        values: Raw list of 30 float values aligned with ``FEATURE_KEYS``.
    """
    values: List[float] = field(default_factory=lambda: [0.0] * NUM_FEATURES)

    def __post_init__(self) -> None:
        if len(self.values) != NUM_FEATURES:
            raise ValueError(
                f"FeatureVector must have exactly {NUM_FEATURES} values, "
                f"got {len(self.values)}"
            )

    # --- convenience -------------------------------------------------------

    def to_dict(self) -> Dict[str, float]:
        """Return a mapping from feature key to value."""
        return dict(zip(FEATURE_KEYS, self.values))

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "FeatureVector":
        """Construct from a dict (missing keys default to 0.0)."""
        values = [float(data.get(k, 0.0)) for k in FEATURE_KEYS]
        return cls(values=values)

    def distance_to(self, other: "FeatureVector") -> float:
        """Euclidean distance between two feature vectors."""
        return math.sqrt(
            sum((a - b) ** 2 for a, b in zip(self.values, other.values))
        )


@dataclass
class TrainingEntry:
    """A single labelled training sample for the KNN model.

    Attributes:
        features: The feature vector.
        label:    Classification label (e.g. document category, or a JSON-
                  serialisable settings dict stored as a string).
        weight:   Optional per-sample weight (higher = more important).
        created_at: ISO-8601 timestamp of when the entry was added.
    """
    features: FeatureVector
    label: str
    weight: float = 1.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "features": self.features.to_dict(),
            "label": self.label,
            "weight": self.weight,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingEntry":
        return cls(
            features=FeatureVector.from_dict(data["features"]),
            label=str(data["label"]),
            weight=float(data.get("weight", 1.0)),
            created_at=str(data.get("created_at", "")),
        )


@dataclass
class PredictionResult:
    """Output of ``UnifiedLearning.predict()``.

    Attributes:
        label:       Predicted label / settings.
        confidence:  Confidence score in [confidence_floor, confidence_ceil].
        neighbours:  The *k* nearest neighbours used for the prediction.
        distances:   Euclidean distances to each neighbour.
    """
    label: str
    confidence: float
    neighbours: List[str] = field(default_factory=list)
    distances: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "neighbours": self.neighbours,
            "distances": self.distances,
        }


@dataclass
class PatternRecord:
    """A stored correction / pattern.

    Attributes:
        original_text:    Original (incorrect) OCR text.
        corrected_text:   User-corrected text.
        language:         Language code (``'ar'``, ``'en'``, ``'mixed'``).
        confidence:       OCR confidence at the time of capture.
        source:           Origin (``'manual'``, ``'auto'``, ``'active_learning'``).
        usage_count:      How many times this pattern has been applied.
        created_at:       ISO-8601 timestamp.
    """
    original_text: str
    corrected_text: str
    language: str = "ar"
    confidence: float = 0.0
    source: str = "manual"
    usage_count: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternRecord":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class FeedbackRecord:
    """A user-feedback record.

    Attributes:
        original_text:    Text before correction.
        corrected_text:   Text after correction.
        status:           Feedback status (verified / rejected / pending).
        timestamp:        ISO-8601 timestamp.
        context:          Optional free-text context (e.g. document type).
    """
    original_text: str
    corrected_text: str
    status: str = FeedbackStatus.PENDING.value
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackRecord":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class ModelMetadata:
    """Serialisable metadata stored alongside the KNN model.

    Attributes:
        version:        Schema version string.
        trained_at:     ISO-8601 timestamp of last training.
        total_entries:  Number of training entries.
        num_features:   Dimensionality of the feature vectors.
        k:              KNN ``k`` parameter used.
        feature_min:    Per-feature minimum (for normalisation).
        feature_max:    Per-feature maximum (for normalisation).
    """
    version: str = "1.0.0"
    trained_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_entries: int = 0
    num_features: int = NUM_FEATURES
    k: int = DEFAULT_K
    feature_min: Dict[str, float] = field(
        default_factory=lambda: {k: 0.0 for k in FEATURE_KEYS}
    )
    feature_max: Dict[str, float] = field(
        default_factory=lambda: {k: 1.0 for k in FEATURE_KEYS}
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


# ---------------------------------------------------------------------------
# Committee Model (for query-by-committee)
# ---------------------------------------------------------------------------

@dataclass
class CommitteePrediction:
    """Prediction from a single committee member."""
    label: str
    confidence: float
    member_id: str


class _CommitteeMember:
    """A lightweight committee member with a configurable sub-sample size."""

    def __init__(
        self,
        member_id: str,
        k: int = 3,
        sample_ratio: float = 0.7,
        seed: int | None = None,
    ) -> None:
        self.member_id = member_id
        self.k = k
        self.sample_ratio = sample_ratio
        self.seed = seed

    def predict(
        self,
        query: FeatureVector,
        entries: List[TrainingEntry],
        norm_min: Dict[str, float],
        norm_max: Dict[str, float],
    ) -> CommitteePrediction:
        """Predict using a random subset of the training data."""
        import random

        rng = random.Random(self.seed)
        subset_size = max(1, int(len(entries) * self.sample_ratio))
        subset = rng.sample(entries, min(subset_size, len(entries)))

        if not subset:
            return CommitteePrediction(
                label="unknown", confidence=0.0, member_id=self.member_id
            )

        distances = []
        for entry in subset:
            d = _normalised_distance(query, entry.features, norm_min, norm_max)
            distances.append((d, entry))

        distances.sort(key=lambda x: x[0])
        top_k = distances[: min(self.k, len(distances))]

        if not top_k:
            return CommitteePrediction(
                label="unknown", confidence=0.0, member_id=self.member_id
            )

        # Weighted vote
        weights: Counter = Counter()
        total_weight = 0.0
        for dist, entry in top_k:
            w = 1.0 / max(dist, 1e-6)
            weights[entry.label] += w
            total_weight += w

        if total_weight == 0:
            return CommitteePrediction(
                label="unknown", confidence=0.0, member_id=self.member_id
            )

        best_label = weights.most_common(1)[0][0]
        best_conf = weights[best_label] / total_weight

        return CommitteePrediction(
            label=best_label,
            confidence=best_conf,
            member_id=self.member_id,
        )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalised_distance(
    a: FeatureVector,
    b: FeatureVector,
    norm_min: Dict[str, float],
    norm_max: Dict[str, float],
) -> float:
    """Compute Euclidean distance on min-max normalised features.

    Args:
        a: Query feature vector.
        b: Reference feature vector.
        norm_min: Per-feature minimums from training data.
        norm_max: Per-feature maximums from training data.

    Returns:
        Normalised Euclidean distance.
    """
    total = 0.0
    for key, va, vb in zip(FEATURE_KEYS, a.values, b.values):
        rng = norm_max.get(key, 1.0) - norm_min.get(key, 0.0)
        if rng < 1e-9:
            continue
        na = (va - norm_min.get(key, 0.0)) / rng
        nb = (vb - norm_min.get(key, 0.0)) / rng
        total += (na - nb) ** 2
    return math.sqrt(total)


def _update_normalisation(
    entries: List[TrainingEntry],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Recompute per-feature min/max from training entries.

    Args:
        entries: Current training data.

    Returns:
        Tuple of (feature_min, feature_max) dictionaries.
    """
    if not entries:
        return {k: 0.0 for k in FEATURE_KEYS}, {k: 1.0 for k in FEATURE_KEYS}

    mins: Dict[str, float] = {k: float("inf") for k in FEATURE_KEYS}
    maxs: Dict[str, float] = {k: float("-inf") for k in FEATURE_KEYS}

    for entry in entries:
        for key, val in zip(FEATURE_KEYS, entry.features.values):
            mins[key] = min(mins[key], val)
            maxs[key] = max(maxs[key], val)

    return mins, maxs


def _weighted_majority_vote(
    neighbours: List[Tuple[float, TrainingEntry]],
) -> Tuple[str, float]:
    """Return the label with the highest inverse-distance weight.

    Args:
        neighbours: List of (distance, entry) pairs, sorted ascending.

    Returns:
        (best_label, confidence) where confidence is in [0, 1].
    """
    weights: Counter = Counter()
    total_weight = 0.0

    for dist, entry in neighbours:
        w = 1.0 / max(dist, 1e-6)
        w *= entry.weight
        weights[entry.label] += w
        total_weight += w

    if total_weight == 0 or not weights:
        return "unknown", 0.0

    best_label, best_w = weights.most_common(1)[0]
    return best_label, best_w / total_weight


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

class FeatureExtractor:
    """Extract a 30-dimensional feature vector from raw inputs.

    The extractor accepts a dictionary of raw measurements and derives the
    remaining features with sensible defaults so that callers only need to
    supply whichever subset they have available.

    Usage::

        ext = FeatureExtractor()
        vec = ext.extract({
            "width": 2480,
            "height": 3508,
            "blur_score": 120.5,
            "brightness": 0.72,
            "edge_density": 0.04,
            "border_noise": 0.15,
            "text": "Patient presents with fractured femur ...",
        })
    """

    def extract(self, raw: Dict[str, Any]) -> FeatureVector:
        """Build a :class:`FeatureVector` from a raw measurement dict.

        Recognised keys (all optional; missing values default to 0.0):

        Image-level:
            ``width``, ``height``, ``blur_score``, ``brightness``,
            ``edge_density``, ``border_noise``, ``contrast``,
            ``sharpness``, ``text_density``, ``whitespace_ratio``,
            ``horizontal_line_score``, ``vertical_line_score``,
            ``ink_coverage``, ``skew_score``

        Text-level:
            ``text``, ``char_count``, ``word_count``, ``avg_word_length``,
            ``digit_ratio``, ``arabic_char_ratio``, ``latin_char_ratio``,
            ``punctuation_ratio``, ``unique_word_ratio``

        Layout / medical:
            ``line_spacing_ratio``, ``margin_uniformity``, ``header_score``,
            ``footer_score``, ``table_score``, ``medical_term_score``,
            ``confidence_score``

        Args:
            raw: Dictionary of raw measurements (any subset accepted).

        Returns:
            A fully populated 30-dimensional :class:`FeatureVector`.
        """
        text: str = str(raw.get("text", ""))

        # ---- Image features (1-15) ----
        w = float(raw.get("width", 0))
        h = float(raw.get("height", 0))
        aspect_ratio = w / max(h, 1)
        blur_score = float(raw.get("blur_score", 0))
        brightness = float(raw.get("brightness", 0.5))
        edge_density = float(raw.get("edge_density", 0))
        border_noise = float(raw.get("border_noise", 0))
        contrast = float(raw.get("contrast", 0.5))
        sharpness = float(raw.get("sharpness", 0.5))
        text_density = float(raw.get("text_density", 0.3))
        whitespace_ratio = float(raw.get("whitespace_ratio", 0.2))
        h_line = float(raw.get("horizontal_line_score", 0))
        v_line = float(raw.get("vertical_line_score", 0))
        ink_coverage = float(raw.get("ink_coverage", 0.3))
        skew = float(raw.get("skew_score", 0))

        # ---- Text features (16-23) ----
        char_count = float(raw.get("char_count", len(text)))
        words = text.split() if text else []
        word_count = float(raw.get("word_count", len(words)))
        avg_word_len = float(
            raw.get(
                "avg_word_length",
                (sum(len(w) for w in words) / len(words)) if words else 0,
            )
        )
        digit_ratio = float(raw.get("digit_ratio", _digit_ratio(text)))
        arabic_ratio = float(raw.get("arabic_char_ratio", _arabic_ratio(text)))
        latin_ratio = float(raw.get("latin_char_ratio", _latin_ratio(text)))
        punct_ratio = float(raw.get("punctuation_ratio", _punct_ratio(text)))
        unique_ratio = float(
            raw.get("unique_word_ratio", _unique_ratio(words))
        )

        # ---- Layout / medical (24-30) ----
        line_spacing = float(raw.get("line_spacing_ratio", 0.3))
        margin_uni = float(raw.get("margin_uniformity", 0.8))
        header = float(raw.get("header_score", 0))
        footer = float(raw.get("footer_score", 0))
        table_score = float(raw.get("table_score", 0))
        med_term = float(raw.get("medical_term_score", _medical_term_score(text)))
        conf_score = float(raw.get("confidence_score", 0.5))

        return FeatureVector(values=[
            w, h, aspect_ratio, blur_score, brightness, edge_density,
            border_noise, contrast, sharpness, text_density,
            whitespace_ratio, h_line, v_line, ink_coverage, skew,
            char_count, word_count, avg_word_len, digit_ratio,
            arabic_ratio, latin_ratio, punct_ratio, unique_ratio,
            line_spacing, margin_uni, header, footer, table_score,
            med_term, conf_score,
        ])


def _digit_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(c.isdigit() for c in text) / len(text)


def _arabic_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum("\u0600" <= c <= "\u06FF" for c in text) / len(text)


def _latin_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(c.isalpha() and c.isascii() for c in text) / len(text)


def _punct_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(not c.isalnum() and not c.isspace() for c in text) / len(text)


def _unique_ratio(words: List[str]) -> float:
    if not words:
        return 0.0
    return len(set(words)) / len(words)


_MEDICAL_TERMS = frozenset({
    "fracture", "bone", "joint", "surgery", "patient", "diagnosis",
    "treatment", "hospital", "clinic", "prescription", "medication",
    "dosage", "x-ray", "mri", "ct", "ultrasound", "blood", "heart",
    "lung", "liver", "kidney", "cancer", "tumor", "biopsy",
    "anesthesia", "antibiotic", "pathology", "cardiology", "neurology",
    "orthopedic", "radiology", "pharmacology",
    "كسر", "عظم", "مفصل", "عملية", "مريض", "تشخيص", "علاج",
    "مستشفى", "وصفة", "دواء", "جراحة", "قلب", "دماغ",
})


def _medical_term_score(text: str) -> float:
    """Ratio of recognised medical terms present in *text*."""
    if not text:
        return 0.0
    text_lower = text.lower()
    found = sum(1 for term in _MEDICAL_TERMS if term in text_lower)
    return found / len(_MEDICAL_TERMS)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class UnifiedLearning:
    """Unified learning adapter for OmniMedical Suite.

    Combines KNN classification (30 features), active learning (uncertainty
    sampling & query-by-committee), pattern storage, and feedback collection
    into a single, production-ready interface.

    Example usage::

        ul = UnifiedLearning(model_path="model/unified.json")

        # Train
        ul.train(features={"width": 800, "height": 1100, "text": "..."}, label="orthopedic")

        # Predict
        result = ul.predict(features={"width": 820, "height": 1120, "text": "..."})
        print(result.label, result.confidence)

        # Active learning loop
        queries = ul.active_learn(strategy="uncertainty", pool=unlabelled, n=5)

        # Pattern management
        ul.store_pattern(original="فم", corrected="في", language="ar")
        suggestion = ul.suggest_correction(original="فم")

        # Feedback
        ul.collect_feedback(original="فم", corrected="في", status="verified")

        # Persist
        ul.save()
    """

    def __init__(
        self,
        model_path: Union[str, Path] = "model/unified_learning.json",
        k: int = DEFAULT_K,
        confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
        confidence_ceil: float = DEFAULT_CONFIDENCE_CEIL,
        committee_size: int = 5,
        committee_sample_ratio: float = 0.7,
    ) -> None:
        """Initialise the unified learning system.

        Args:
            model_path:       Path to the JSON model file (created if missing).
            k:                Number of nearest neighbours for KNN.
            confidence_floor: Minimum prediction confidence.
            confidence_ceil:  Maximum prediction confidence.
            committee_size:   Number of committee members for QBC.
            committee_sample_ratio: Fraction of training data sampled per member.
        """
        self.model_path = Path(model_path)
        self.k = k
        self.confidence_floor = confidence_floor
        self.confidence_ceil = confidence_ceil

        # Internal state
        self._entries: List[TrainingEntry] = []
        self._patterns: Dict[str, List[PatternRecord]] = defaultdict(list)
        self._feedback: List[FeedbackRecord] = []
        self._metadata = ModelMetadata(k=self.k)

        # Feature extraction helper
        self._extractor = FeatureExtractor()

        # Committee members for query-by-committee
        self._committee: List[_CommitteeMember] = [
            _CommitteeMember(
                member_id=f"member_{i}",
                k=max(1, self.k - 1),
                sample_ratio=committee_sample_ratio,
                seed=i,
            )
            for i in range(committee_size)
        ]

        # Try loading from disk
        self._load()

        logger.info(
            "UnifiedLearning initialised: %d entries, %d patterns, "
            "%d feedback records, k=%d",
            len(self._entries),
            sum(len(v) for v in self._patterns.values()),
            len(self._feedback),
            self.k,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Union[str, Path] | None = None) -> None:
        """Persist all state (model + patterns + feedback) to a JSON file.

        Args:
            path: Override path; defaults to ``self.model_path``.
        """
        target = Path(path) if path else self.model_path
        target.parent.mkdir(parents=True, exist_ok=True)

        # Update metadata before saving
        self._metadata.trained_at = datetime.now(timezone.utc).isoformat()
        self._metadata.total_entries = len(self._entries)
        self._metadata.k = self.k

        payload: Dict[str, Any] = {
            "metadata": self._metadata.to_dict(),
            "entries": [e.to_dict() for e in self._entries],
            "patterns": {
                key: [p.to_dict() for p in records]
                for key, records in self._patterns.items()
            },
            "feedback": [f.to_dict() for f in self._feedback],
        }

        tmp_path = target.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            tmp_path.replace(target)
            logger.info("Model saved to %s (%d entries)", target, len(self._entries))
        except Exception:
            logger.exception("Failed to save model to %s", target)
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _load(self) -> None:
        """Load persisted state from disk (no-op if file missing)."""
        if not self.model_path.exists():
            logger.debug("No existing model at %s — starting fresh", self.model_path)
            return

        try:
            with open(self.model_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)

            self._metadata = ModelMetadata.from_dict(payload.get("metadata", {}))
            self.k = self._metadata.k

            self._entries = [
                TrainingEntry.from_dict(e) for e in payload.get("entries", [])
            ]

            raw_patterns: Dict = payload.get("patterns", {})
            self._patterns = defaultdict(list)
            for key, records in raw_patterns.items():
                self._patterns[key] = [PatternRecord.from_dict(r) for r in records]

            self._feedback = [
                FeedbackRecord.from_dict(f) for f in payload.get("feedback", [])
            ]

            logger.info(
                "Model loaded from %s: %d entries, %d patterns, %d feedback",
                self.model_path,
                len(self._entries),
                sum(len(v) for v in self._patterns.values()),
                len(self._feedback),
            )
        except Exception:
            logger.exception("Failed to load model from %s", self.model_path)

    # ------------------------------------------------------------------
    # KNN: predict
    # ------------------------------------------------------------------

    def predict(
        self,
        features: Union[Dict[str, Any], FeatureVector],
        k: int | None = None,
    ) -> PredictionResult:
        """Predict a label using KNN classification.

        Args:
            features: Either a raw measurement dict (auto-extracted to 30-D)
                      or a pre-built :class:`FeatureVector`.
            k:        Override ``self.k`` for this single call.

        Returns:
            A :class:`PredictionResult` with the predicted label, confidence,
            neighbour labels, and distances.

        Raises:
            ValueError: If no training entries exist.
        """
        if not self._entries:
            raise ValueError("Cannot predict — no training entries available. Call train() first.")

        use_k = k if k is not None else self.k
        if use_k < 1:
            raise ValueError(f"k must be >= 1, got {use_k}")

        query = (
            features if isinstance(features, FeatureVector)
            else self._extractor.extract(features)
        )

        norm_min = self._metadata.feature_min
        norm_max = self._metadata.feature_max

        # Compute distances
        dists: List[Tuple[float, TrainingEntry]] = []
        for entry in self._entries:
            d = _normalised_distance(query, entry.features, norm_min, norm_max)
            dists.append((d, entry))

        dists.sort(key=lambda x: x[0])
        top_k = dists[: min(use_k, len(dists))]

        best_label, raw_conf = _weighted_majority_vote(top_k)

        # Scale confidence
        avg_dist = sum(d for d, _ in top_k) / len(top_k) if top_k else 1.0
        scaled_conf = max(self.confidence_floor, 1.0 - avg_dist * 0.8)
        scaled_conf = min(scaled_conf, self.confidence_ceil)
        # Blend weighted-vote confidence with distance-based confidence
        blended = 0.6 * raw_conf + 0.4 * scaled_conf
        final_conf = max(self.confidence_floor, min(self.confidence_ceil, blended))

        logger.debug(
            "predict: label=%s confidence=%.3f (k=%d, avg_dist=%.4f)",
            best_label, final_conf, use_k, avg_dist,
        )

        return PredictionResult(
            label=best_label,
            confidence=round(final_conf, 4),
            neighbours=[e.label for _, e in top_k],
            distances=[round(d, 6) for d, _ in top_k],
        )

    # ------------------------------------------------------------------
    # KNN: train
    # ------------------------------------------------------------------

    def train(
        self,
        features: Union[Dict[str, Any], FeatureVector],
        label: str,
        weight: float = 1.0,
    ) -> int:
        """Add a single labelled training entry and update normalisation stats.

        Args:
            features: Raw measurement dict or pre-built :class:`FeatureVector`.
            label:    Classification label for this entry.
            weight:   Per-sample importance weight.

        Returns:
            The index of the newly added entry in ``self._entries``.
        """
        vec = (
            features if isinstance(features, FeatureVector)
            else self._extractor.extract(features)
        )

        entry = TrainingEntry(features=vec, label=label, weight=weight)
        self._entries.append(entry)

        # Update normalisation bounds
        self._metadata.feature_min, self._metadata.feature_max = (
            _update_normalisation(self._entries)
        )
        self._metadata.total_entries = len(self._entries)

        logger.debug(
            "train: entry %d, label=%s, weight=%.2f, total=%d",
            len(self._entries) - 1, label, weight, len(self._entries),
        )
        return len(self._entries) - 1

    def train_batch(
        self,
        items: Iterable[Tuple[Union[Dict[str, Any], FeatureVector], str]],
        weights: Optional[Iterable[float]] = None,
    ) -> int:
        """Add multiple labelled entries at once.

        Args:
            items:   Iterable of (features, label) tuples.
            weights: Optional per-item weights (default all 1.0).

        Returns:
            Number of entries added.
        """
        weight_iter = weights if weights is not None else (1.0 for _ in items)
        count = 0
        for (feat, label), w in zip(items, weight_iter):
            self.train(feat, label, weight=float(w))
            count += 1
        logger.info("train_batch: added %d entries (total %d)", count, len(self._entries))
        return count

    # ------------------------------------------------------------------
    # Active Learning
    # ------------------------------------------------------------------

    def active_learn(
        self,
        pool: Sequence[Union[Dict[str, Any], FeatureVector]],
        strategy: Union[str, ActiveLearningStrategy] = ActiveLearningStrategy.UNCERTAINTY,
        n: int = 5,
        confidence_threshold: float = 0.7,
    ) -> List[Tuple[int, float, str]]:
        """Select samples from *pool* for labelling using an active-learning strategy.

        Args:
            pool:    Unlabelled candidate samples.
            strategy: Sampling strategy — ``'uncertainty'``, ``'query_by_committee'``,
                      or ``'diversity'``.
            n:       Number of samples to select.
            confidence_threshold: For uncertainty sampling, only pick samples whose
                                 current confidence is below this value.

        Returns:
            List of ``(pool_index, score, rationale)`` tuples.  Lower *score*
            means higher priority for labelling (for uncertainty / QBC).  The
            *rationale* is a human-readable string.

        Raises:
            ValueError: If the pool is empty or no training data exists.
        """
        if not pool:
            raise ValueError("Pool must not be empty")
        if not self._entries:
            raise ValueError(
                "No training data exists — seed the model with train() before "
                "using active learning."
            )

        strat = (
            strategy if isinstance(strategy, ActiveLearningStrategy)
            else ActiveLearningStrategy(strategy)
        )

        if strat == ActiveLearningStrategy.UNCERTAINTY:
            return self._uncertainty_sampling(pool, n, confidence_threshold)
        elif strat == ActiveLearningStrategy.QUERY_BY_COMMITTEE:
            return self._query_by_committee(pool, n)
        elif strat == ActiveLearningStrategy.DIVERSITY:
            return self._diversity_sampling(pool, n)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _uncertainty_sampling(
        self,
        pool: Sequence[Union[Dict[str, Any], FeatureVector]],
        n: int,
        threshold: float,
    ) -> List[Tuple[int, float, str]]:
        """Select the *n* most uncertain predictions from the pool.

        Samples whose current confidence >= *threshold* are deprioritised.

        Returns:
            List of (index, confidence, rationale) sorted by confidence ascending.
        """
        scored: List[Tuple[int, float]] = []
        for idx, item in enumerate(pool):
            vec = item if isinstance(item, FeatureVector) else self._extractor.extract(item)
            result = self.predict(vec)
            scored.append((idx, result.confidence))

        # Sort by confidence ascending (most uncertain first)
        scored.sort(key=lambda x: x[1])

        output: List[Tuple[int, float, str]] = []
        for idx, conf in scored[:n]:
            rationale = (
                f"Low confidence ({conf:.3f}) — needs labelling"
                if conf < threshold
                else f"Confidence {conf:.3f} above threshold {threshold}"
            )
            output.append((idx, conf, rationale))

        logger.info(
            "uncertainty_sampling: selected %d samples from pool of %d", n, len(pool)
        )
        return output

    def _query_by_committee(
        self,
        pool: Sequence[Union[Dict[str, Any], FeatureVector]],
        n: int,
    ) -> List[Tuple[int, float, str]]:
        """Select samples where the committee disagrees the most.

        For each pool sample, every committee member predicts independently.
        The disagreement score is 1 minus the fraction of members that agree
        with the majority label.

        Returns:
            List of (index, disagreement, rationale) sorted descending.
        """
        norm_min = self._metadata.feature_min
        norm_max = self._metadata.feature_max

        scored: List[Tuple[int, float, str]] = []

        for idx, item in enumerate(pool):
            vec = item if isinstance(item, FeatureVector) else self._extractor.extract(item)
            preds = [
                member.predict(vec, self._entries, norm_min, norm_max)
                for member in self._committee
            ]

            if not preds:
                continue

            labels = [p.label for p in preds]
            counts = Counter(labels)
            majority_label, majority_count = counts.most_common(1)[0]
            agreement = majority_count / len(preds)
            disagreement = 1.0 - agreement

            scored.append((idx, disagreement, f"Committee disagreement: {disagreement:.2f}"))

        scored.sort(key=lambda x: x[1], reverse=True)

        logger.info(
            "query_by_committee: selected %d samples from pool of %d", n, len(pool)
        )
        return scored[:n]

    def _diversity_sampling(
        self,
        pool: Sequence[Union[Dict[str, Any], FeatureVector]],
        n: int,
    ) -> List[Tuple[int, float, str]]:
        """Select a diverse subset using greedy farthest-point sampling.

        Starting from a random seed, iteratively picks the pool sample
        that is furthest from the already-selected set.

        Returns:
            List of (index, min_distance, rationale).
        """
        import random

        if len(pool) <= n:
            return [(i, 0.0, "Full pool selected (pool <= n)") for i in range(len(pool))]

        vecs = [
            item if isinstance(item, FeatureVector) else self._extractor.extract(item)
            for item in pool
        ]

        # Random seed
        seed_idx = random.randint(0, len(vecs) - 1)
        selected: List[int] = [seed_idx]
        output: List[Tuple[int, float, str]] = [
            (seed_idx, 0.0, "Random seed for diversity sampling")
        ]

        for _ in range(n - 1):
            best_idx = -1
            best_min_dist = -1.0
            for i, v in enumerate(vecs):
                if i in selected:
                    continue
                min_d = min(
                    v.distance_to(vecs[j]) for j in selected
                )
                if min_d > best_min_dist:
                    best_min_dist = min_d
                    best_idx = i

            if best_idx >= 0:
                selected.append(best_idx)
                output.append((best_idx, round(best_min_dist, 4), "Diverse selection"))

        logger.info(
            "diversity_sampling: selected %d samples from pool of %d", n, len(pool)
        )
        return output

    # ------------------------------------------------------------------
    # Pattern storage & retrieval
    # ------------------------------------------------------------------

    def store_pattern(
        self,
        original_text: str,
        corrected_text: str,
        language: str = "ar",
        confidence: float = 0.0,
        source: str = "manual",
    ) -> int:
        """Store a correction pattern for future lookup.

        If the same ``original_text`` already exists for the same language,
        the ``usage_count`` is incremented rather than creating a duplicate.

        Args:
            original_text:  The incorrect OCR text.
            corrected_text: The user-corrected text.
            language:       Language code (``'ar'``, ``'en'``, ``'mixed'``).
            confidence:     OCR confidence at capture time.
            source:         Where the correction came from.

        Returns:
            Total number of patterns stored for this key.
        """
        key = f"{language}:{original_text}"
        records = self._patterns[key]

        # Check for an existing record with the same correction
        for rec in records:
            if rec.corrected_text == corrected_text:
                rec.usage_count += 1
                rec.confidence = (rec.confidence + confidence) / 2
                logger.debug(
                    "store_pattern: updated existing pattern '%s' -> '%s' (usage=%d)",
                    original_text, corrected_text, rec.usage_count,
                )
                return len(records)

        # New pattern
        records.append(PatternRecord(
            original_text=original_text,
            corrected_text=corrected_text,
            language=language,
            confidence=confidence,
            source=source,
        ))

        logger.debug(
            "store_pattern: new pattern '%s' -> '%s' (%s), total for key=%d",
            original_text, corrected_text, language, len(records),
        )
        return len(records)

    def suggest_correction(
        self,
        original_text: str,
        language: str = "ar",
        min_usage: int = 2,
    ) -> Optional[PatternRecord]:
        """Look up the best correction for an original text.

        Returns the pattern with the highest ``usage_count`` that meets the
        minimum usage threshold.

        Args:
            original_text: The text to look up.
            language:      Language code.
            min_usage:     Minimum times the pattern must have been used.

        Returns:
            The best matching :class:`PatternRecord`, or ``None``.
        """
        key = f"{language}:{original_text}"
        records = self._patterns.get(key, [])

        candidates = [r for r in records if r.usage_count >= min_usage]
        if not candidates:
            return None

        # Sort by usage_count descending, then by confidence descending
        candidates.sort(key=lambda r: (r.usage_count, r.confidence), reverse=True)
        return candidates[0]

    def get_all_patterns(
        self,
        language: str | None = None,
        min_usage: int = 1,
    ) -> List[PatternRecord]:
        """Return all stored patterns, optionally filtered.

        Args:
            language:   If set, only return patterns for this language.
            min_usage:  Minimum usage count filter.

        Returns:
            List of matching :class:`PatternRecord` instances.
        """
        results: List[PatternRecord] = []
        for key, records in self._patterns.items():
            if language and not key.startswith(f"{language}:"):
                continue
            for rec in records:
                if rec.usage_count >= min_usage:
                    results.append(rec)
        return results

    def apply_patterns(self, text: str, language: str = "ar") -> str:
        """Apply all matching correction patterns to a text.

        Performs word-level substitution based on stored patterns.

        Args:
            text:     The text to correct.
            language: Language code.

        Returns:
            The corrected text.
        """
        if not text:
            return text

        words = text.split()
        corrected: List[str] = []
        changes = 0

        for word in words:
            suggestion = self.suggest_correction(word, language=language)
            if suggestion:
                corrected.append(suggestion.corrected_text)
                changes += 1
            else:
                corrected.append(word)

        if changes:
            logger.debug("apply_patterns: %d corrections applied", changes)

        return " ".join(corrected)

    # ------------------------------------------------------------------
    # Feedback collection
    # ------------------------------------------------------------------

    def collect_feedback(
        self,
        original_text: str,
        corrected_text: str,
        status: str = FeedbackStatus.PENDING.value,
        context: str = "",
    ) -> int:
        """Record a user-feedback event.

        Feedback is persisted alongside the model when :meth:`save` is called
        and can be used to build correction dictionaries (see
        ``build_correction_dict_from_feedback``).

        Args:
            original_text:  Text before correction.
            corrected_text: Text after correction.
            status:         ``'verified'``, ``'rejected'``, or ``'pending'``.
            context:        Optional context hint (e.g. ``'drug_name'``).

        Returns:
            Index of the new feedback record.
        """
        record = FeedbackRecord(
            original_text=original_text,
            corrected_text=corrected_text,
            status=status,
            context=context,
        )
        self._feedback.append(record)

        logger.debug(
            "collect_feedback: '%s' -> '%s' [%s]",
            original_text[:30], corrected_text[:30], status,
        )
        return len(self._feedback) - 1

    def build_correction_dict_from_feedback(
        self,
        min_votes: int = 1,
    ) -> Dict[str, str]:
        """Aggregate feedback records into a correction dictionary.

        For each ``original_text``, the most common ``corrected_text`` among
        verified feedback records is chosen, provided it has at least
        ``min_votes`` votes.

        Args:
            min_votes: Minimum number of verified votes for a correction to
                       be included.

        Returns:
            Dict mapping ``original_text`` → ``corrected_text``.
        """
        verified = [f for f in self._feedback if f.status == FeedbackStatus.VERIFIED.value]
        buckets: Dict[str, Counter] = defaultdict(Counter)

        for fb in verified:
            if fb.original_text and fb.corrected_text:
                buckets[fb.original_text][fb.corrected_text] += 1

        result: Dict[str, str] = {}
        for orig, counts in buckets.items():
            best_corr, best_count = counts.most_common(1)[0]
            if best_count >= min_votes:
                result[orig] = best_corr

        logger.info(
            "build_correction_dict_from_feedback: %d corrections from %d verified feedback",
            len(result), len(verified),
        )
        return result

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Return summary statistics for all feedback records.

        Returns:
            Dict with keys ``total``, ``verified``, ``rejected``, ``pending``,
            and ``correction_dict`` (built with default ``min_votes=1``).
        """
        total = len(self._feedback)
        status_counts = Counter(f.status for f in self._feedback)
        return {
            "total": total,
            "verified": status_counts.get(FeedbackStatus.VERIFIED.value, 0),
            "rejected": status_counts.get(FeedbackStatus.REJECTED.value, 0),
            "pending": status_counts.get(FeedbackStatus.PENDING.value, 0),
            "correction_dict": self.build_correction_dict_from_feedback(),
        }

    # ------------------------------------------------------------------
    # Convenience: end-to-end learning loop
    # ------------------------------------------------------------------

    def end_to_end_learn(
        self,
        unlabelled_pool: Sequence[Dict[str, Any]],
        label_fn: Callable[[Dict[str, Any]], str],
        strategy: Union[str, ActiveLearningStrategy] = ActiveLearningStrategy.UNCERTAINTY,
        rounds: int = 3,
        n_per_round: int = 5,
        auto_save: bool = True,
    ) -> Dict[str, Any]:
        """Run an end-to-end active learning loop.

        For each round:
        1. Select ``n_per_round`` samples via the chosen strategy.
        2. Call ``label_fn(sample)`` to obtain labels (simulating a human).
        3. Train on the newly labelled samples.
        4. (Optional) auto-save the model.

        Args:
            unlabelled_pool: Pool of raw measurement dicts.
            label_fn:        Callable that accepts a raw dict and returns a label.
            strategy:        Active learning strategy.
            rounds:          Number of active-learning rounds.
            n_per_round:     Samples to select per round.
            auto_save:       Whether to call ``save()`` after each round.

        Returns:
            Summary dict with ``rounds``, ``samples_labelled``, and ``entries_before``.
        """
        if not unlabelled_pool:
            raise ValueError("unlabelled_pool must not be empty")

        entries_before = len(self._entries)
        mutable_pool = list(unlabelled_pool)
        total_labelled = 0

        for rnd in range(1, rounds + 1):
            if not mutable_pool:
                logger.info("end_to_end_learn: pool exhausted after round %d", rnd - 1)
                break

            queries = self.active_learn(
                pool=mutable_pool,
                strategy=strategy,
                n=min(n_per_round, len(mutable_pool)),
            )

            # Collect indices to label (in reverse order to preserve indices)
            indices_to_label = sorted({idx for idx, _, _ in queries}, reverse=True)

            round_labelled = 0
            for idx in indices_to_label:
                sample = mutable_pool.pop(idx)
                label = label_fn(sample)
                self.train(sample, label)
                round_labelled += 1

            total_labelled += round_labelled

            logger.info(
                "end_to_end_learn: round %d/%d — labelled %d samples (total %d)",
                rnd, rounds, round_labelled, len(self._entries),
            )

            if auto_save:
                self.save()

        return {
            "rounds_completed": min(rounds, len(unlabelled_pool) // n_per_round + 1),
            "samples_labelled": total_labelled,
            "entries_before": entries_before,
            "entries_after": len(self._entries),
        }

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    @property
    def num_entries(self) -> int:
        """Number of training entries currently stored."""
        return len(self._entries)

    @property
    def num_patterns(self) -> int:
        """Total number of stored pattern records."""
        return sum(len(v) for v in self._patterns.values())

    @property
    def num_feedback(self) -> int:
        """Number of feedback records."""
        return len(self._feedback)

    def get_model_info(self) -> Dict[str, Any]:
        """Return a summary of the current model state.

        Returns:
            Dict with metadata, entry count, pattern count, and feedback stats.
        """
        return {
            "metadata": self._metadata.to_dict(),
            "num_entries": self.num_entries,
            "num_patterns": self.num_patterns,
            "num_feedback": self.num_feedback,
            "feedback_stats": self.get_feedback_stats(),
            "k": self.k,
            "num_features": NUM_FEATURES,
        }

    def reset(self) -> None:
        """Clear all in-memory state (entries, patterns, feedback)."""
        self._entries.clear()
        self._patterns.clear()
        self._feedback.clear()
        self._metadata = ModelMetadata(k=self.k)
        logger.warning("UnifiedLearning state reset")

    def export_correction_dict(
        self,
        output_path: Union[str, Path],
        min_usage: int = 2,
    ) -> Path:
        """Export all patterns as a flat ``{original: corrected}`` JSON file.

        This is compatible with the feedback module's ``load_correction_dict``.

        Args:
            output_path: Destination file path.
            min_usage:   Minimum usage count for a pattern to be exported.

        Returns:
            The path written to.
        """
        patterns = self.get_all_patterns(min_usage=min_usage)
        d: Dict[str, str] = {}
        for p in patterns:
            # Keep the highest-usage correction per original
            if p.original_text not in d or p.usage_count > d.get("_usage", 0):
                d[p.original_text] = p.corrected_text
                d["_usage"] = p.usage_count  # temporary

        # Clean up temporary key
        d.pop("_usage", None)

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)

        logger.info("Exported %d corrections to %s", len(d), target)
        return target

    def import_correction_dict(
        self,
        input_path: Union[str, Path],
        language: str = "ar",
    ) -> int:
        """Import a ``{original: corrected}`` JSON file as patterns.

        Args:
            input_path: Source JSON file.
            language:   Language tag to assign to imported patterns.

        Returns:
            Number of patterns imported.
        """
        source = Path(input_path)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")

        with open(source, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        count = 0
        for original, corrected in data.items():
            if isinstance(corrected, str) and original != corrected:
                self.store_pattern(
                    original_text=original,
                    corrected_text=corrected,
                    language=language,
                    source="import",
                )
                count += 1

        logger.info("Imported %d patterns from %s", count, source)
        return count
