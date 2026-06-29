"""Layout-aware OCR preprocessing module for medical documents.

Provides document layout detection, line segmentation, and reading order
optimization for Arabic and English medical documents.

This module is the next processing layer after scanner-fixer preprocessing.
It analyzes document structure to improve OCR accuracy by:
  1. Identifying document regions (header, footer, body, tables, margins)
  2. Segmenting text lines within body regions using projection profiles
  3. Ordering lines correctly for RTL (Arabic) and LTR (English) text

Pipeline position:
    scanner-fixer (skew/crop/noise) -> layout_aware_segmenter (THIS) -> OCR engines

Classes:
    LayoutRegion: Dataclass representing a detected document region.
    LineRegion: Dataclass representing a segmented text line.
    LayoutResult: Full layout detection result with all regions.
    OCRResult: Final OCR output with structured line metadata.
    LayoutDetector: Detects document regions using contour + projection analysis.
    LineSegmenter: Segments text lines with horizontal projection profiles.
    LayoutAwareOCR: Orchestrates the full layout-aware OCR pipeline.

Dependencies: opencv-python, numpy, Pillow (PIL)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image


# ============================================================================
# Data Classes
# ============================================================================


class RegionType(enum.Enum):
    """Types of document regions detected by layout analysis."""
    HEADER_ZONE = "header"
    FOOTER_ZONE = "footer"
    BODY_TEXT = "body"
    TABLE_REGION = "table"
    MARGIN_AREA = "margin"
    UNKNOWN = "unknown"


@dataclass
class LayoutRegion:
    """A rectangular region of the document with a semantic type.

    Attributes:
        region_type: Semantic type of the region (header, footer, etc.).
        bbox: Bounding box as (x, y, width, height).
        confidence: Detection confidence score (0.0 to 1.0).
    """
    region_type: RegionType
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float = 1.0

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    @property
    def area(self) -> int:
        return self.bbox[2] * self.bbox[3]

    @property
    def center(self) -> Tuple[int, int]:
        return (self.bbox[0] + self.bbox[2] // 2, self.bbox[1] + self.bbox[3] // 2)

    def crop(self, image: np.ndarray) -> np.ndarray:
        """Crop this region from the source image."""
        x, y, w, h = self.bbox
        return image[y:y + h, x:x + w]


@dataclass
class LineRegion:
    """A single text line within a document region.

    Attributes:
        bbox: Bounding box as (x, y, width, height).
        text: OCR text content (populated after OCR processing).
        confidence: Average OCR confidence score.
        reading_order: Order index for reading (0 = first line to read).
        parent_region_type: Type of the parent layout region.
        is_rtl: Whether this line is detected as right-to-left text.
    """
    bbox: Tuple[int, int, int, int]
    text: str = ""
    confidence: float = 0.0
    reading_order: int = -1
    parent_region_type: RegionType = RegionType.BODY_TEXT
    is_rtl: bool = False

    @property
    def y_center(self) -> int:
        return self.bbox[1] + self.bbox[3] // 2


@dataclass
class LayoutResult:
    """Full layout detection result.

    Attributes:
        regions: All detected layout regions.
        image_size: Original image dimensions (height, width).
        body_regions: Only the body text regions (convenience property).
        header_regions: Only header regions.
        footer_regions: Only footer regions.
        table_regions: Only table regions.
    """
    regions: List[LayoutRegion] = field(default_factory=list)
    image_size: Tuple[int, int] = (0, 0)

    @property
    def body_regions(self) -> List[LayoutRegion]:
        return [r for r in self.regions if r.region_type == RegionType.BODY_TEXT]

    @property
    def header_regions(self) -> List[LayoutRegion]:
        return [r for r in self.regions if r.region_type == RegionType.HEADER_ZONE]

    @property
    def footer_regions(self) -> List[LayoutRegion]:
        return [r for r in self.regions if r.region_type == RegionType.FOOTER_ZONE]

    @property
    def table_regions(self) -> List[LayoutRegion]:
        return [r for r in self.regions if r.region_type == RegionType.TABLE_REGION]


@dataclass
class OCRResult:
    """Final structured OCR output.

    Attributes:
        lines: Ordered list of text lines with metadata.
        full_text: Concatenated text from all lines.
        regions_used: Which layout regions were processed.
        total_lines: Total number of lines detected.
        avg_confidence: Average confidence across all lines.
    """
    lines: List[LineRegion] = field(default_factory=list)
    full_text: str = ""
    regions_used: List[RegionType] = field(default_factory=list)
    total_lines: int = 0
    avg_confidence: float = 0.0


# ============================================================================
# Layout Detector
# ============================================================================


class LayoutDetector:
    """Detects document layout regions using OpenCV contour and projection analysis.

    Uses a combination of:
    - Horizontal projection profile to find blank-line separators
    - Vertical projection profile to detect column structure
    - Contour detection for table-like regions
    - Heuristic rules for header/footer/margin detection

    This is a heuristic-based detector (no ML model required) suitable for
    scanned medical documents that follow standard page layouts.

    Example:
        detector = LayoutDetector()
        result = detector.detect(image)
        for region in result.body_regions:
            print(f"Body region at y={region.y}, h={region.height}")
    """

    def __init__(
        self,
        header_fraction: float = 0.12,
        footer_fraction: float = 0.08,
        margin_fraction: float = 0.05,
        min_region_height: int = 30,
        table_density_threshold: float = 0.3,
    ) -> None:
        """Initialize the layout detector.

        Args:
            header_fraction: Fraction of page height to consider as potential header.
            footer_fraction: Fraction of page height to consider as potential footer.
            margin_fraction: Fraction of page width to consider as margin.
            min_region_height: Minimum pixel height for a valid region.
            table_density_threshold: Text density threshold for table detection.
        """
        self.header_fraction = header_fraction
        self.footer_fraction = footer_fraction
        self.margin_fraction = margin_fraction
        self.min_region_height = min_region_height
        self.table_density_threshold = table_density_threshold

    def detect(self, image: np.ndarray) -> LayoutResult:
        """Detect layout regions in a document image.

        Args:
            image: Input image (BGR or grayscale) as numpy array.

        Returns:
            LayoutResult with all detected regions.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        h, w = gray.shape
        result = LayoutResult(image_size=(h, w))

        # Binarize
        binary = cv2.adaptiveThreshold(
            ~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 10
        )

        # Detect margins
        result.regions.extend(self._detect_margins(binary, w, h))

        # Detect header and footer using projection profiles
        result.regions.extend(self._detect_header_footer(binary, w, h))

        # Detect body text regions
        result.regions.extend(self._detect_body_regions(binary, w, h))

        # Detect table regions within body
        result.regions.extend(self._detect_tables(binary, w, h, result.body_regions))

        return result

    def _detect_margins(
        self, binary: np.ndarray, w: int, h: int
    ) -> List[LayoutRegion]:
        """Detect left and right margin areas."""
        regions = []
        margin_w = int(w * self.margin_fraction)

        # Check if left margin has little text
        left_strip = binary[:, :margin_w]
        if np.mean(left_strip) > 200:  # Mostly white
            regions.append(LayoutRegion(
                region_type=RegionType.MARGIN_AREA,
                bbox=(0, 0, margin_w, h),
                confidence=0.8,
            ))

        # Check right margin
        right_strip = binary[:, w - margin_w:]
        if np.mean(right_strip) > 200:
            regions.append(LayoutRegion(
                region_type=RegionType.MARGIN_AREA,
                bbox=(w - margin_w, 0, margin_w, h),
                confidence=0.8,
            ))

        return regions

    def _detect_header_footer(
        self, binary: np.ndarray, w: int, h: int
    ) -> List[LayoutRegion]:
        """Detect header and footer zones using horizontal projection."""
        regions = []

        # Horizontal projection (count dark pixels per row)
        h_proj = np.sum(binary < 128, axis=1).astype(float)
        h_proj_norm = h_proj / max(w, 1)

        header_limit = int(h * self.header_fraction)
        footer_start = h - int(h * self.footer_fraction)

        # Header: check if top area has text followed by a blank line
        header_text_rows = np.where(h_proj_norm[:header_limit] > 0.02)[0]
        if len(header_text_rows) > 0:
            header_end = int(header_text_rows[-1]) + 5
            # Check for separator line after header
            if header_end < header_limit:
                next_rows = h_proj_norm[header_end:min(header_end + 20, header_limit)]
                if np.mean(next_rows) < 0.01:  # Blank line found
                    regions.append(LayoutRegion(
                        region_type=RegionType.HEADER_ZONE,
                        bbox=(0, 0, w, header_end + 3),
                        confidence=0.75,
                    ))

        # Footer: check if bottom area has text preceded by a blank line
        footer_text_rows = np.where(h_proj_norm[footer_start:] > 0.02)[0]
        if len(footer_text_rows) > 0:
            footer_text_start = footer_start + int(footer_text_rows[0])
            # Check for blank line before footer
            if footer_text_start > footer_start:
                prev_rows = h_proj_norm[max(0, footer_text_start - 20):footer_text_start]
                if np.mean(prev_rows) < 0.01:
                    regions.append(LayoutRegion(
                        region_type=RegionType.FOOTER_ZONE,
                        bbox=(0, footer_text_start - 3, w, h - footer_text_start + 3),
                        confidence=0.75,
                    ))

        return regions

    def _detect_body_regions(
        self, binary: np.ndarray, w: int, h: int
    ) -> List[LayoutRegion]:
        """Detect body text regions as the area between header and footer."""
        regions = []

        # Default: entire page is body
        y_start = 0
        y_end = h

        # Adjust for detected margins
        margin_w = int(w * self.margin_fraction)
        x_start = margin_w
        x_end = w - margin_w

        if x_end <= x_start:
            x_start, x_end = 0, w

        body_h = y_end - y_start
        if body_h >= self.min_region_height:
            regions.append(LayoutRegion(
                region_type=RegionType.BODY_TEXT,
                bbox=(x_start, y_start, x_end - x_start, body_h),
                confidence=0.9,
            ))

        return regions

    def _detect_tables(
        self,
        binary: np.ndarray,
        w: int,
        h: int,
        body_regions: List[LayoutRegion],
    ) -> List[LayoutRegion]:
        """Detect table-like regions within body using contour density analysis.

        Tables are characterized by:
        - Regular horizontal and vertical line patterns
        - High density of dark pixels in a grid pattern
        - Multiple short text segments aligned in columns
        """
        table_regions = []

        for body in body_regions:
            bx, by, bw, bh = body.bbox
            body_crop = binary[by:by + bh, bx:bx + bw]

            if body_crop.size == 0:
                continue

            # Detect horizontal lines
            h_proj = np.sum(body_crop < 128, axis=1).astype(float)
            h_proj_norm = h_proj / max(bw, 1)

            # Detect vertical lines
            v_proj = np.sum(body_crop < 128, axis=0).astype(float)
            v_proj_norm = v_proj / max(bh, 1)

            # Count rows with high text density (potential table rows)
            dense_rows = np.sum(h_proj_norm > self.table_density_threshold)
            dense_cols = np.sum(v_proj_norm > self.table_density_threshold)

            # If we have many dense rows and columns, it might be a table
            row_ratio = dense_rows / max(bh, 1)
            col_ratio = dense_cols / max(bw, 1)

            if row_ratio > 0.3 and col_ratio > 0.01:
                # Find contiguous block of dense rows
                dense_mask = h_proj_norm > self.table_density_threshold
                dense_indices = np.where(dense_mask)[0]

                if len(dense_indices) > 3:
                    # Find gaps to split into separate tables
                    gaps = np.diff(dense_indices)
                    gap_threshold = 15  # pixels
                    table_starts = [dense_indices[0]]
                    table_ends = []

                    for i, gap in enumerate(gaps):
                        if gap > gap_threshold:
                            table_ends.append(dense_indices[i])
                            table_starts.append(dense_indices[i + 1])
                    table_ends.append(dense_indices[-1])

                    for ts, te in zip(table_starts, table_ends):
                        table_h = te - ts + 1
                        if table_h >= self.min_region_height:
                            table_regions.append(LayoutRegion(
                                region_type=RegionType.TABLE_REGION,
                                bbox=(bx, by + ts, bw, table_h),
                                confidence=0.6,
                            ))

        return table_regions


