# ocr-groundtruth

Build verified OCR ground truth from **ABBYY FineReader 16** and **Readiris 23**,
and use it to evaluate your own OCR engines with **real CER/WER** — not invented numbers.

## Important limitation discovered (read first)

ABBYY FineReader 16 (consumer edition) and Readiris 23 do **not** export ALTO XML or
hOCR — that requires ABBYY FineReader **Engine/Server** (developer edition), which you
likely don't have. Both tools *do* export **searchable PDF** (PDF with an invisible OCR
text layer), which is the common format this tool works with.

This means you get text + word positions extracted from the PDF text layer
(via PyMuPDF), not native ALTO/hOCR confidence scores from ABBYY/Readiris themselves.

## Workflow

```
1. In VMware (Windows guest):
   - Open ABBYY FineReader 16 → OCR your scanned images → Export as searchable PDF
   - Open Readiris 23 → OCR the same images → Export as searchable PDF
   - Save both to a shared folder, same filename stem (e.g. 0001.pdf in both)

2. On Manjaro:
   ocr-groundtruth build-batch \
       --abbyy-dir ./shared/abbyy_output/ \
       --readiris-dir ./shared/readiris_output/ \
       --output ./ground_truth/

3. This produces one JSON per document:
   - merged_text: best-guess ground truth (where ABBYY and Readiris agree)
   - word_results: per-word agreement detail (full / majority / conflict)
   - review_needed: True if any word disagreed (needs human check)

4. Evaluate YOUR engine (scanner-fixer + Tesseract/EasyOCR) against it:
   ocr-groundtruth evaluate \
       --ground-truth ./ground_truth/0001.json \
       --engine-output ./my_engine_output/0001.txt \
       --engine-name "scanner_fixer_v1"
```

## Install

```bash
pip install -e .
```

## Python API

### Build ground truth from one document
```python
from ocr_groundtruth import build_ground_truth_record

record = build_ground_truth_record(
    image_id="0001",
    abbyy_pdf="abbyy_output/0001.pdf",
    readiris_pdf="readiris_output/0001.pdf",
)

print(record["merged_text"])
print(record["stats"])
# {'total_words': 142, 'full_agreement': 138, 'conflicts': 4, 'agreement_rate': 0.972}
```

### Add your own engine as a third source (improves voting)
```python
record = build_ground_truth_record(
    image_id="0001",
    abbyy_pdf="abbyy_output/0001.pdf",
    readiris_pdf="readiris_output/0001.pdf",
    extra_sources={
        "tesseract": open("my_tesseract_output/0001.txt").read(),
    },
)
```

### Batch process a whole folder
```python
from ocr_groundtruth import build_dataset_from_folder

results = build_dataset_from_folder(
    abbyy_dir="abbyy_output/",
    readiris_dir="readiris_output/",
    output_dir="ground_truth/",
)
```

### Measure real CER/WER — did scanner-fixer actually help?
```python
from ocr_groundtruth import compare_engines

ground_truth = "Patient Name John Doe Diagnosis Acute bronchitis"

result = compare_engines(ground_truth, {
    "tesseract_raw": "Patiant Nam Jon Doe Diagnosls Acut bronchltis",
    "tesseract_with_scanner_fixer": "Patient Name John Doe Diagnosis Acute bronchitis",
})

print(result["best_wer"])
# "tesseract_with_scanner_fixer"

for r in result["results"]:
    print(r["engine"], "CER:", r["cer"], "WER:", r["wer"])
# tesseract_raw                  CER: 0.1429  WER: 0.8571
# tesseract_with_scanner_fixer   CER: 0.0     WER: 0.0
```

## How word agreement works

When you have 2+ OCR sources for the same document, each word position is voted on:

| Sources agree | Result | Confidence |
|---|---|---|
| All sources say the same word | `full` | 1.0 |
| Strict majority agrees (e.g. 2-of-3) | `majority` | proportional |
| Tie or no majority (e.g. ABBYY vs Readiris disagree 1-vs-1) | `conflict` | 0.5 |

Records with any `conflict` are flagged `review_needed: true` so you can spot-check
them manually — this is much faster than reviewing every page from scratch, since you
only review the disagreements.

## CLI reference

```bash
ocr-groundtruth build-one --abbyy a.pdf --readiris b.pdf --id doc001
ocr-groundtruth build-batch --abbyy-dir ./a/ --readiris-dir ./b/ --output ./gt/
ocr-groundtruth evaluate --ground-truth gt/doc001.json --engine-output out.txt --engine-name myengine
```

## Run tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Integration with omni-medical-suite / scanner-fixer

Use this to close the loop that was previously unverified — does `scanner-fixer`
actually improve OCR accuracy, or does it just look cleaner visually?

```python
import cv2
from scanner_fixer import fix_scan
import pytesseract
from ocr_groundtruth import evaluate_engine_output
import json

# Ground truth already built from ABBYY + Readiris
gt = json.loads(open("ground_truth/0001.json").read())["merged_text"]

# Run Tesseract on raw scan vs scanner-fixer output
raw_text = pytesseract.image_to_string(cv2.imread("raw_scans/0001.png"), lang="ara+eng")
fixed = fix_scan("raw_scans/0001.png")
fixed_text = pytesseract.image_to_string(fixed["image"], lang="ara+eng")

raw_eval = evaluate_engine_output(gt, raw_text, "raw")
fixed_eval = evaluate_engine_output(gt, fixed_text, "scanner_fixer")

print(f"Raw:           CER={raw_eval['cer']}  WER={raw_eval['wer']}")
print(f"Scanner-fixer: CER={fixed_eval['cer']}  WER={fixed_eval['wer']}")
```

This is the real measurement that was missing before — not an estimate, an
actual number computed from real ABBYY/Readiris-verified ground truth.
