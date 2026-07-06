# Medical OCR Ground Truth - Versioning and Release Notes

This document tracks all released versions of the Medical OCR Ground Truth dataset.

## Released Datasets

| Version | Type | Size | Date | CER (Test) | Notes |
|---------|------|------|------|------------|-------|
| v1.2 | Bilingual Medical | 5,000 | 2026-07-01 | 4.2% | Bilingual corpus (Arabic-English) |
| v1.1 | Handwritten Arabic | 2,000 | 2026-06-15 | 8.5% | Added handwritten support |
| v1.0 | Printed Arabic | 8,000 | 2026-06-01 | 2.8% | Initial printed dataset |

## Release Details

### v1.2 - Bilingual Medical Corpus (2026-07-01)

Type: Bilingual (Arabic-English)
Size: 5,000 pages
CER (Test): 4.2%

Added:
- Bilingual medical documents (Arabic-English parallel corpus)
- 5,000 new pages with dual-language annotations
- Medical domain classification for bilingual documents

Benchmarks:
- CER (Printed): 3.1%
- CER (Handwritten): 7.8%
- WER (Printed): 5.4%
- WER (Handwritten): 13.5%
- Medical Term Accuracy: 91.5%

### v1.1 - Handwritten Arabic (2026-06-15)

Type: Handwritten Arabic Medical Documents
Size: 2,000 pages
CER (Test): 8.5%

Added:
- Handwritten medical notes and prescriptions
- 2,000 pages of handwritten Arabic text
- Specialized annotation for handwriting recognition

Benchmarks:
- CER (Handwritten): 8.5%
- WER (Handwritten): 14.2%
- Medical Term Accuracy: 88.7%
- Processing Time: 1.2s/page

### v1.0 - Printed Arabic (2026-06-01)

Type: Printed Arabic Medical Documents
Size: 8,000 pages
CER (Test): 2.8%

Added:
- Initial release of Medical OCR Ground Truth dataset
- 8,000 pages of printed Arabic medical documents
- Comprehensive medical terminology coverage

Benchmarks:
- CER (Printed): 2.8%
- WER (Printed): 5.1%
- Medical Term Accuracy: 94.2%
- Processing Time: 0.45s/page

## Versioning Policy

We follow a modified semantic versioning for datasets:
- Major Version (X.0.0): Breaking changes, new data types, significant restructuring
- Minor Version (0.X.0): New data additions, backward-compatible changes
- Patch Version (0.0.X): Bug fixes, small improvements, metadata updates

## Upcoming Releases

### v1.3 - Expanded Bilingual (Planned for 2026-07-15)
- Additional 5,000 bilingual pages
- French and German medical documents
- Enhanced quality scoring

### v2.0 - Multi-Lingual Medical (Planned for 2026-08-01)
- Support for 10+ languages
- Advanced layout preservation
- Table and form extraction

## Migration Guide

To combine multiple versions:

from datasets import load_dataset

v1_0 = load_dataset("DrAbdulmalek/medical-ocr-ground-truth-v1.0")
v1_1 = load_dataset("DrAbdulmalek/medical-ocr-ground-truth-v1.1")
v1_2 = load_dataset("DrAbdulmalek/medical-ocr-ground-truth-v1.2")

combined = {
    "train": v1_0["train"] + v1_1["train"] + v1_2["train"],
    "validation": v1_0["validation"] + v1_1["validation"] + v1_2["validation"],
    "test": v1_0["test"] + v1_1["test"] + v1_2["test"]
}

## Support

For questions or issues with a specific version, please open an issue with the appropriate label.

## License

All versions of the Medical OCR Ground Truth dataset are licensed under the MIT License.
