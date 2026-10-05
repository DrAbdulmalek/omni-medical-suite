"""ABBYY FineReader teacher pipeline.

Turns ABBYY FineReader XML exports (ALTO / PAGE / FineReader XML) into
training assets for the suite's own OCR models:

- parse  : unified PageAnnotation from any of the three XML dialects
- crop   : line/word snippets (قصاصات) + manifest
- align  : trusted-text alignment -> post-correction training pairs
- build  : HuggingFace-compatible JSONL + YOLO layout labels
- cascade: hybrid routing (student model / HITL review / ABBYY fallback)

ABBYY FineReader itself is proprietary; this package only consumes its
XML *output files* and embeds no ABBYY code, weights or SDK.
"""

from .alignment import (
    align_texts,
    build_correction_pair,
    cer,
    guess_language,
    levenshtein_distance,
    line_pairs_from_trusted_text,
    normalize_for_alignment,
)
from .cascade import CascadeReport, CascadeRouter, CascadeThresholds
from .cropping import crop_segments, crop_single_box, load_manifest
from .dataset_builder import (
    BLOCK_TYPE_TO_CLASS,
    YOLO_CLASS_NAMES,
    build_layout_yolo,
    crop_records_to_pairs,
    write_ocr_jsonl,
)
from .models import (
    BBox,
    CorrectionPair,
    CropLevel,
    CropRecord,
    PageAnnotation,
    RouteDecision,
    SourceFormat,
    TextBlock,
    TextLine,
    Word,
)
from .xml_parsing import AbbyyXmlError, detect_format, parse_abbyy_xml, parse_abbyy_xml_all

__version__ = "1.0.0"

__all__ = [
    "AbbyyXmlError",
    "BBox",
    "BLOCK_TYPE_TO_CLASS",
    "CascadeReport",
    "CascadeRouter",
    "CascadeThresholds",
    "CorrectionPair",
    "CropLevel",
    "CropRecord",
    "PageAnnotation",
    "RouteDecision",
    "SourceFormat",
    "TextBlock",
    "TextLine",
    "Word",
    "YOLO_CLASS_NAMES",
    "align_texts",
    "build_correction_pair",
    "build_layout_yolo",
    "cer",
    "crop_records_to_pairs",
    "crop_segments",
    "crop_single_box",
    "detect_format",
    "guess_language",
    "levenshtein_distance",
    "line_pairs_from_trusted_text",
    "load_manifest",
    "normalize_for_alignment",
    "parse_abbyy_xml",
    "parse_abbyy_xml_all",
    "write_ocr_jsonl",
]
