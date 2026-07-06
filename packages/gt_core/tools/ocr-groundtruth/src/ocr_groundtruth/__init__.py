"""
ocr_groundtruth: Build verified ground-truth datasets from ABBYY FineReader
and Readiris OCR output, and use them to evaluate your own OCR engines
with real CER/WER (not estimated numbers).

Workflow:
    1. OCR your documents in ABBYY FineReader 16 and/or Readiris 23
       (via VMware), export as searchable PDF.
    2. Use build_dataset_from_folder() to merge and align the text layers.
    3. Use evaluate.compare_engines() to measure your own pipeline's
       actual accuracy against the merged ground truth.
"""

from .pdf_extractor import extract_pdf_text, extract_pdf_words, extract_pdf_lines, is_text_layer_present
from .alignment import tokenize, align_two_sources, merge_multi_source, compute_similarity_ratio
from .groundtruth_builder import build_ground_truth_record, build_dataset_from_folder
from .evaluate import (
    character_error_rate,
    word_error_rate,
    evaluate_engine_output,
    compare_engines,
)

__version__ = "1.0.0"

__all__ = [
    "extract_pdf_text",
    "extract_pdf_words",
    "extract_pdf_lines",
    "is_text_layer_present",
    "tokenize",
    "align_two_sources",
    "merge_multi_source",
    "compute_similarity_ratio",
    "build_ground_truth_record",
    "build_dataset_from_folder",
    "character_error_rate",
    "word_error_rate",
    "evaluate_engine_output",
    "compare_engines",
]
