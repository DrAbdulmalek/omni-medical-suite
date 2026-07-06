# Medical OCR Ground Truth System

> Comprehensive system for importing, comparing, and improving Arabic Medical OCR using Ground Truth from ABBYY FineReader, ReadIRIS, and PDF Grabber.

**Author:** Dr. Abdulmalek
**License:** MIT
**Layer:** Core Library (Layer 1)

---

## Architecture Position

```
Layer 1: Core Engines
  ├── medical-ocr-postprocessor  ← Uses our dictionary
  ├── medical-ocr-benchmarks     ← Uses our benchmark tool
  └── medical-ocr-ground-truth    ← THIS REPO
        ↓
Layer 2: Product Apps
  ├── medical-handwriting-ocr     ← Integrates snippet trainer
  └── medical-doc-processor       ← Uses patch + dict
        ↓
Layer 3: Platform
  └── omni-medical-suite          ← Full integration
        ↓
Layer 4: Deployment
  └── medical-ocr-trainer-hf      ← HF Space demo
```

---

## What This System Does

| Feature | Description |
|---------|-------------|
| **GT Import** | Import Word/RTF/PDF from ABBYY, ReadIRIS, PDF Grabber |
| **OCR Benchmark** | Measure CER, WER, Medical Term Accuracy |
| **Auto Dictionary** | Generate correction dictionaries from OCR errors |
| **Font Validation** | Validate OCR chars against PDF font glyphs |
| **Snippet Trainer** | Interactive learning from user corrections |
| **Postprocessor Patch** | Drop-in correction for Arabic medical OCR |
| **Full Pipeline** | One-command automated workflow |

---

## Quick Start

### Install Dependencies

```bash
pip install -r requirements_ground_truth.txt
```

### Run Full Pipeline (One Command)

```bash
python run_full_pipeline.py \
    --abbyy "abbyy_output.docx" \
    --image "scanned_page.jpg" \
    --output-dir "pipeline_output"
```

### Individual Tools

```bash
# Import Ground Truth from ABBYY
python import_ground_truth.py abbyy_output.docx --output gt.txt

# Compare OCR with Ground Truth
python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt --generate-dict

# Run OCR Benchmark
python ocr_benchmark.py --ground-truth-file gt.txt --ocr-file ocr.txt

# Apply Postprocessor Patch
python medical_doc_gui_patch.py  # Demo with built-in test

# Interactive Snippet Training
python snippet_review_ui.py
```

---

## Pipeline Workflow

```
ABBYY (.docx) ──────┐
                     │     ┌──────────────┐     ┌─────────────────┐
ReadIRIS (.rtf) ────┼────▶│  Import GT   │────▶│  Ground Truth   │
                     │     │  (Step 1)    │     │  Database       │
PDF Grabber (.json) ─┘     └──────────────┘     └────────┬────────┘
                                                            │
Scanned Image (.jpg) ──────▶┌──────────────┐              │
                            │  Run OCR     │              │
                            │  (Step 2)    │              │
                            └──────┬───────┘              │
                                   │                      │
                            ┌──────▼───────┐     ┌───────▼────────┐
                            │  Postprocess  │     │  Compare &     │
                            │  Patch (Step3)│     │  Benchmark (4) │
                            └──────┬───────┘     └───────┬────────┘
                                   │                      │
                            ┌──────▼──────────────────────▼───────┐
                            │  Export: Dictionary + Training Data  │
                            │  (Step 5)                            │
                            └──────────────────┬──────────────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │  Final Report (Step6) │
                                    │  CER / WER / Med Acc │
                                    └─────────────────────┘
```

---

## File Reference

| File | Lines | Description |
|------|-------|-------------|
| `run_full_pipeline.py` | ~1200 | **Main entry point** — 8-step automated pipeline |
| `import_ground_truth.py` | ~500 | Import .docx/.rtf/.pdf/.html as Ground Truth |
| `gt_comparison_engine.py` | ~390 | Compare OCR vs GT — CER/WER + auto dictionary |
| `ocr_benchmark.py` | ~510 | Standalone benchmark tool |
| `font_glyph_validator.py` | ~343 | Validate OCR chars against font data |
| `training_pipeline_manager.py` | ~313 | Pipeline orchestration (6-step) |
| `medical_doc_gui_patch.py` | ~360 | Postprocessor patch v13.2 for Arabic medical OCR |
| `ocr_snippet_trainer.py` | ~1120 | Interactive snippet learning system with SQLite |
| `snippet_cli.py` | ~338 | CLI for snippet training |
| `snippet_review_ui.py` | ~479 | Tkinter GUI for snippet review |
| `arabic_medical_dict.json` | 270 entries | Medical correction dictionary |

