"""
AI Fuel Engine - Configuration Module

Comprehensive configuration management using dataclasses with support for
dictionary serialization, deserialization, and environment variable loading.

Environment Variable Mapping:
    AI_FUEL_MAX_TOKENS, AI_FUEL_OVERLAP_TOKENS, AI_FUEL_MIN_CHUNK_TOKENS,
    AI_FUEL_KEYWORD_CONFIDENCE_THRESHOLD, AI_FUEL_SEMANTIC_CONFIDENCE_THRESHOLD,
    AI_FUEL_SEMANTIC_MODEL_NAME, AI_FUEL_DEDUP_ENABLED, AI_FUEL_EXACT_DEDUP,
    AI_FUEL_SEMANTIC_DEDUP_THRESHOLD, AI_FUEL_EXPORT_FORMAT, AI_FUEL_OUTPUT_DIR,
    AI_FUEL_PHI_PROTECTION_ENABLED, AI_FUEL_PHI_MASKING_MODE,
    AI_FUEL_BATCH_SIZE, AI_FUEL_NUM_WORKERS, AI_FUEL_LOG_LEVEL,
    AI_FUEL_QDRANT_URL, AI_FUEL_QDRANT_COLLECTION,
    AI_FUEL_ACTIVE_LEARNING_ENABLED, AI_FUEL_UNCERTAINTY_THRESHOLD
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


@dataclass
class AIFuelConfig:
    """
    Master configuration for the AI Fuel Engine pipeline.

    All settings are optional with sensible defaults. Configuration can be
    loaded from a dictionary, environment variables, or constructed directly.

    Attributes:
        max_tokens: Maximum number of tokens per text chunk.
        overlap_tokens: Number of overlapping tokens between consecutive chunks.
        min_chunk_tokens: Minimum token count for a valid chunk (smaller chunks are discarded).
        keyword_confidence_threshold: Minimum confidence for keyword-based classification.
        semantic_confidence_threshold: Minimum confidence for semantic classification.
        semantic_model_name: Name of the sentence-transformers model for semantic similarity.
        dedup_enabled: Whether to run deduplication on classified chunks.
        exact_dedup: Whether to perform exact (hash-based) deduplication.
        semantic_dedup_threshold: Cosine similarity threshold for semantic deduplication.
        export_format: Default export format (jsonl, parquet, rag, csv).
        output_dir: Directory path for exported output files.
        phi_protection_enabled: Whether to scan and protect Protected Health Information.
        phi_masking_mode: Mode of PHI handling — 'tag', 'mask', or 'remove'.
        batch_size: Number of documents to process in a single batch.
        num_workers: Number of parallel worker processes.
        log_level: Python logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        qdrant_url: URL of the Qdrant vector database instance.
        qdrant_collection: Name of the Qdrant collection for vector storage.
        active_learning_enabled: Whether active learning feedback loop is active.
        uncertainty_threshold: Confidence threshold below which samples are flagged for review.
    """

    # ── Segmenter settings ──────────────────────────────────────────────
    max_tokens: int = 4000
    overlap_tokens: int = 200
    min_chunk_tokens: int = 100

    # ── Classifier settings ──────────────────────────────────────────────
    keyword_confidence_threshold: float = 0.85
    semantic_confidence_threshold: float = 0.85
    semantic_model_name: str = "paraphrase-multilingual-mpnet-base-v2"

    # ── Dedup settings ────────────────────────────────────────────────────
    dedup_enabled: bool = True
    exact_dedup: bool = True
    semantic_dedup_threshold: float = 0.95

    # ── Export settings ──────────────────────────────────────────────────
    export_format: str = "jsonl"
    output_dir: str = "./datasets"

    # ── PHI protection ───────────────────────────────────────────────────
    phi_protection_enabled: bool = True
    phi_masking_mode: str = "tag"  # tag, mask, remove

    # ── Processing ──────────────────────────────────────────────────────
    batch_size: int = 10
    num_workers: int = 4
    log_level: str = "INFO"

    # ── Qdrant ───────────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "ai_fuel_corpus"

    # ── Active Learning ───────────────────────────────────────────────────
    active_learning_enabled: bool = True
    uncertainty_threshold: float = 0.7

    # ── Internal ──────────────────────────────────────────────────────────
    _frozen: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the configuration to a plain dictionary.

        Internal / private fields (prefixed with ``_``) are excluded.

        Returns:
            A dictionary representation of the configuration.
        """
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AIFuelConfig":
        """Create an ``AIFuelConfig`` instance from a dictionary.

        Only keys that match actual dataclass fields are used; unknown keys
        are silently ignored so that forward-compatible configs don't break.

        Args:
            d: Dictionary of configuration values.

        Returns:
            A new ``AIFuelConfig`` instance.

        Raises:
            TypeError: If a known key receives a value of an incompatible type.
        """
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        try:
            return cls(**filtered)
        except TypeError as exc:
            raise TypeError(
                f"Failed to construct AIFuelConfig from dict: {exc}"
            ) from exc

    @classmethod
    def from_env(cls, prefix: str = "AI_FUEL_") -> "AIFuelConfig":
        """Create an ``AIFuelConfig`` by reading environment variables.

        Each dataclass field can be overridden via an environment variable
        named ``{PREFIX}{FIELD_NAME}`` (upper-case).  For example,
        ``AI_FUEL_MAX_TOKENS`` overrides ``max_tokens``.

        Boolean values accept ``1``, ``true``, ``yes`` (case-insensitive).

        Args:
            prefix: Environment variable prefix (default ``AI_FUEL_``).

        Returns:
            A new ``AIFuelConfig`` with environment overrides applied.
        """
        env_values: Dict[str, Any] = {}
        for f in cls.__dataclass_fields__.values():
            if f.name.startswith("_"):
                continue
            env_key = f"{prefix}{f.name.upper()}"
            raw = os.environ.get(env_key)
            if raw is None:
                continue

            # Coerce the string value to the field's declared type
            try:
                env_values[f.name] = cls._coerce_env_value(raw, f.type)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Ignoring env var %s=%r: %s", env_key, raw, exc
                )

        config = cls(**env_values)
        logger.info("Loaded AIFuelConfig from env with %d overrides", len(env_values))
        return config

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Validate configuration values after construction."""
        self._validate_ranges()
        self._validate_choices()

    def _validate_ranges(self) -> None:
        """Ensure numeric fields are within sensible bounds."""
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens must be >= 0")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be < max_tokens")
        if self.min_chunk_tokens < 1:
            raise ValueError("min_chunk_tokens must be >= 1")
        if not (0.0 <= self.keyword_confidence_threshold <= 1.0):
            raise ValueError("keyword_confidence_threshold must be in [0, 1]")
        if not (0.0 <= self.semantic_confidence_threshold <= 1.0):
            raise ValueError("semantic_confidence_threshold must be in [0, 1]")
        if not (0.0 <= self.semantic_dedup_threshold <= 1.0):
            raise ValueError("semantic_dedup_threshold must be in [0, 1]")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.num_workers < 1:
            raise ValueError("num_workers must be >= 1")
        if not (0.0 <= self.uncertainty_threshold <= 1.0):
            raise ValueError("uncertainty_threshold must be in [0, 1]")

    def _validate_choices(self) -> None:
        """Ensure string fields have allowed values."""
        valid_formats = {"jsonl", "parquet", "rag", "csv"}
        if self.export_format not in valid_formats:
            raise ValueError(
                f"export_format must be one of {valid_formats}, got '{self.export_format}'"
            )
        valid_phi_modes = {"tag", "mask", "remove"}
        if self.phi_masking_mode not in valid_phi_modes:
            raise ValueError(
                f"phi_masking_mode must be one of {valid_phi_modes}, "
                f"got '{self.phi_masking_mode}'"
            )
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"log_level must be one of {valid_log_levels}, "
                f"got '{self.log_level}'"
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_env_value(raw: str, target_type: Any) -> Any:
        """Coerce a raw environment-variable string to *target_type*.

        Supports ``bool``, ``int``, ``float``, and ``str``.

        Args:
            raw: The raw string value from ``os.environ``.
            target_type: The Python type to coerce to.

        Returns:
            The coerced value.

        Raises:
            TypeError: If *target_type* is unsupported.
            ValueError: If the value cannot be parsed as the target type.
        """
        # Resolve typing generics (e.g. ``typing.Optional[int]`` → ``int``)
        origin = getattr(target_type, "__origin__", None)
        if origin is not None:
            # Use the first non-None argument for Optional[X]
            args = getattr(target_type, "__args__", ())
            for arg in args:
                if arg is not type(None):
                    target_type = arg
                    break

        if target_type is bool:
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        if target_type is int:
            return int(raw.strip())
        if target_type is float:
            return float(raw.strip())
        if target_type is str:
            return raw.strip()
        raise TypeError(f"Unsupported env var target type: {target_type}")

    def __repr__(self) -> str:
        fields = self.to_dict()
        items = ", ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"AIFuelConfig({items})"
