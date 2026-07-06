"""
config — Configuration Package
===============================

Exports all configuration dataclasses and enums used throughout
the Omni Medical OCR Pipeline.
"""

from config.settings import (
    Device,
    EngineName,
    ModelConfig,
    PipelineConfig,
    PreprocessingConfig,
    SpellCheckStrategy,
)

__all__ = [
    "Device",
    "EngineName",
    "ModelConfig",
    "PipelineConfig",
    "PreprocessingConfig",
    "SpellCheckStrategy",
]