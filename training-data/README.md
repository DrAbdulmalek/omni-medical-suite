# Training Data — Handwriting OCR Ground Truth

This directory contains training samples and generated ground-truth data
for improving handwriting recognition models in the Omni Medical Suite.

## Directory Structure

```
training-data/
├── samples/                    # Raw training sample files
│   ├── medical/                # Arabic handwritten medical documents
│   │   └── (PDFs and extracted page images)
│   └── technical/              # English/German technical documents
│       └── (includes 180° rotated pages for robustness testing)
├── corrections/                # Generated ground-truth data
│   ├── handwriting_corrections.db   # SQLite database of word-level corrections
│   └── handwriting_gt.jsonl         # Exported JSONL for HuggingFace Datasets
└── README.md                   # This file
```

## Sample Files

### Medical Sample (Arabic Handwriting)
- **Content**: Handwritten Arabic medical documents (prescriptions, notes, reports)
- **Purpose**: Training OCR models for Arabic medical handwriting recognition
- **Characteristics**: Mixed Arabic text with medical terminology, numbers, and Latin drug names
- **Source**: Scanned at 200-300 DPI

### Technical Sample (English/German)
- **Content**: Handwritten technical documents with diagrams and formulas
- **Special**: Some pages are rotated 180° (upside-down) to test auto-rotation
- **Purpose**: Training robust OCR for multi-language technical handwriting
- **Characteristics**: Mixed English/German text, technical terms, mathematical notation

## How to Use

### 1. Add Sample PDFs
Place sample PDF files in the appropriate subdirectory:
```bash
training-data/samples/medical/sample_medical.pdf
training-data/samples/technical/sample_technical.pdf
```

### 2. Run the Handwriting Trainer
```bash
# Monorepo version
python apps/handwriting-trainer/app.py

# Or deploy the standalone HF Space
cd hf-spaces/handwriting-trainer
python app.py
```

### 3. Correct & Export
- Upload a sample PDF in the trainer
- Correct OCR results word by word
- Export to JSONL for model training

### 4. Train a Model
```python
from datasets import load_dataset

ds = load_dataset('json', data_files='training-data/corrections/handwriting_gt.jsonl')
ds.push_to_hub('DrAbdulmalek/handwriting-corrections-ar-en-de')
```

## Data Format (JSONL)

Each line in the export file:
```json
{
  "ocr_text": "predicted OCR text",
  "corrected_text": "user-provided ground truth",
  "language": "arabic|english|german|unknown",
  "source_file": "sample_medical.pdf",
  "page_num": 1,
  "confidence": 0.85,
  "created_at": "2026-07-14T12:00:00"
}
```

## Contributing

To add new training samples:
1. Place PDF files in `samples/<category>/`
2. Run the Handwriting Trainer to create corrections
3. Export and commit the JSONL file

## License

Training data is licensed under the same terms as the parent repository.
Ensure you have rights to any uploaded documents before contributing.