# ============================================================================
# Line Segmenter
# ============================================================================


class LineSegmenter:
    """Segments text lines within document regions using projection profile analysis.

    Uses horizontal projection profiles to identify text lines:
    - Rows with ink (dark pixels) indicate text
    - Rows without ink indicate line gaps
    - Connected components are grouped into lines based on vertical proximity

    Handles:
    - Skewed text (accepts skew_angle from scanner-fixer)
    - Mixed Arabic/English text
    - Multi-column layouts within a region

    Example:
        segmenter = LineSegmenter()
        lines = segmenter.segment(image, body_region, skew_angle=-2.5)
        ordered = segmenter.get_reading_order(lines, language='ar')
    """

    def __init__(
        self,
        min_line_height: int = 8,
        max_line_height: int = 200,
        line_gap_threshold: int = 5,
        min_line_width: int = 50,
    ) -> None:
        """Initialize the line segmenter.

        Args:
            min_line_height: Minimum pixel height for a valid text line.
            max_line_height: Maximum pixel height (filters out images/logos).
            line_gap_threshold: Minimum blank rows to split lines.
            min_line_width: Minimum pixel width for a valid text line.
        """
        self.min_line_height = min_line_height
        self.max_line_height = max_line_height
        self.line_gap_threshold = line_gap_threshold
        self.min_line_width = min_line_width

    def segment(
        self,
        image: np.ndarray,
        region: LayoutRegion,
        skew_angle: float = 0.0,
    ) -> List[LineRegion]:
        """Segment text lines within a layout region.

        Args:
            image: Full document image (BGR or grayscale).
            region: Layout region to segment.
            skew_angle: Skew angle in degrees (from scanner-fixer).
                           Positive = clockwise. Applied via deskew.

        Returns:
            List of LineRegion objects in top-to-bottom order.
        """
        # Crop region from image
        crop = region.crop(image)

        if crop.size == 0:
            return []

        # Convert to grayscale if needed
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop.copy()

        # Apply deskew if angle provided
        if abs(skew_angle) > 0.1:
            gray = self._deskew(gray, skew_angle)

        # Binarize
        binary = cv2.adaptiveThreshold(
            ~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 10
        )

        # Horizontal projection profile
        h_proj = np.sum(binary < 128, axis=1).astype(float)
        h, w = binary.shape
        h_proj_norm = h_proj / max(w, 1)

        # Find line start/end using projection profile
        lines = self._find_lines_from_projection(
            h_proj_norm, h, w, region, region.bbox[0], region.bbox[1]
        )

        # Refine line boundaries using connected components
        lines = self._refine_with_components(binary, lines, region.bbox[0], region.bbox[1])

        return lines

    def _deskew(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Apply deskew rotation to an image."""
        h, w = image.shape
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Calculate new image size to avoid clipping
        cos_val = abs(rotation_matrix[0, 0])
        sin_val = abs(rotation_matrix[0, 1])
        new_w = int(h * sin_val + w * cos_val)
        new_h = int(h * cos_val + w * sin_val)

        rotation_matrix[0, 2] += (new_w - w) / 2
        rotation_matrix[1, 2] += (new_h - h) / 2

        return cv2.warpAffine(
            image, rotation_matrix, (new_w, new_h),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )

    def _find_lines_from_projection(
        self,
        h_proj: np.ndarray,
        region_h: int,
        region_w: int,
        region: LayoutRegion,
        offset_x: int,
        offset_y: int,
    ) -> List[LineRegion]:
        """Find text lines from horizontal projection profile."""
        lines = []
        threshold = 0.01  # Minimum ink density to consider as text

        in_line = False
        line_start = 0

        for y in range(region_h):
            if h_proj[y] > threshold:
                if not in_line:
                    line_start = y
                    in_line = True
            else:
                if in_line:
                    # Check if the gap is long enough to split
                    gap_start = y
                    gap_length = 0
                    while y < region_h and h_proj[y] <= threshold:
                        gap_length += 1
                        y += 1

                    if gap_length >= self.line_gap_threshold:
                        # End of line
                        line_end = gap_start
                        line_height = line_end - line_start

                        if self.min_line_height <= line_height <= self.max_line_height:
                            lines.append(LineRegion(
                                bbox=(offset_x, offset_y + line_start,
                                      region_w, line_height),
                                parent_region_type=region.region_type,
                            ))
                        in_line = False
                        y -= 1  # Back up one since we advanced
                    # else: short gap within a line, continue

        # Handle last line
        if in_line:
            line_end = region_h
            line_height = line_end - line_start
            if self.min_line_height <= line_height <= self.max_line_height:
                lines.append(LineRegion(
                    bbox=(offset_x, offset_y + line_start,
                          region_w, line_height),
                    parent_region_type=region.region_type,
                ))

        return lines

    def _refine_with_components(
        self,
        binary: np.ndarray,
        lines: List[LineRegion],
        offset_x: int, offset_y: int,
    ) -> List[LineRegion]:
        """Refine line boundaries using connected component analysis.

        Finds the actual leftmost and rightmost pixels in each line region
        to create tighter bounding boxes.
        """
        refined = []

        for line in lines:
            lx, ly, lw, lh = line.bbox
            # Convert to local coordinates
            local_x = lx - offset_x
            local_y = ly - offset_y

            if (local_y < 0 or local_y + lh > binary.shape[0] or
                    local_x < 0 or local_x + lw > binary.shape[1]):
                refined.append(line)
                continue

            line_crop = binary[local_y:local_y + lh, local_x:local_x + lw]
            if line_crop.size == 0:
                refined.append(line)
                continue

            # Find connected components
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                ~line_crop, connectivity=8
            )

            if num_labels <= 1:  # Only background
                continue

            # Find bounding box of all non-background components
            min_x, max_x = lw, 0
            for label_id in range(1, num_labels):
                sx = stats[label_id, cv2.CC_STAT_LEFT]
                sw = stats[label_id, cv2.CC_STAT_WIDTH]
                sh = stats[label_id, cv2.CC_STAT_HEIGHT]
                # Skip noise (very small components)
                if sh >= 3 and sw >= 2:
                    min_x = min(min_x, sx)
                    max_x = max(max_x, sx + sw)

            if max_x > min_x and (max_x - min_x) >= self.min_line_width:
                refined.append(LineRegion(
                    bbox=(offset_x + min_x, ly, max_x - min_x, lh),
                    parent_region_type=line.parent_region_type,
                ))
            elif max_x > min_x:
                # Short line but still valid
                refined.append(LineRegion(
                    bbox=(offset_x + min_x, ly, max_x - min_x, lh),
                    parent_region_type=line.parent_region_type,
                ))
            # else: no valid components found, skip

        return refined

    def get_reading_order(
        self,
        lines: List[LineRegion],
        language: str = "ar",
    ) -> List[LineRegion]:
        """Determine correct reading order for segmented lines.

        For Arabic (RTL) documents:
        - Lines are read top-to-bottom (same as LTR)
        - Within multi-column layouts, right column is read first
        - Text within each line flows right-to-left

        For English (LTR) documents:
        - Lines read top-to-bottom, left-to-right

        Args:
            lines: Segmented line regions.
            language: Primary language ('ar' for Arabic RTL, 'en' for English LTR).

        Returns:
            Lines sorted in correct reading order with reading_order set.
        """
        if not lines:
            return []

        is_rtl = language.lower().startswith("ar")

        # Sort by y-coordinate first (top to bottom)
        sorted_by_y = sorted(lines, key=lambda l: l.y_center)

        # Group lines into rows (lines with similar y_center)
        row_groups: List[List[LineRegion]] = []
        current_row: List[LineRegion] = [sorted_by_y[0]]
        row_tolerance = 10  # pixels

        for line in sorted_by_y[1:]:
            if abs(line.y_center - current_row[0].y_center) <= row_tolerance:
                current_row.append(line)
            else:
                row_groups.append(current_row)
                current_row = [line]
        row_groups.append(current_row)

        # Within each row, sort by x position (RTL: right-to-left, LTR: left-to-right)
        ordered_lines: List[LineRegion] = []
        order = 0

        for row in row_groups:
            if is_rtl:
                # Arabic: right column/line first
                row_sorted = sorted(row, key=lambda l: -l.bbox[0])
                for line in row_sorted:
                    line.is_rtl = True
            else:
                row_sorted = sorted(row, key=lambda l: l.bbox[0])

            for line in row_sorted:
                line.reading_order = order
                ordered_lines.append(line)
                order += 1

        return ordered_lines


# ============================================================================
# Layout-Aware OCR Orchestrator
# ============================================================================


class LayoutAwareOCR:
    """Orchestrates the full layout-aware OCR pipeline.

    Pipeline:
        1. Load image
        2. Detect document layout (header, footer, body, tables, margins)
        3. Segment text lines within body regions
        4. Apply correct reading order (RTL for Arabic, LTR for English)
        5. Return structured result with line metadata

    Note: This module does NOT perform actual OCR text recognition.
    It prepares the image for OCR by identifying regions and lines.
    The actual text recognition is done by downstream OCR engines
    (PaddleOCR, Tesseract, EasyOCR, TrOCR).

    Integration:
        scanner-fixer output (deskewed image + skew_angle)
            -> LayoutAwareOCR.process()
                -> List[LineRegion] with reading order
                    -> OCR engine processes each line

    Example:
        ocr_pipeline = LayoutAwareOCR(language='ar')
        result = ocr_pipeline.process('scanned_page.png', skew_angle=-1.5)
        for line in result.lines:
            print(f"Line {line.reading_order}: y={line.bbox[1]}, w={line.bbox[2]}")
    """

    def __init__(
        self,
        language: str = "ar",
        detector: Optional[LayoutDetector] = None,
        segmenter: Optional[LineSegmenter] = None,
    ) -> None:
        """Initialize the layout-aware OCR pipeline.

        Args:
            language: Primary document language ('ar' or 'en').
            detector: Custom LayoutDetector instance (uses defaults if None).
            segmenter: Custom LineSegmenter instance (uses defaults if None).
        """
        self.language = language
        self.detector = detector or LayoutDetector()
        self.segmenter = segmenter or LineSegmenter()

    def process(
        self,
        image: Union[str, Path, np.ndarray, Image.Image],
        skew_angle: float = 0.0,
        skip_regions: Optional[List[RegionType]] = None,
    ) -> OCRResult:
        """Process a document image through the full layout-aware pipeline.

        Args:
            image: Input image as file path, numpy array, or PIL Image.
            skew_angle: Skew angle in degrees (from scanner-fixer output).
            skip_regions: Region types to skip (e.g., [RegionType.FOOTER_ZONE]).

        Returns:
            OCRResult with all lines in reading order.
        """
        # Load image
        img_array = self._load_image(image)
        if img_array is None:
            return OCRResult()

        # Skip regions (default: skip footers and margins)
        if skip_regions is None:
            skip_regions = [RegionType.FOOTER_ZONE, RegionType.MARGIN_AREA]

        # Step 1: Detect layout
        layout = self.detector.detect(img_array)

        # Step 2: Filter regions to process
        process_regions = [
            r for r in layout.regions
            if r.region_type not in skip_regions
            and r.region_type != RegionType.UNKNOWN
        ]

        # Step 3: Segment lines in each region
        all_lines: List[LineRegion] = []
        for region in process_regions:
            lines = self.segmenter.segment(img_array, region, skew_angle=skew_angle)
            all_lines.extend(lines)

        # Step 4: Apply reading order
        ordered_lines = self.segmenter.get_reading_order(all_lines, self.language)

        # Step 5: Build result
        regions_used = list({r.region_type for r in process_regions})
        avg_conf = (
            np.mean([l.confidence for l in ordered_lines])
            if ordered_lines else 0.0
        )

        return OCRResult(
            lines=ordered_lines,
            full_text="",  # Populated by downstream OCR engines
            regions_used=regions_used,
            total_lines=len(ordered_lines),
            avg_confidence=float(avg_conf),
        )

    def process_for_ocr_engines(
        self,
        image: Union[str, Path, np.ndarray, Image.Image],
        skew_angle: float = 0.0,
    ) -> Tuple[OCRResult, List[np.ndarray]]:
        """Process image and extract cropped line images for OCR engines.

        This is a convenience method that returns both the structured result
        and the individual line crops ready to be fed to OCR engines.

        Args:
            image: Input image.
            skew_angle: Skew angle from scanner-fixer.

        Returns:
            Tuple of (OCRResult, list of cropped line images in reading order).
        """
        img_array = self._load_image(image)
        if img_array is None:
            return OCRResult(), []

        result = self.process(img_array, skew_angle=skew_angle)

        # Crop each line from the image
        line_crops = []
        for line in result.lines:
            x, y, w, h = line.bbox
            if y >= 0 and y + h <= img_array.shape[0] and x >= 0 and x + w <= img_array.shape[1]:
                crop = img_array[y:y + h, x:x + w]
                line_crops.append(crop)
            else:
                line_crops.append(np.array([]))

        return result, line_crops

    def _load_image(self, image: Union[str, Path, np.ndarray, Image.Image]) -> Optional[np.ndarray]:
        """Load an image from various input formats into a numpy array."""
        if isinstance(image, np.ndarray):
            return image
        if isinstance(image, Image.Image):
            return np.array(image)
        if isinstance(image, (str, Path)):
            path = str(image)
            if not Path(path).exists():
                return None
            img = cv2.imread(path)
            return img
        return None


# ============================================================================
# Demo / Self-Test
# ============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Layout-Aware OCR Segmenter — Self-Test")
    print("=" * 60)

    # Create a synthetic test image with header, body, footer
    test_image = np.ones((800, 600, 3), dtype=np.uint8) * 255

    # Draw header text (simulated with rectangles)
    cv2.rectangle(test_image, (50, 20), (550, 50), (0, 0, 0), -1)
    cv2.rectangle(test_image, (50, 55), (300, 65), (0, 0, 0), -1)  # separator

    # Draw body text lines
    for i in range(20):
        y = 100 + i * 30
        line_width = np.random.randint(300, 550)
        cv2.rectangle(test_image, (50, y), (50 + line_width, y + 12), (0, 0, 0), -1)

    # Draw a table-like region
    for row in range(5):
        y = 750 + row * 8
        for col in range(4):
            x = 50 + col * 140
            cv2.rectangle(test_image, (x, y), (x + 80, y + 6), (0, 0, 0), -1)

    # Draw footer
    cv2.rectangle(test_image, (200, 785), (400, 795), (0, 0, 0), -1)

    # Run pipeline
    ocr = LayoutAwareOCR(language="ar")
    result = ocr.process(test_image, skew_angle=0)

    print(f"\nImage size: {test_image.shape[1]}x{test_image.shape[0]}")
    print(f"Regions detected: {len(result.regions_used)}")
    print(f"Region types: {[r.value for r in result.regions_used]}")
    print(f"Lines segmented: {result.total_lines}")
    print(f"Average confidence: {result.avg_confidence:.2f}")

    print("\nLine details (first 5):")
    for line in result.lines[:5]:
        direction = "RTL" if line.is_rtl else "LTR"
        print(f"  #{line.reading_order}: y={line.bbox[1]:3d}, "
              f"w={line.bbox[2]:3d}, h={line.bbox[3]:2d}, "
              f"{direction}, parent={line.parent_region_type.value}")

    if result.total_lines > 5:
        print(f"  ... ({result.total_lines - 5} more lines)")

    # Test with a file if provided as argument
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"\nProcessing file: {image_path}")
        file_result = ocr.process(image_path)
        print(f"Lines found: {file_result.total_lines}")
        for line in file_result.lines[:10]:
            print(f"  #{line.reading_order}: ({line.bbox[0]}, {line.bbox[1]}, "
                  f"{line.bbox[2]}, {line.bbox[3]})")

    print("\n" + "=" * 60)
    print("Self-test complete.")
    print("=" * 60)
