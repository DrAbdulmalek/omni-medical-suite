"""Unified data models for the Readiris teacher pipeline.

Readiris (IRIS/Canon) is proprietary software: this package never embeds or
redistributes Readiris code, binaries or weights. It only *ingests the text
exports* (TXT / HTML / RTF) that a locally licensed Readiris copy produces
for the repository owner's own documents, and converts them into training
assets for our own (student) OCR models.

Contract note: the dataclasses below intentionally mirror
``tools/abbyy_teacher/models.py`` (PR #168) so both teacher pipelines emit
the same training-data contract. Extra fields are additive only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SourceFormat(str, Enum):
    """Export dialect detected in a teacher export file.

    Readiris does not expose a documented XML layout dialect like ABBYY's
    ALTO/PAGE/FineReader XML; its text-bearing exports are TXT, HTML and RTF.
    Geometry (bounding boxes) is only available in HTML exports that carry
    positioned blocks; TXT/RTF are text-only (zero boxes).
    """

    TXT = "txt"
    HTML = "html"
    RTF = "rtf"


class CropLevel(str, Enum):
    """Granularity of an image snippet (قصاصات)."""

    LINE = "line"
    WORD = "word"


@dataclass
class BBox:
    """Axis-aligned rectangle in page pixel coordinates (origin: top-left)."""

    x: int
    y: int
    w: int
    h: int

    @property
    def x1(self) -> int:
        return self.x + self.w

    @property
    def y1(self) -> int:
        return self.y + self.h

    def clamp_to(self, width: int, height: int) -> "BBox":
        """Return a copy clamped into the page bounds; never negative."""
        x0 = max(0, min(int(self.x), width))
        y0 = max(0, min(int(self.y), height))
        x2 = max(x0, min(int(self.x1), width))
        y2 = max(y0, min(int(self.y1), height))
        return BBox(x=x0, y=y0, w=x2 - x0, h=y2 - y0)

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]

    @property
    def has_geometry(self) -> bool:
        """False for text-only exports (TXT/RTF) where boxes are unknown."""
        return self.w > 0 and self.h > 0


@dataclass
class Word:
    """A single recognised word with its box and normalised confidence."""

    text: str
    bbox: BBox
    confidence: float
    line_id: str = ""
    suspicious: bool = False

    def __post_init__(self) -> None:
        self.confidence = _clamp_confidence(self.confidence)


@dataclass
class TextLine:
    """A line of text composed of words, with a merged bounding box."""

    text: str
    bbox: BBox
    confidence: float
    words: list[Word] = field(default_factory=list)
    line_id: str = ""
    block_id: str = ""

    def __post_init__(self) -> None:
        self.confidence = _clamp_confidence(self.confidence)


@dataclass
class TextBlock:
    """A layout region (paragraph, table cell, heading, picture, ...)."""

    block_id: str
    block_type: str
    bbox: BBox
    lines: list[TextLine] = field(default_factory=list)


@dataclass
class PageAnnotation:
    """Unified representation of one exported page from any teacher format."""

    source_format: SourceFormat
    image_filename: str
    width: int
    height: int
    dpi: Optional[int]
    blocks: list[TextBlock] = field(default_factory=list)
    source_path: str = ""
    # Additive provenance (not part of the #168 contract): sha256 of the
    # export file the annotation was parsed from, hex-encoded.
    export_sha256: str = ""

    @property
    def lines(self) -> list[TextLine]:
        return [line for block in self.blocks for line in block.lines]

    @property
    def words(self) -> list[Word]:
        return [word for line in self.lines for word in line.words]

    @property
    def has_geometry(self) -> bool:
        """True when at least one line carries a real (non-zero) box."""
        return any(l.bbox.has_geometry for l in self.lines)

    def mean_line_confidence(self) -> float:
        lines = self.lines
        if not lines:
            return 0.0
        return sum(l.confidence for l in lines) / len(lines)

    def suspicious_count(self) -> int:
        return sum(1 for w in self.words if w.suspicious)

    def full_text(self, separator: str = "\n") -> str:
        return separator.join(line.text for line in self.lines)

    def summary(self) -> dict[str, Any]:
        payload = {
            "source_format": self.source_format.value,
            "image_filename": self.image_filename,
            "width": self.width,
            "height": self.height,
            "dpi": self.dpi,
            "source_path": self.source_path,
            "blocks": len(self.blocks),
            "lines": len(self.lines),
            "words": len(self.words),
            "suspicious_words": self.suspicious_count(),
            "mean_line_confidence": round(self.mean_line_confidence(), 4),
            # additive keys (compatible superset of the #168 summary)
            "has_geometry": self.has_geometry,
        }
        if self.export_sha256:
            payload["export_sha256"] = self.export_sha256
        return payload


@dataclass
class CropRecord:
    """A saved image snippet (قصاصة) linked to its recognised text."""

    crop_path: str
    level: CropLevel
    text: str
    bbox: BBox
    confidence: float
    source_image: str
    page_index: int
    source_format: SourceFormat

    def to_jsonl_dict(self) -> dict[str, Any]:
        return {
            "crop_path": self.crop_path,
            "level": self.level.value,
            "text": self.text,
            "bbox": self.bbox.to_list(),
            "confidence": round(self.confidence, 4),
            "source_image": self.source_image,
            "page_index": self.page_index,
            "source_format": self.source_format.value,
        }


@dataclass
class CorrectionPair:
    """An (ocr_text -> corrected_text) training pair for post-correction models.

    Field names intentionally match the existing repo contract exported by
    ``apps/handwriting-trainer`` (see ``training-data/README.md``) and the
    ABBYY teacher pipeline (``tools/abbyy_teacher``):
    ``ocr_text, corrected_text, language, source_file, page_num,
    confidence, created_at``. Additional teacher-specific fields are additive.
    """

    ocr_text: str
    corrected_text: str
    source_file: str = ""
    page_num: int = 1
    level: str = CropLevel.LINE.value
    bbox: Optional[list[int]] = None
    confidence: Optional[float] = None
    cer: Optional[float] = None
    language: str = "unknown"
    source_format: str = ""
    created_at: str = ""
    # additive provenance
    export_sha256: str = ""


@dataclass
class RouteDecision:
    """Outcome of the hybrid cascade router for one OCR unit."""

    engine: str  # "student" | "review" | "readiris_fallback"
    reason: str
    confidence: float
    suspicious: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "suspicious": self.suspicious,
        }


def _clamp_confidence(value: Any) -> float:
    """Normalise any confidence-like value into [0.0, 1.0]."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v > 1.0:  # some engines export 0-100 scales
        v = v / 100.0
    return max(0.0, min(1.0, v))
