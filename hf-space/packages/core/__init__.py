# Medical Document Processor - Core Python Package
# Version: 3.2
# Modules: image processing, encryption, DB management, Mistral AI integration

"""
وحدة البنية الأساسية (Core Structure Module)
================================================
أنواع البيانات الأساسية المشتركة بين جميع وحدات المعالجة.
Shared data models and type definitions for all processing modules.

Unified logging configuration for all packages/core modules.

Usage (from any module in packages/core):
    from packages.core import logger

All modules share the same logger with consistent formatting.

الوحدات الفرعية:
- image_processor: معالجة الصور (crop, skew, shadow, quality)
- structure: أنواع البيانات المشتركة (BBox, DocumentBlock, etc.)
- engine_router: توجيه محركات OCR
- corrections_manager: إدارة قاموس التصحيحات
- word_trainer: تدريب الكلمات
- spell_checker: التدقيق الإملائي الهجين
- log_manager: إدارة السجلات
- base_db: قاعدة البيانات الأساسية
- user_manager: إدارة المستخدمين
- parallel_processor: المعالجة المتوازية
- model_manager: إدارة ذاكرة النماذج
- progress_tracker: تتبّع التقدّم
- database_manager: نظام قاعدة البيانات مع بصمة SHA-256
- file_fingerprint: نظام بصمة الملفات
- classifier: مصنف المحتوى الطبي والعلمي
- watchdog_service: مراقب المجلدات
- dataset_generator: مولد بيانات التدريب الناعم
- search_engine: محرك البحث الشامل
- handwriting_db: قاعدة بيانات الخط اليدوي

OmniFile AI Processor - وحدة معالجة الملفات الذكية
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
    find_page_bounds,
    auto_detect_skew,
    smart_auto_crop,
    remove_shadow,
    detect_blur_laplacian,
    sharpen_image,
    extract_page_number,
    assess_image_quality,
    apply_processing,
    image_segmentation,
)

from .structure import (
    BBox,
    BlockType,
    OCRToken,
    DocumentBlock,
    DocumentPage,
    DocumentMetadata,
    Document,
)
from .engine_router import EngineRouter
from .corrections_manager import CorrectionsDictManager
from .word_trainer import WordCorrectionDB
from .spell_checker import HybridSpellChecker
from .log_manager import AppLogger, get_app_logger
from .base_db import BaseDB
from .user_manager import UserManager
from .parallel_processor import ParallelProcessor
from .model_manager import ModelCache
from .progress_tracker import (
    ProgressCallback,
    ProgressTracker,
    ProgressRenderer,
    PipelineStep,
    ProcessingPipeline,
    StepProgress,
    create_progress_callback,
    progress_to_logger,
    GradioProgressAdapter,
    StreamlitProgressAdapter,
)

__all__ = [
    # Logger
    "logger",
    # Image processor
    "find_page_bounds",
    "auto_detect_skew",
    "smart_auto_crop",
    "remove_shadow",
    "detect_blur_laplacian",
    "sharpen_image",
    "extract_page_number",
    "assess_image_quality",
    "apply_processing",
    "image_segmentation",
    # Structure types
    "BBox", "BlockType", "OCRToken", "DocumentBlock",
    "DocumentPage", "DocumentMetadata", "Document",
    # Core modules
    "EngineRouter", "CorrectionsDictManager",
    "WordCorrectionDB", "HybridSpellChecker",
    "AppLogger", "get_app_logger",
    "BaseDB", "UserManager",
    "ParallelProcessor", "ModelCache",
    # Progress tracker
    "ProgressCallback",
    "ProgressTracker",
    "ProgressRenderer",
    "PipelineStep",
    "ProcessingPipeline",
    "StepProgress",
    "create_progress_callback",
    "progress_to_logger",
    "GradioProgressAdapter",
    "StreamlitProgressAdapter",
]