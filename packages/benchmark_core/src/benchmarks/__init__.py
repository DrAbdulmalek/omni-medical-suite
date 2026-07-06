"""
medical-ocr-benchmarks — Benchmark suite for measuring OCR quality on medical documents.
Benchmark Suite لقياس جودة التعرف البصري على الوثائق الطبية.

This package provides tools to:
- Run OCR benchmarks across multiple engines (PaddleOCR, Tesseract, EasyOCR, TrOCR, Surya)
- Calculate metrics: CER, WER, medical term accuracy, latency, throughput
- Generate reports in Markdown, JSON, and HTML
- Check CI thresholds for automatic failure detection
- Manage test datasets across specialties and languages
"""

__version__ = "0.1.0"
__author__ = "Dr. Abdulmalek"

from benchmarks.metrics import (
    character_error_rate,
    word_error_rate,
    medical_term_accuracy,
    calculate_all_metrics,
)
from benchmarks.dataset import DatasetManager
from benchmarks.runner import BenchmarkRunner
from benchmarks.report import ReportGenerator
from benchmarks.ci import ThresholdChecker

__all__ = [
    "character_error_rate",
    "word_error_rate",
    "medical_term_accuracy",
    "calculate_all_metrics",
    "DatasetManager",
    "BenchmarkRunner",
    "ReportGenerator",
    "ThresholdChecker",
]
