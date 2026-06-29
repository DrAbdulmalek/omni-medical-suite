# Architectural Portfolio: OmniMedical Suite

Welcome to the technical portfolio of the **OmniMedical Suite** ecosystem. This document outlines the core architecture, decision rules, and system health metrics.

---

## Core Architecture

The suite is built as a modular, data-driven network with specialized repositories:

| Layer | Repository | Primary Responsibility |
|-------|------------|------------------------|
| **Preprocessing (MANDATORY)** | [scanner-fixer](https://github.com/DrAbdulmalek/scanner-fixer) | **Required** first step — skew detection, auto-crop, noise reduction, scan normalization before OCR |
| **Orchestration** | [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) | Pipeline orchestration, API endpoints, core logic |
| **Data** | [medical-ocr-ground-truth](https://github.com/DrAbdulmalek/medical-ocr-ground-truth) | Single source of truth for verified datasets |
| **Training** | [medical-ocr-training-hub](https://github.com/DrAbdulmalek/medical-ocr-training-hub) | Data ingestion, validation, PII scrubbing |
| **Learning** | [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer) | Human-in-the-loop correction, ensemble collection |
| **Evaluation** | [medical-ocr-benchmarks](https://github.com/DrAbdulmalek/medical-ocr-benchmarks) | Nightly regression tests, quality gates |
| **Deployment** | [HF Spaces](https://huggingface.co/DrAbdulmalek) | Live demos and user correction interfaces |

---

## System Data Flow

> **⚠️ Critical**: Every medical image enters the pipeline through **Scanner Fixer** (green node below). This preprocessing step is **mandatory** — images that bypass it will suffer 40-50% higher CER and must be rejected at the Resolution Gate.

```mermaid
graph LR
    A[Medical Scans] --> B[Scanner Fixer (MANDATORY)]
    B --> C[OmniMedical Suite]
    C --> D{OCR Engine}
    D -->|User Corrections| E[Training Hub]
    E -->|Validated Data| F[Ground Truth]
    F -->|Trigger| G[Benchmarks]
    G -->|Threshold Check| H{Pass?}
    H -->|Yes| I[Deploy to Production]
    H -->|No| J[Retrain Model]
    J --> D

    style B fill:#4caf50,stroke:#2e7d32,stroke-width:2px,color:#fff
    style C fill:#2196f3,stroke:#1565c0,stroke-width:2px,color:#fff
    style F fill:#ff9800,stroke:#e65100,stroke-width:2px,color:#fff
    style H fill:#ff5722,stroke:#bf360c,stroke-width:2px,color:#fff
```

---

## Decision Rules (5 Core Rules)

These rules govern all data processing and model updates:

1. **Resolution Gate**: Images below 150 DPI are auto-rejected to prevent OCR degradation.

2. **Mandatory Preprocessing**: ALL scanned images MUST pass through [Scanner Fixer](https://github.com/DrAbdulmalek/scanner-fixer) for skew correction, auto-crop, and noise reduction before OCR processing. This is a required step — not optional. Skipping it increases CER by 40-50% on printed text.

3. **PII Redaction**: All patient identifiers (names, phones, dates) are automatically redacted before storage using a hybrid Regex + CamelBERT NER pipeline.

4. **CER Threshold**: Character Error Rate must stay below 5% for printed text and 12% for handwritten text. Benchmarks run nightly and trigger retraining on regression.

5. **Nightly Regression**: Every model update must pass baseline benchmarks before merging to production. A/B testing compares new vs current model on a holdout set.

---

## System Health Metrics

| Metric | Target | Current Status |
|--------|--------|----------------|
| **Printed Text CER** | < 5% | Active Monitoring |
| **Handwritten CER** | < 12% | Active Monitoring |
| **Preprocessing Impact** | ~40-50% CER reduction | Measured via benchmarks |
| **Data Ingestion Speed** | < 1.5s per page | Automated |
| **PII Redaction Accuracy** | 100% | Enforced (Hybrid Scrubber) |
| **Image Quality Gate** | >= 800x600 px | Enforced |

---

## Security & Governance

- **No Hardcoded Secrets**: All tokens injected via environment variables
- **Automated Auditing**: Daily pipeline reports generated automatically
- **Privacy First**: Strict PII redaction at code level (Hybrid Regex + CamelBERT NER)
- **Compliance**: HIPAA/GDPR aligned data handling

---

## Quick Start

```bash
# Clone the core repository
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite

# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python main.py
```

---

## Ecosystem Documentation

- **Main Platform**: [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)
- **Pre-OCR Normalization (MANDATORY)**: [scanner-fixer](https://github.com/DrAbdulmalek/scanner-fixer) — required first step for all medical images
- **Ground Truth**: [medical-ocr-ground-truth](https://github.com/DrAbdulmalek/medical-ocr-ground-truth)
- **Training Hub**: [medical-ocr-training-hub](https://github.com/DrAbdulmalek/medical-ocr-training-hub)
- **OCR Trainer**: [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer)
- **Benchmarks**: [medical-ocr-benchmarks](https://github.com/DrAbdulmalek/medical-ocr-benchmarks)

*Maintained with precision and care by [DrAbdulmalek](https://github.com/DrAbdulmalek).*