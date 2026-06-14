# Continuous Improvement Pipeline
# أنبوب التحسين المستمر

> How corrections from Hugging Face Space flow back to improve the OCR system.

---

## Pipeline Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ 1. GT Import    │────▶│ 2. Benchmarks    │────▶│ 3. Trainer      │
│                 │     │                  │     │                 │
│ ABBYY/ReadIRIS  │     │ CER/WER/Medical  │     │ Streamlit UI    │
│ → Ground Truth  │     │ Term Accuracy    │     │ Ensemble OCR    │
│                 │     │                  │     │ Interactive Fix │
│ Repo:           │     │ Repo:            │     │ Repo:           │
│ medical-ocr-    │     │ medical-ocr-     │     │ medical-ocr-    │
│ ground-truth    │     │ benchmarks       │     │ trainer         │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                         │
                                                         │ corrections
                                                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ 6. Platform     │◀────│ 5. Benchmarks    │◀────│ 4. HF Space     │
│                 │     │ (Re-evaluate)    │     │                 │
│ omni-medical-   │     │                  │     │ Online Demo     │
│ suite           │     │ Baseline         │     │ User Corrections│
│                 │     │ Regression Check │     │ Quick Feedback  │
│ Full Pipeline   │     │                  │     │                 │
│ Production Use  │     │ Repo:            │     │ Repo:           │
│                 │     │ medical-ocr-     │     │ medical-ocr-    │
│                 │     │ benchmarks       │     │ trainer-hf      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │
        │ improved models/dictionaries
        ▼
┌─────────────────┐
│ 7. Training Hub │
│                 │
│ Bridge: HF ↔ GitHub
│ Continuous Model
│ Improvement     │
│                 │
│ Repo:           │
│ medical-ocr-    │
│ training-hub    │
└─────────────────┘
```

---

## Step-by-Step Flow

### Step 1: Import Ground Truth
**Repository:** [medical-ocr-ground-truth](https://github.com/DrAbdulmalek/medical-ocr-ground-truth)

```bash
# Import from ABBYY FineReader
python import_ground_truth.py abbyy_output.docx --output gt_page588.txt

# Import from ReadIRIS
python import_ground_truth.py readiris_output.rtf --output gt_readiris.txt

# Compare OCR with GT and generate correction dictionary
python gt_comparison_engine.py --gt gt_page588.txt --ocr ocr_output.txt \
    --generate-dict --output report.json
```

**Output:** Ground truth files, correction dictionaries, training pairs.

### Step 2: Establish Baselines
**Repository:** [medical-ocr-benchmarks](https://github.com/DrAbdulmalek/medical-ocr-benchmarks)

```bash
# Run benchmarks against current engines
medocr-bench --engines paddleocr,tesseract --check-ci

# Results saved to results/ with CER/WER/medical accuracy
```

**Output:** Baseline metrics for regression detection.

### Step 3: Collect Corrections
**Repository:** [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer)

```bash
streamlit run app.py
# 1. Upload medical documents
# 2. Run ensemble OCR (5 engines)
# 3. Review and correct errors
# 4. Export training data
```

**Output:** Corrected pairs, training datasets (JSONL/CSV/Parquet).

### Step 4: Gather User Feedback (HF Space)
**Hugging Face:** [DrAbdulmalek/medical-ocr-trainer](https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-trainer)

Users try the demo, upload documents, and make corrections.
These corrections are captured and can be bridged back to GitHub.

### Step 5: Training Hub Integration
**Repository:** [medical-ocr-training-hub](https://github.com/DrAbdulmalek/medical-ocr-training-hub)

```text
HF Space corrections → Training Hub → GitHub training data → Model improvement
```

The Training Hub acts as the bridge between online user feedback and offline training.

### Step 6: Re-evaluate
**Repository:** [medical-ocr-benchmarks](https://github.com/DrAbdulmalek/medical-ocr-benchmarks)

```bash
# Re-run benchmarks after improvement
medocr-bench --engines paddleocr --check-ci

# Compare against previous baselines
medocr-bench --compare-baseline results/baseline_v1.json
```

CI automatically detects regressions (≥5% degradation).

### Step 7: Deploy to Platform
**Repository:** [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)

```bash
# Update postprocessor dictionary
cp improved_dict.json omni-medical-suite/data/correction_dict.json

# Deploy
cd omni-medical-suite && make deploy
```

---

## Automation

### CI Pipeline (Automatic)

| Trigger | Action | Repository |
|---------|--------|------------|
| Push to `ground-truth` data files | Run GT validation → notify benchmarks | ground-truth |
| Weekly Monday 4AM | Full benchmark suite | benchmarks |
| PR to any repo | Quick benchmark check | benchmarks |
| Push to `postprocessor` | Publish to PyPI | postprocessor |
| Push to `suite` | Full CI (lint + test + build) | omni-medical-suite |

### Manual Steps

| Step | Frequency | Effort |
|------|-----------|--------|
| Import new GT data | Monthly | 30 min |
| Review HF Space corrections | Weekly | 15 min |
| Export training data from trainer | As needed | 5 min |
| Re-baseline after changes | Per release | 10 min |
| Deploy updated dictionaries | Per improvement | 5 min |

---

## Quality Gates

Before any release reaches the platform:

1. [ ] `medical-ocr-benchmarks` CI passes (no regression > 5%)
2. [ ] `medical-ocr-postprocessor` tests pass (37+ tests)
3 [ ] New dictionary entries validated against GT
4. [ ] No default credentials in `omni-medical-suite`
5. [ ] Audit event model checksums verified

---

## Repository Map

```
omni-medical-suite          ← Main Platform (production use)
├── medical-ocr-postprocessor ← Core correction library (pip install)
├── medical-handwriting-ocr   ← Production OCR (GPU/Lite modes)
├── medical-ocr-trainer       ← Data collection & correction
├── medical-ocr-trainer-hf    ← HF Space (demo only)
├── medical-ocr-benchmarks    ← Quality measurement
├── medical-ocr-ground-truth  ← Golden truth source
├── medical-ocr-training-hub  ← HF ↔ GitHub bridge
├── OmniFile_Processor        ← Legacy (read-only)
└── medical-doc-processor     ← Legacy (read-only)
```

---

> This pipeline creates a **closed loop**: GT → Measure → Correct → Train → Re-measure → Deploy
> 
> Part of the [Medical OCR Ecosystem](https://github.com/DrAbdulmalek/omni-medical-suite/blob/main/PORTFOLIO.md)
