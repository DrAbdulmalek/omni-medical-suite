"""
Configuration Module for Omni Medical OCR Pipeline
===================================================

Provides dataclass-based configuration with YAML/JSON loading
and sensible defaults for Arabic medical OCR workflows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Device(str, Enum):
    """Compute device selection."""
    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"


class EngineName(str, Enum):
    """Supported OCR engine identifiers."""
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"
    TROCR = "trocr"


class SpellCheckStrategy(str, Enum):
    """Spell checking strategy to apply."""
    NONE = "none"
    HYBRID = "hybrid"          # Dictionary + edit-distance
    LLM_FALLBACK = "llm_fallback"  # Hybrid, then LLM for low-confidence


# ---------------------------------------------------------------------------
# PreprocessingConfig
# ---------------------------------------------------------------------------

@dataclass
class PreprocessingConfig:
    """Image preprocessing parameters applied before OCR."""

    # Deskew
    deskew: bool = True
    deskew_sigma: float = 3.0

    # Denoise
    denoise: bool = True
    denoise_h: int = 10         # OpenCV fastNlMeansDenoising h-param

    # Contrast enhancement (CLAHE)
    enhance_contrast: bool = True
    clahe_clip_limit: float = 2.0
    clahe_grid_size: tuple[int, int] = (8, 8)

    # Resize / DPI
    target_dpi: int = 300
    max_dimension: int = 4096
    min_dimension: int = 256

    # Binarisation (optional additional step)
    binarize: bool = False
    binarize_threshold: int = 0  # 0 = Otsu automatic

    # Grayscale conversion
    to_grayscale: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary (JSON/YAML-safe)."""
        return asdict(self)


# ---------------------------------------------------------------------------
# ModelConfig
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """Paths, device selection, and per-engine model settings."""

    # Global device
    device: str = Device.CPU.value  # default safe; override in load_config

    # Tesseract
    tesseract_cmd: Optional[str] = None   # path to tesseract binary
    tesseract_lang: str = "ara+eng"

    # EasyOCR
    easyocr_lang: List[str] = field(default_factory=lambda: ["ar", "en"])
    easyocr_gpu: bool = False
    easyocr_model_storage: str = "~/.EasyOCR/model"

    # PaddleOCR
    paddleocr_lang: str = "ar"
    paddleocr_use_gpu: bool = False
    paddleocr_det_model_dir: Optional[str] = None
    paddleocr_rec_model_dir: Optional[str] = None
    paddleocr_cls_model_dir: Optional[str] = None

    # TrOCR (HuggingFace)
    trocr_model_name: str = "microsoft/trocr-base-handwritten"
    trocr_processor_name: str = "microsoft/trocr-base-handwritten"
    trocr_use_fp16: bool = False

    # Spell checker / LLM
    medical_dictionary_path: Optional[str] = None
    arabic_dictionary_path: Optional[str] = None
    llm_model_name: Optional[str] = None  # e.g. "instructlab/merlinite-7b-lab"
    llm_device: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# PipelineConfig  (the "top-level" config used by OmniMedicalOCR)
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """
    Master configuration for the OmniMedicalOCR pipeline.

    This is the primary configuration object passed to
    ``OmniMedicalOCR(config=...)``.
    """

    # --- Engine selection & weights ---
    enabled_engines: List[str] = field(
        default_factory=lambda: [
            EngineName.TESSERACT.value,
            EngineName.EASYOCR.value,
            EngineName.PADDLEOCR.value,
            # EngineName.TROCR.value,  # heavy — opt-in
        ]
    )
    engine_weights: Dict[str, float] = field(
        default_factory=lambda: {
            EngineName.TESSERACT.value: 0.2,
            EngineName.EASYOCR.value: 0.3,
            EngineName.PADDLEOCR.value: 0.3,
            EngineName.TROCR.value: 0.2,
        }
    )

    # --- Confidence thresholds ---
    min_confidence: float = 0.3          # drop lines below this
    high_confidence: float = 0.8         # above = keep as-is
    merge_iou_threshold: float = 0.5     # bounding-box overlap for merging

    # --- Language ---
    primary_language: str = "ar"
    secondary_language: str = "en"

    # --- Spell checking ---
    spell_check_strategy: str = SpellCheckStrategy.HYBRID.value
    spell_check_max_edit_distance: int = 2
    spell_check_min_word_length: int = 3

    # --- Batch / parallelism ---
    max_workers: int = 4
    batch_size: int = 8

    # --- PDF handling ---
    pdf_dpi: int = 300
    pdf_first_page: Optional[int] = None
    pdf_last_page: Optional[int] = None

    # --- Nested configs (composed) ---
    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    model: ModelConfig = field(default_factory=ModelConfig)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Recursively serialise to a plain dictionary."""
        d = asdict(self)
        # Ensure nested dataclasses are plain dicts too (asdict handles it)
        return d

    def to_json(self, path: str | Path, indent: int = 2, **kwargs: Any) -> None:
        """Write configuration to a JSON file."""
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, **kwargs),
            encoding="utf-8",
        )

    def to_yaml(self, path: str | Path, **kwargs: Any) -> None:
        """Write configuration to a YAML file."""
        Path(path).write_text(
            yaml.dump(self.to_dict(), allow_unicode=True, default_flow_style=False, **kwargs),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Factory: load from file
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Instantiate from a plain dictionary, ignoring unknown keys."""
        # Build nested configs first
        prep_data = data.pop("preprocessing", {})
        model_data = data.pop("model", {})

        prep = PreprocessingConfig(**{k: v for k, v in prep_data.items()
                                       if k in PreprocessingConfig.__dataclass_fields__})
        model = ModelConfig(**{k: v for k, v in model_data.items()
                                if k in ModelConfig.__dataclass_fields__})

        # Filter top-level keys to avoid TypeError on unknown fields
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(preprocessing=prep, model=model, **valid)

    @classmethod
    def from_json(cls, path: str | Path) -> "PipelineConfig":
        """Load configuration from a JSON file."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        """Load configuration from a YAML file."""
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Expected a YAML mapping in {path}, got {type(raw).__name__}")
        return cls.from_dict(raw)

    @classmethod
    def load(cls, path: str | Path) -> "PipelineConfig":
        """Auto-detect format (YAML or JSON) and load configuration."""
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix in (".yaml", ".yml"):
            return cls.from_yaml(p)
        if suffix == ".json":
            return cls.from_json(p)
        raise ValueError(f"Unsupported config file format: {suffix}")