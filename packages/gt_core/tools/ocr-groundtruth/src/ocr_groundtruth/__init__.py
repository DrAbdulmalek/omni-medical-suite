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

from .alignment import align_two_sources, compute_similarity_ratio, merge_multi_source, tokenize
from .evaluate import (
    character_error_rate,
    compare_engines,
    evaluate_engine_output,
    word_error_rate,
)
from .groundtruth_builder import build_dataset_from_folder, build_ground_truth_record
from .pdf_extractor import extract_pdf_lines, extract_pdf_text, extract_pdf_words, is_text_layer_present

__version__ = "1.0.0"

__all__ = [
    "align_two_sources",
    "build_dataset_from_folder",
    "build_ground_truth_record",
    "character_error_rate",
    "compare_engines",
    "compute_similarity_ratio",
    "evaluate_engine_output",
    "extract_pdf_lines",
    "extract_pdf_text",
    "extract_pdf_words",
    "is_text_layer_present",
    "merge_multi_source",
    "tokenize",
    "word_error_rate",
]