---

## Benchmark Results (Page 588)

Tested on a scanned Arabic medical textbook index page (21 medical terms):

| Metric | Before Patch | After Patch | Improvement |
|--------|-------------|-------------|-------------|
| **CER** | 35.21% | 30.28% | +4.93% |
| **WER** | 68.24% | 40.00% | +28.24% |
| **Medical Accuracy** | 24% (7/29) | 83% (24/29) | +59% |
| **Terms Fixed** | — | 17 new | — |

### Remaining Challenges

The 5 unfixed terms require **line segmentation improvements** (merging split lines):

- "رأس الفخذ" — split across lines
- "عسرات التصنع" — parts separated
- "غياب الأطراف الخلقي" — word omission
- "تشوهات العمود الفقري" — reordering
- "التشوهات الخلقية" — fragmentation

---

## Dictionary Structure

The `arabic_medical_dict.json` contains 270 entries in 3 categories:

```json
{
  "_meta": { "name": "Arabic Medical OCR Correction Dictionary", "version": "1.0.0" },
  "corrections": { "الشثل": "الشلل", "الهيكنية": "الهيكلية", ... },
  "phrases": { "متلازمة داء بر تن": "متلازمة داء برتن", ... },
  "regex_patterns": [
    { "pattern": "الشن(?!ل)", "replacement": "الشلل", "description": "Fix paralysis term" }
  ]
}
```

---

## Integration with Other Repos

### medical-ocr-postprocessor
```python
from medical_doc_gui_patch import patch_ocr_result
result = patch_ocr_result(ocr_result, dictionary_path="arabic_medical_dict.json")
```

### medical-handwriting-ocr / omni-medical-suite
```python
from ocr_snippet_trainer import OCRSnippetTrainer
trainer = OCRSnippetTrainer(db_path="data/snippets.db", dictionary_path="arabic_medical_dict.json")
snippets = trainer.process_image("document.jpg", engine="paddleocr")
```

---

## Requirements

```
python>=3.10
opencv-python-headless>=4.8.0
pillow>=10.0
numpy>=1.24.0
easyocr>=1.7.1
paddleocr>=2.7.0
pytesseract>=0.3.10
python-docx>=0.8.11
PyMuPDF>=1.23.0
arabic-reshaper>=3.0
python-bidi>=0.4.2
```

---

## Related Repositories

| Repo | Role |
|------|------|
| [medical-ocr-postprocessor](https://github.com/DrAbdulmalek/medical-ocr-postprocessor) | Core correction engine |
| [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) | Main platform |
| [medical-handwriting-ocr](https://github.com/DrAbdulmalek/medical-handwriting-ocr) | Handwriting OCR |
| [medical-ocr-benchmarks](https://github.com/DrAbdulmalek/medical-ocr-benchmarks) | Benchmark suite |
| [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer) | Training tool |
| [medical-ocr-trainer-hf](https://github.com/DrAbdulmalek/medical-ocr-trainer-hf) | HF Space deployment |

---

## Built-in Tools

This repository includes utility tools to streamline ground truth creation and evaluation.

### `tools/ocr-groundtruth`

A CLI tool for building ground truth from ABBYY/Readiris PDFs and measuring CER/WER.

**Usage:**
```bash
cd tools/ocr-groundtruth
pip install -e .
python -m ocr_groundtruth.cli --help
```

> **Note:** This tool was merged from the standalone `ocr-groundtruth` repository (now archived). All future development happens here as part of the official ground truth ecosystem.

---

## Governance

- **Versioned Datasets Policy**: See [DATASETS_POLICY.md](DATASETS_POLICY.md) for dataset versioning, quality gates, and release process
- **Validation**: Run `python validate_dataset.py --data-dir data/vX.Y.Z/` before any release
- **Official Status**: This repository is the **single source of truth** for ground truth data across the Medical OCR Ecosystem
