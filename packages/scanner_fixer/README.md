# scanner-fixer

Pre-OCR image normalization for scanned documents.  
Part of the **OmniMedical OCR Ecosystem**.

## What it does

| Step | What | Why |
|------|------|-----|
| **Crop** | Removes dark scanner borders | Clean input for OCR |
| **Rotate** | Detects and fixes 180° flips | Upside-down pages |
| **Deskew** | Corrects small tilt angles | Scanner misalignment |
| **Enhance** | CLAHE contrast + denoise + sharpen | Better OCR accuracy |

## Install

```bash
pip install -e .

# With Tesseract OSD support (more accurate rotation detection):
pip install -e ".[tesseract]"
```

## Usage

### Single image
```bash
scanner-fixer fix scan.jpg
scanner-fixer fix scan.jpg --output fixed.jpg --report
scanner-fixer fix scan.jpg --binarize          # For text-only pages
scanner-fixer fix scan.jpg --no-rotate         # Skip rotation detection
```

### Batch processing
```bash
scanner-fixer batch ./scans/ --output-dir ./fixed/
scanner-fixer batch ./scans/ --binarize --suffix _ocr
```

### Image info
```bash
scanner-fixer info scan.jpg
```

### Python API
```python
from scanner_fixer import fix_scan

result = fix_scan("scan.jpg", output_path="fixed.jpg")
print(result["report"])
# {'rotation_applied_deg': 180, 'skew_corrected_deg': 2.5, 'final_size': '2480x3508'}

# From numpy array
import cv2
img = cv2.imread("scan.jpg")
result = fix_scan(img)
fixed_image = result["image"]

# Batch
from scanner_fixer import fix_scan_batch
from pathlib import Path

results = fix_scan_batch(
    input_paths=list(Path("./scans").glob("*.jpg")),
    output_dir="./fixed"
)
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--binarize` | False | Convert to B&W (text-only pages) |
| `--no-crop` | - | Skip border removal |
| `--no-rotate` | - | Skip 180° rotation detection |
| `--no-deskew` | - | Skip tilt correction |
| `--no-enhance` | - | Skip contrast/denoise |
| `--deskew-method` | hough | `hough` or `projection` |
| `--use-tesseract` | False | Tesseract OSD for rotation |
| `--report` | False | Print JSON processing report |

## Pipeline control

```python
result = fix_scan(
    "scan.jpg",
    do_crop=True,
    do_rotate=True,
    do_deskew=True,
    do_enhance=True,
    binarize=False,          # True for text-only
    target_dpi=300,          # Upsample if below 300 DPI
    use_tesseract_osd=False, # More accurate but requires pytesseract
    deskew_method="hough",   # "hough" or "projection"
    crop_padding=10,
)
```

## Run tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Integration with omni-medical-suite

```python
# In omni-medical-suite core/pipeline.py:
from scanner_fixer import fix_scan

def process_document(image_path, config):
    if config.preprocessing.scanner_fixer.enabled:
        result = fix_scan(image_path)
        image = result["image"]
    # ... continue with OCR
```
