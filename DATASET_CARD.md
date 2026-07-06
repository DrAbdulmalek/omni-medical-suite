---
license: mit
datasets:
- DrAbdulmalek/medical-ocr-ground-truth-v1.0
language:
- en
- ar
tags:
- medical
- ocr
- arabic
- ground-truth
- healthcare
- bilingual
---

# Medical OCR Ground Truth Dataset v1.0

## Dataset Details

Medical OCR Ground Truth Dataset v1.0 is a high-quality, annotated dataset for training and evaluating OCR systems on Arabic and English medical documents. The dataset contains 10,000 pages of medical documents with ground truth transcriptions.

- Created by: Dr. Abdulmalek Tamer Al-Husseini
- Organization: Independent Research
- License: MIT
- Language support: English, Arabic (primary)
- Domain: Medical documents, prescriptions, reports
- Total size: 10,000 pages

## Dataset Structure

The dataset is organized as follows:

medical-ocr-ground-truth-v1.0/
├── train/
│   ├── images/
│   └── labels.jsonl
├── validation/
│   ├── images/
│   └── labels.jsonl
├── test/
│   ├── images/
│   └── labels.jsonl
└── dataset_card.md

## Data Instances

Each data instance consists of:

Field | Type | Description
------|------|-------------
id | string | Unique document identifier
image | string | Path to the image file
text | string | Ground truth transcription
language | string | Document language (en, ar, en-ar)
domain | string | Medical specialty (cardiology, neurology, etc.)
source | string | Source of the document (ABBYY, ReadIRIS, etc.)
quality_score | float | Quality score (0.0-1.0)
page_number | int | Page number in the document
document_type | string | Type of document (prescription, report, etc.)

## Dataset Splits

Split | Size | Percentage | Use
-----|------|------------|-----
Train | 8,000 | 80% | Training
Validation | 1,000 | 10% | Validation
Test | 1,000 | 10% | Testing

## Dataset Versions

Version | Type | Size | Date | CER (Test)
--------|------|------|------|------------
v1.0 | Printed Arabic | 8,000 | 2026-06-01 | 2.8%
v1.1 | Handwritten Arabic | 2,000 | 2026-06-15 | 8.5%
v1.2 | Bilingual Medical | 5,000 | 2026-07-01 | 4.2%

## Data Sources

The dataset includes documents from multiple sources:
- ABBYY FineReader: 4,000 pages (40%)
- ReadIRIS: 3,000 pages (30%)
- PDF Grabber: 2,000 pages (20%)
- Manual Annotation: 1,000 pages (10%)

## Medical Domain Coverage

The dataset covers 20+ medical specialties including:
- Cardiology
- Neurology
- Pediatrics
- Surgery
- Radiology
- Oncology
- Endocrinology
- Gastroenterology
- Pulmonology
- Nephrology

## Performance on This Dataset

Model | CER (Printed) | CER (Handwritten) | Medical Term Accuracy
------|---------------|-------------------|----------------------
Tesseract | 5.2% | 12.8% | 89.5%
EasyOCR | 3.8% | 9.5% | 92.1%
Ensemble v1.0 | 2.8% | 8.5% | 94.2%

## Usage

### Loading the Dataset

from datasets import load_dataset

# Load the full dataset
dataset = load_dataset("DrAbdulmalek/medical-ocr-ground-truth-v1.0")

# Access splits
train = dataset["train"]
validation = dataset["validation"]
test = dataset["test"]

# Get a single example
example = train[0]
print(example["text"])

## Ethical Considerations

- Privacy: All documents have been anonymized to remove personal information
- Consent: Documents were collected with appropriate consent where required
- Compliance: Dataset complies with relevant data protection regulations
- Bias: Dataset has been reviewed to minimize bias across different medical specialties

## Citation

@misc{medical-ocr-ground-truth-v1.0,
  author = {Dr. Abdulmalek Tamer Al-Husseini},
  title = {Medical OCR Ground Truth Dataset v1.0},
  year = {2026},
  howpublished = {https://huggingface.co/datasets/DrAbdulmalek/medical-ocr-ground-truth-v1.0},
  note = {Accessed: 2026-06-28}
}

## Version History

Version | Date | Description
--------|------|-------------
v1.0 | 2026-06-01 | Initial release - Printed Arabic
v1.1 | 2026-06-15 | Added Handwritten Arabic
v1.2 | 2026-07-01 | Added Bilingual Medical Corpus

## Contact

- GitHub: https://github.com/DrAbdulmalek
- Hugging Face: https://huggingface.co/DrAbdulmalek
- Email: contact@dr-abdulmalek.dev
