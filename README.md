# Medical OCR Training Hub

![Release Pipeline](https://img.shields.io/badge/pipeline-release-green)

Welcome to the **Medical OCR Training Hub**. This repository serves as the vital strategic bridge within the `Omni-Medical-Suite` ecosystem. It provides a **training & release pipeline** that automates the continuous data loop between user-assisted corrections on Hugging Face Spaces and our production-ready training datasets on GitHub.

---

## 🚢 Release Pipeline

This repository includes a fully documented release pipeline that transforms raw training data into production-ready model artifacts with automated quality gates, benchmarking, and changelog generation.

📖 **See [RELEASE_PIPELINE.md](./RELEASE_PIPELINE.md) for the full pipeline documentation.**

---

## 🗺️ The Architecture & Data Loop

This hub orchestrates a continuous training & release pipeline to ensure our Medical OCR models improve over time based on real-world corrections, with automated benchmarks, readiness gates, and changelog management.

```mermaid
graph TD
    %% === Source Layer ===
    A[📄 Medical Scans / X-Rays / Prescriptions] --> B(🧠 Omni-Medical-Suite)
    B -->|Initial OCR Extraction| C{🤖 Multi-Engine OCR}
    C -->|Raw Text| D[⚕️ Doctor Correction via HF Space]

    %% === Ingestion Layer ===
    D -->|User Feedback + Images| E(🌉 Medical OCR Training Hub)
    E -->|1. Validate + Dedup + Arabic PII Scrub| F{🛡️ Quality Gate}

    %% === Storage Layer ===
    F -->|Clean Data| G[📚 medical-ocr-ground-truth]
    F -->|Rejected / PII-Flagged| H[🗑️ Quarantine + Audit Log]

    %% === Training Layer ===
    G -->|Trigger Pipeline| I[🏋️ medical-ocr-trainer / trainer-hf]
    I -->|Fine-tuned Model| J[📊 medical-ocr-benchmarks]

    %% === Deployment Layer ===
    J -->|Nightly Regression Check| K{✅ Accuracy > Threshold?}
    K -->|Yes| L[🚀 Deploy Updated Model to Omni-Medical-Suite]
    K -->|No| M[🚨 Alert + Trigger New Training Cycle]
    M --> I

    %% === Data Preparation Layer ===
    G -->|Clean Corpus| N[🔄 ai-fuel-engine + bilingual-extractor]
    N -->|Aligned TSV/CSV| O[🧠 Translation Model Training]

    %% Styles
    style B fill:#2f80ed,stroke:#333,stroke-width:2px,color:#fff
    style E fill:#27ae60,stroke:#333,stroke-width:2px,color:#fff
    style G fill:#f2994a,stroke:#333,stroke-width:2px,color:#fff
    style I fill:#9b59b6,stroke:#333,stroke-width:2px,color:#fff
    style J fill:#e74c3c,stroke:#333,stroke-width:2px,color:#fff
    style L fill:#2ecc71,stroke:#333,stroke-width:2px,color:#fff
    style M fill:#e74c3c,stroke:#333,stroke-width:2px,color:#fff
```

### How the Bridging Loop Works

1. **Inbound from HF:** Corrections made by users or annotators on the Hugging Face correction Space are packaged (JSON metadata + scanned images).
2. **Ingestion & Validation:** This hub ingests the packets, runs schema validation, and ensures adherence to our DATASETS_POLICY.md.
3. **Ground Truth Enrichment:** Verified data is automatically pushed into the `medical-ocr-ground-truth` repository as the Single Source of Truth (SSOT).
4. **Benchmark Verification:** The updated ground truth triggers nightly regression benchmarks to guarantee that retrained models maintain high baseline accuracy.

---

## 🛠️ Repository Structure

```
medical-ocr-training-hub/
├── src/
│   └── ingestion/
│       ├── ingest_and_clean.py      # v1.1 — Basic ingestion (legacy)
│       └── ingest_and_clean_v2.py   # v2.0 — Arabic PII + Dedup + TSV output
├── tests/
│       └── test_pipeline_v2.py      # 24 tests for v2 pipeline
├── config.yaml                    # Pipeline configuration
├── setup.sh                       # Environment setup
├── training_data/                 # Local training data staging
├── docs/                          # Documentation
├── models/                        # Model artifacts
├── scripts/                       # Utility scripts
└── README.md
```

---

## 🔒 Governance & Security

Because this pipeline processes medical text and handwriting documents, strict data governance is applied:

- All inbound data must strip potential PII (Personally Identifiable Information) before hitting the public ground truth layers.
- Contribution validation thresholds must meet a minimum confidence score defined in our nightly benchmarks.
- Part of the [Omni-Medical-Suite](https://github.com/DrAbdulmalek/omni-medical-suite) ecosystem.

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/DrAbdulmalek/medical-ocr-training-hub.git
cd medical-ocr-training-hub

# Install dependencies
pip install requests

```bash
# Run v2 pipeline (Arabic PII + Dedup + TSV — recommended)
python src/ingestion/ingest_and_clean_v2.py

# Run v1 pipeline (legacy, English-only PII)
python src/ingestion/ingest_and_clean.py

# Run tests
pytest tests/test_pipeline_v2.py -v
```

---

## 📥 Data Flow

| Stage | Input | Output | Validation |
|-------|-------|--------|------------|
| **Ingestion** | HF Space corrections (JSON + images) | Raw data packets | Schema check |
| **PII Scrubbing** | Raw text fields | Redacted text | Arabic + English patterns (Syrian/KSA/UAE phones, Arabic-numeral dates, IDs, emails) |
| **Deduplication** | Valid packets | Unique records | MD5 hash-based dedup |
| **TSV Export** | Clean records | `aligned_corpus.tsv` | Sentence alignment for translation model training |
| **Quality Gate** | Scrubbed packets | Clean data | Minimum text length, required fields |
| **Ground Truth** | Clean data | Verified datasets | DATASETS_POLICY.md compliance |

---

## 🧪 Testing

The v2 pipeline includes **24 automated tests** covering:
- PII scrubbing (Syrian, Saudi, UAE phones; Gregorian & Hijri dates; Arabic numerals; emails; IDs)
- Hash-based deduplication (case-insensitive, whitespace-normalized)
- Validation (missing fields, short text, duplicate detection)
- TSV output (header, row count, PII absence in output)
- End-to-end pipeline (5 mock records → 4 passed, 1 duplicate, PII verified)

```bash
pytest tests/test_pipeline_v2.py -v
# Expected: 24 passed
```

---

## 📄 License

MIT License — Part of the Omni-Medical-Suite ecosystem by [DrAbdulmalek](https://github.com/DrAbdulmalek).