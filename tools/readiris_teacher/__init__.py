"""Readiris teacher pipeline.

Turns Readiris text exports (TXT / HTML / RTF) from a locally licensed copy
into training assets for the suite's own OCR models:

- parse  : unified PageAnnotation from any of the three export dialects
- crop   : line/word snippets (قصاصات) + manifest (geometry-bearing HTML only)
- align  : trusted-text alignment -> post-correction training pairs
- build  : HuggingFace-compatible JSONL + YOLO layout labels (when geometry)
- cascade: hybrid routing (student model / HITL review / Readiris fallback)

Readiris itself is proprietary (IRIS/Canon); this package only consumes its
*output files* for the owner's own documents and embeds no Readiris code,
binaries, weights or SDK. Every CLI command that ingests an export clears a
license gate (``--i-own-license`` + ``READIRIS_LICENSE_CONFIRMED=1``).

Contract note: mirrors ``tools/abbyy_teacher`` (PR #168) - same dataclasses,
same JSONL schema, additive fields only.
"""

from .alignment import (
    align_texts,
    build_correction_pair,
    cer,
    guess_language,
    levenshtein_distance,
    line_pairs_from_trusted_text,
    normalize_for_alignment,
    pairs_to_jsonl,
)
from .cascade import CascadeReport, CascadeRouter, CascadeThresholds
from .cropping import crop_segments, crop_single_box, load_manifest
from .dataset_builder import (
    BLOCK_TYPE_TO_CLASS,
    YOLO_CLASS_NAMES,
    build_layout_yolo,
    crop_records_to_pairs,
    lines_to_pairs,
    write_ocr_jsonl,
)
from .export_parsing import (
    ReadirisExportError,
    detect_format,
    parse_readiris_export,
    parse_readiris_export_all,
)
from .licensing import LICENSE_ENV_VAR, LICENSE_NOTICE, LicenseGateError, require_license
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

__version__ = "1.0.0"

__all__ = [
    "BBox",
    "BLOCK_TYPE_TO_CLASS",
    "CascadeReport",
    "CascadeRouter",
    "CascadeThresholds",
    "CorrectionPair",
    "CropLevel",
    "CropRecord",
    "LICENSE_ENV_VAR",
    "LICENSE_NOTICE",
    "LicenseGateError",
    "PageAnnotation",
    "ReadirisExportError",
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
    "lines_to_pairs",
    "load_manifest",
    "normalize_for_alignment",
    "pairs_to_jsonl",
    "parse_readiris_export",
    "parse_readiris_export_all",
    "require_license",
    "write_ocr_jsonl",
]
