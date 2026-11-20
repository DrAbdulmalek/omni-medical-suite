"""Unified data models for the ABBYY FineReader teacher pipeline.

ABBYY FineReader is proprietary software: this package never embeds or
redistributes ABBYY code or weights. It only *ingests the XML exports*
(ALTO XML, PAGE XML, FineReader XML) that ABBYY produces when a human
operator reviews its results, and converts them into training assets for
our own (student) OCR models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SourceFormat(str, Enum):
    """XML dialect detected in a teacher export file."""

    ALTO = "alto"
    PAGE = "page"
    FINEREADER = "finereader"


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

    @classmethod
    def from_points(cls, points: list[tuple[int, int]]) -> "BBox":
        """Bounding box of a polygon (PAGE XML ``Coords points``)."""
        xs = [int(p[0]) for p in points]
        ys = [int(p[1]) for p in points]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return cls(x=x0, y=y0, w=max(0, x1 - x0), h=max(0, y1 - y0))


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

    @property
    def lines(self) -> list[TextLine]:
        return [line for block in self.blocks for line in block.lines]

    @property
    def words(self) -> list[Word]:
        return [word for line in self.lines for word in line.words]

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
        return {
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
        }


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
    ``apps/handwriting-trainer`` (see ``training-data/README.md``):
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


@dataclass
class RouteDecision:
    """Outcome of the hybrid cascade router for one OCR unit."""

    engine: str  # "student" | "review" | "abbyy_fallback"
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
    if v > 1.0:  # ABBYY sometimes exports 0-100 scales
        v = v / 100.0
    return max(0.0, min(1.0, v))
