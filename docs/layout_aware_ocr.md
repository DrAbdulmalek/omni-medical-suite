# Layout-Aware OCR — Technical Documentation

## Overview

Layout-aware OCR is a preprocessing technique that analyzes the **physical structure** of a document page before running text recognition. Instead of feeding an entire page image to an OCR engine, it first identifies distinct regions (headers, footers, body text, tables, margins) and segments individual text lines. This dramatically improves OCR accuracy for medical documents, which often have complex layouts with headers, footers, tables, and multi-column text.

### Why It Matters for Medical Documents

Medical documents present unique OCR challenges that flat full-page OCR cannot handle well:

1. **Headers and footers** contain metadata (patient ID, page numbers, dates) that should not be mixed with body text
2. **Tables** with lab results, vital signs, or medication schedules need special handling to preserve column structure
3. **Multi-column layouts** in medical journals and textbooks require correct reading order detection
4. **Arabic RTL text** requires right-to-left reading order and proper line ordering
5. **Margin annotations** (doctor's notes, stamps) should be separated from main content

Without layout awareness, OCR engines may:
- Mix header text with body text
- Read table columns in wrong order
- Fail to handle Arabic RTL direction
- Include page numbers and footers in extracted text

## Architecture

```
                    ┌─────────────────────┐
                    │  Scanned Document   │
                    │     (raw image)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   scanner-fixer     │
                    │  (skew/crop/noise)  │  ← Preprocessing (MANDATORY)
                    │  Output: deskewed   │
                    │  image + skew_angle │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ layout_aware_       │  ← THIS MODULE
                    │ segmenter.py        │
                    │                     │
                    │ 1. LayoutDetector   │
                    │    → regions        │
                    │ 2. LineSegmenter    │
                    │    → lines          │
                    │ 3. Reading Order    │
                    │    → ordered lines  │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
      ┌────────▼────┐  ┌──────▼──────┐  ┌────▼─────┐
      │  PaddleOCR  │  │  Tesseract  │  │  EasyOCR  │
      │  (primary)  │  │  (fallback) │  │ (backup)  │
      └────────┬────┘  └──────┬──────┘  └────┬─────┘
               │               │               │
               └───────────────┼───────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  OCR Result        │
                    │  Merger + Corrector │
                    │  (ensemble output) │
                    └─────────────────────┘
```

## Algorithm Details

### 1. Layout Detection (`LayoutDetector`)

Uses heuristic-based analysis (no ML model required):

- **Horizontal projection profile**: Counts dark pixels per row to find text bands
- **Vertical projection profile**: Counts dark pixels per column to detect column structure
- **Contour density analysis**: Identifies table regions by detecting grid-like patterns
- **Header/footer heuristics**: Identifies top/bottom zones with text followed by blank separator lines
- **Margin detection**: Identifies left/right white strips with minimal ink

### 2. Line Segmentation (`LineSegmenter`)

Within each body region:

1. **Binarize** the region using adaptive thresholding
2. **Compute horizontal projection** to find text vs blank rows
3. **Group consecutive text rows** into line candidates
4. **Filter** by minimum/maximum height (removes noise and images)
5. **Refine boundaries** using connected component analysis (finds actual left/right extents of each line)
6. **Handle skew** by accepting `skew_angle` from scanner-fixer and applying rotation before segmentation

### 3. Reading Order (`get_reading_order`)

- **Arabic (RTL)**: Lines are grouped into rows by y-coordinate similarity, then within each row, lines are sorted right-to-left
- **English (LTR)**: Standard top-to-bottom, left-to-right ordering
- **Mixed**: Lines are ordered primarily by y-coordinate; RTL detection is applied per-line based on content analysis

## Usage Examples

### Basic Usage

```python
from backend.ocr.layout_aware_segmenter import LayoutAwareOCR

# Initialize for Arabic medical documents
ocr = LayoutAwareOCR(language='ar')

# Process a scanned page (after scanner-fixer preprocessing)
result = ocr.process('preprocessed_page.png', skew_angle=-1.5)

print(f"Found {result.total_lines} lines")
print(f"Regions: {[r.value for r in result.regions_used]}")

for line in result.lines:
    direction = "RTL" if line.is_rtl else "LTR"
    print(f"  Line #{line.reading_order}: {direction} at y={line.bbox[1]}")
```

### Get Cropped Lines for OCR Engines

```python
ocr = LayoutAwareOCR(language='ar')
result, line_crops = ocr.process_for_ocr_engines('page.png')

for i, (line, crop) in enumerate(zip(result.lines, line_crops)):
    if crop.size > 0:
        # Feed each crop to your OCR engine
        text = paddleocr.ocr(crop)
        line.text = text
```

### Custom Detector Configuration

```python
from backend.ocr.layout_aware_segmenter import LayoutDetector, LineSegmenter, LayoutAwareOCR

detector = LayoutDetector(
    header_fraction=0.15,    # Top 15% for header
    footer_fraction=0.10,    # Bottom 10% for footer
    margin_fraction=0.07,    # 7% side margins
    table_density_threshold=0.25,
)

segmenter = LineSegmenter(
    min_line_height=10,
    line_gap_threshold=8,
)

ocr = LayoutAwareOCR(
    language='ar',
    detector=detector,
    segmenter=segmenter,
)
```

### Skipping Specific Regions

```python
# Skip footers and tables (only process body + header)
result = ocr.process(
    'page.png',
    skip_regions=[
        RegionType.FOOTER_ZONE,
        RegionType.TABLE_REGION,
    ]
)
```

## Integration with scanner-fixer

The layout segmenter is designed to work directly with scanner-fixer output:

```python
from scanner_fixer import ScannerFixer  # scanner-fixer module
from backend.ocr.layout_aware_segmenter import LayoutAwareOCR

# Step 1: Preprocess with scanner-fixer
fixer = ScannerFixer()
deskewed, skew_angle = fixer.fix('raw_scan.png')

# Step 2: Layout-aware segmentation
ocr = LayoutAwareOCR(language='ar')
result = ocr.process(deskewed, skew_angle=skew_angle)
```

## Performance Considerations

- **No ML models**: Uses only OpenCV operations, so it's fast and has no model loading overhead
- **Typical speed**: ~50-100ms per page on a modern CPU for A4 documents
- **Memory**: Minimal — only stores projection arrays (width or height of image)
- **Scalability**: Can process pages in parallel using multiprocessing since there's no shared state

## Limitations and Future Work

- **Current**: Heuristic-based (no deep learning). May struggle with highly irregular layouts
- **Planned**: Integration with layout detection models (e.g., LayoutLM, DiT) for complex documents
- **Planned**: Table structure extraction (cell-level segmentation)
- **Planned**: Figure/diagram detection and masking
- **Planned**: Handwriting vs printed text detection per line

## File Location

``Nomni-medical-suite/backend/ocr/layout_aware_segmenter.py`

## Dependencies

- `opencv-python >= 4.5`
- `numpy >= 1.21`
- `Pillow >= 9.0`
