"""
src.core — Core Pipeline Package
=================================

Exports the main orchestrator and its configuration dataclass.
"""

from config.settings import PipelineConfig
from src.core.pipeline import (
    BBox,
    EngineResult,
    LineResult,
    OmniMedicalOCR,
    PipelineResult,
)

__all__ = [
    "BBox",
    "EngineResult",
    "LineResult",
    "OmniMedicalOCR",
    "PipelineConfig",
    "PipelineResult",
]