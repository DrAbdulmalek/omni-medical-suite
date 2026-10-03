# Versioned Datasets Policy
# سياسة إدارة البيانات الأساس المُنسَّقة

> This document establishes `medical-ocr-ground-truth` as the **official golden truth source**
> for the entire Medical OCR Ecosystem.

---

## 1. Role & Authority

`medical-ocr-ground-truth` is the **single source of truth** for:
- Golden test datasets used by `medical-ocr-benchmarks`
- Training pairs consumed by `medical-ocr-trainer`
- Correction dictionaries fed into `medical-ocr-postprocessor`
- Baseline references for `omni-medical-suite` evaluation

No other repository may define canonical ground truth without referencing this repo.

## 2. Dataset Versioning Scheme

All datasets follow semantic versioning: `v{MAJOR}.{MINOR}.{PATCH}`

| Component | Bumped When |
|-----------|-------------|
| MAJOR | Structural change (new fields, format change, re-labeling) |
| MINOR | New data added (new pages, new sources, new specialties) |
| PATCH | Bug fixes in existing data (typos, metadata corrections) |

### Version Directory Structure

```
data/
├── v1.0.0/
│   ├── manifest.json          # Dataset manifest with metadata
│   ├── golden/                # Ground truth text files
│   │   ├── cardiology/
│   │   ├── radiology/
│   │   ├── prescriptions/
│   │   └── mixed_rtl_ltr/    # Mixed Arabic/English cases
│   ├── ocr_outputs/           # Raw OCR outputs for comparison
│   └── reports/               # Benchmark reports at this version
├── v1.1.0/
│   └── ...
└── LATEST -> v1.1.0          # Symlink to current version
```

## 3. Manifest Format

Every dataset version MUST include a `manifest.json`:

```json
{
  "version": "1.1.0",
  "created_at": "2026-06-11T00:00:00Z",
  "created_by": "Dr. Abdulmalek",
  "description": "Arabic medical OCR ground truth with 50+ cases",
  "sources": [
    {"name": "ABBYY FineReader", "pages": 20, "format": "docx"},
    {"name": "ReadIRIS", "pages": 15, "format": "rtf"},
    {"name": "Manual", "pages": 10, "format": "txt"}
  ],
  "statistics": {
    "total_pages": 45,
    "total_lines": 1250,
    "languages": ["arabic", "english", "mixed"],
    "specialties": ["cardiology", "radiology", "orthopedics", "prescriptions"],
    "rtl_ltr_mixed_lines": 180
  },
  "upstream_consumers": [
    "medical-ocr-benchmarks",
    "medical-ocr-trainer",
    "medical-ocr-postprocessor",
    "omni-medical-suite"
  ]
}
```

## 4. Quality Gates

Before any dataset version is released, it MUST pass these quality gates:

### 4.1 Completeness Gate
- [ ] All test cases have non-empty `ground_truth` field
- [ ] Each case has `source`, `language`, `specialty` metadata
- [ ] Mixed RTL/LTR cases are explicitly tagged

### 4.2 Consistency Gate
- [ ] No duplicate test case IDs within a version
- [ ] File encoding is UTF-8 with NFC normalization
- [ ] Arabic text passes `normalize_arabic()` without data loss

### 4.3 Medical Accuracy Gate
- [ ] At least 3 native Arabic medical terms per specialty
- [ ] Drug names include dosage information
- [ ] Lab values include units and reference ranges

### 4.4 Integration Gate
- [ ] Dataset loads in `medical-ocr-benchmarks` without errors
- [ ] `gt_comparison_engine.py --gt <dataset> --ocr <baseline>` produces valid report
- [ ] Exported dictionary is valid JSON with > 0 entries

## 5. Release Process

1. **Prepare**: Add/modify data in a new `vX.Y.Z/` directory
2. **Validate**: Run `python validate_dataset.py --version X.Y.Z`
3. **Test Integration**: Run benchmarks against the new dataset
4. **Tag**: `git tag dataset-vX.Y.Z -m "Dataset v1.1.0: description"`
5. **Push**: `git push origin dataset-vX.Y.Z`
6. **Notify**: Update `PORTFOLIO.md` in `omni-medical-suite` with new dataset version

## 6. Data Retention Policy

| Data Type | Retention | Reason |
|-----------|-----------|--------|
| Released dataset versions | Indefinite | Reproducibility |
| Working drafts (unversioned) | 90 days | Cleanup |
| Benchmark reports | Indefinite | Historical tracking |
| Correction dictionaries | Per version | Tied to dataset version |
| Training pairs | Per version | Tied to dataset version |

## 7. Integration Points

### 7.1 With medical-ocr-benchmarks
```bash
# Benchmarks consume ground truth via golden dataset loader
python -m benchmarks.runner --data-dir /path/to/ground-truth/data/v1.1.0/golden/
```

### 7.2 With medical-ocr-trainer
```bash
# Trainer imports training pairs from ground truth exports
python export_training.py --input ground-truth/data/v1.1.0/ --format jsonl
```

### 7.3 With medical-ocr-postprocessor
```bash
# Postprocessor loads correction dictionaries
cp ground-truth/data/v1.1.0/correction_dict.json postprocessor/data/
```

## 8. Table Extraction & Layout Benchmark Data

As of v1.1.0, datasets SHOULD include structured table extraction cases:
- Medical lab reports with multi-row tables
- Prescription tables with drug/dosage/frequency columns
- Vital signs tables with temporal data
- Mixed RTL/LTR table headers (Arabic column names, English values)

Each table case must include:
- Original image or reference
- Ground truth in both plain text and structured JSON
- Table structure metadata (rows, columns, merged cells)

---

**Version:** 1.0.0  
**Last Updated:** 2026-06-11  
**Owner:** Dr. Abdulmalek