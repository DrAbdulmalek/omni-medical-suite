# Medical Document Processor - Core Python Package
# Version: 3.2
# Modules: image processing, encryption, DB management, Mistral AI integration

"""
Unified logging configuration for all packages/core modules.

Usage (from any module in packages/core):
    from packages.core import logger

All modules share the same logger with consistent formatting.
"""

import logging
import sys


# Configure root logger for the core package
def _setup_logging():
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Get the core package logger
    core_logger = logging.getLogger("packages.core")
    core_logger.setLevel(logging.INFO)
    core_logger.addHandler(handler)
    core_logger.propagate = False

    return core_logger

# Module-level logger - use this in all core modules
logger = _setup_logging()

# Re-export main processing functions for convenience
from .image_processor import (
    apply_processing,
    assess_image_quality,
    auto_detect_skew,
    detect_blur_laplacian,
    extract_page_number,
    find_page_bounds,
    image_segmentation,
    remove_shadow,
    sharpen_image,
    smart_auto_crop,
)

__all__ = [
    "apply_processing",
    "assess_image_quality",
    "auto_detect_skew",
    "detect_blur_laplacian",
    "extract_page_number",
    "find_page_bounds",
    "image_segmentation",
    "logger",
    "remove_shadow",
    "sharpen_image",
    "smart_auto_crop",
]
