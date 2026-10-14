# packages/omni_preprocess/contract/preprocessing_result.py
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class PreprocessOperation(Enum):
    DESKEW = "deskew"
    CLEAN = "clean"
    SPLIT = "split"
    MERGE = "merge"
    REDACT = "redact"
    CONVERT = "convert"

@dataclass
class PreprocessingResult:
    """نتيجة معالجة PDF من Stirling PDF."""
    output_path: str
    operation: PreprocessOperation
    success: bool
    processing_time_ms: float
    source_path: str = ""
    page_count: int = 0
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
