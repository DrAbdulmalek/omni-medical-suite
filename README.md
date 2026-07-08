<p align="center">
  <img src="https://img.shields.io/badge/Platform-OCR%20%2B%20NLP%20%2B%20AI-6C63FF?style=for-the-badge" />
</p>

<h1 align="center">
  <img width="32" src="https://img.icons8.com/color/96/hospital-3.png" style="vertical-align: middle"/>
  Omni Medical Suite
</h1>

<p align="center">
  <strong>Arabic Medical Document Intelligence Platform</strong><br/>
  <sup>OCR &middot; Handwriting Recognition &middot; Spell Correction &middot; NER &middot; Training</sup>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Packages-31-4B8BBE?style=flat-square" />
  <img src="https://img.shields.io/badge/Apps-5-2ECC71?style=flat-square" />
  <img src="https://img.shields.io/badge/Tests-50%2B-FF6B6B?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-3C873A?style=flat-square" />
  <a href="https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr"><img src="https://img.shields.io/badge/HF%20Space-Live-FFA500?style=flat-square&logo=huggingface" /></a>
</p>

<p align="center">
  <a href="https://github.com/DrAbdulmalek/omni-medical-suite"><b>GitHub</b></a> &middot;
  <a href="https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr"><b>Demo</b></a> &middot;
  <a href="docs/ARCHITECTURE.md"><b>Architecture</b></a> &middot;
  <a href="ROADMAP.md"><b>Roadmap</b></a> &middot;
  <a href="CONTRIBUTING.md"><b>Contributing</b></a>
</p>

---

## What It Does

Omni Medical Suite extracts, corrects, and structures Arabic text from medical documents and handwritten prescriptions. It combines **4 OCR engines** with AI-powered spell correction and medical context protection.

```
  Prescription Image
         |
    [Scanner Fixer]         deskew, crop, CLAHE, denoise
         |
    [OCR Ensemble]          PaddleOCR + Tesseract + EasyOCR + TrOCR
         |
    [Arabic NLP]            RTL handling, mixed-language detection
         |
    [Spell Checker]         Dictionary + Jais LLM + medical vocabulary protection
         |
    [NER Extractor]         Drug names, dosages, dates, diagnoses
         |
    Structured Output       JSON / CSV / XLSX / PDF
```

## Key Features

| Feature | Description |
|---------|-------------|
| **4-Engine OCR Ensemble** | PaddleOCR, Tesseract, EasyOCR, TrOCR — fused with confidence voting |
| **Arabic Handwriting Recognition** | Custom TrOCR fine-tuned on medical handwriting |
| **Medical Spell Checker** | HybridSpellChecker protects medical terms from false corrections |
| **Jais LLM Proofreading** | AI-powered Arabic proofreading via Jais model |
| **Image Preprocessing** | Deskew, CLAHE contrast, line removal, perspective correction |
| **Named Entity Recognition** | Extracts drugs, dosages, dates, and diagnoses |
| **HITL Feedback Loop** | Human corrections feed back into training data |
| **Multi-Page PDF + Tables** | Batch processing with table extraction |
| **Desktop + Web + API** | PyQt6 desktop app, Gradio web UI, FastAPI REST API |
| **Continuous Retraining** | Weekly model improvement from accumulated corrections |

## Quick Start

### Option 1: Gradio Web UI
```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
pip install -r requirements.txt
python app/gradio_full_hitl.py
```
Open `http://localhost:7860`

### Option 2: Desktop App (PyQt6)
```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
pip install PyQt6 pytesseract  # PaddleOCR/EasyOCR optional
python desktop/omni_medical_desktop.py
```

Features:
- **OCR Scanner** tab — upload image, run Tesseract/PaddleOCR/EasyOCR/Ensemble, view results
- **Jais LLM Proofread** checkbox — enable AI proofreading when GPU is available
- **Medical NER** panel — extracted entities (drugs, dosages, diagnoses) displayed after Jais run
- **Text Editor** tab — RTL Arabic editor with Find & Replace
- **Dictionary** tab — live-search medical terms from `medical_terms.json`
- **Settings** tab — engine selection, language, confidence threshold, dark mode

### Option 3: Docker (Full Stack)
```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
cp .env.example .env   # Edit with your settings
docker-compose up -d
```

### Option 4: Docker Lite (OCR Only)
```bash
docker-compose -f docker-compose.lite.yml up -d
```

### Live Demo
**[HuggingFace Space](https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr)** — No installation needed.

## Monorepo Structure

```
omni-medical-suite/
├── app/                         # Main Gradio HITL application
├── src/                         # Core library
│   ├── ocr/                     #   OCR engine routing & ensemble
│   ├── ner/                     #   Named Entity Recognition (Jais)
│   ├── llm/                     #   LLM integration (Jais, Ollama)
│   ├── layout/                  #   Document layout analysis
│   └── benchmarks/              #   Benchmarking utilities
├── desktop/                     # PyQt6 desktop application
├── apps/                        # Standalone applications
│   ├── ocr-pipeline/            #   Full end-to-end pipeline
│   ├── handwriting-demo/        #   Handwriting recognition demo
│   ├── ocr-demo/                #   Multi-engine comparison
│   ├── trainer-ui/              #   Model training interface
│   └── collector/               #   HITL data collector
├── packages/                    # Reusable Python packages (31)
│   ├── scanner_fixer/           #   Pre-OCR image normalization
│   ├── vision/                  #   Computer vision & HTR
│   ├── nlp/                     #   Spell checking, translation, RTL
│   ├── medical/                 #   Medical dictionaries & domain logic
│   ├── core/                    #   Shared utilities, DB, auth
│   ├── ocr_postprocess/         #   OCR post-processing & fusion
│   ├── omnifile/                #   File processing & export
│   ├── training/                #   Model training framework
│   └── ...                      #   ai-fuel, bilingual, export, etc.
├── config/                      # Model configs, Prometheus, Grafana, Nginx
├── tests/                       # 40+ test files
├── docs/                        # Architecture, guides, ADRs
├── hf-space/                    # HuggingFace Spaces deployment
├── infra/                       # Docker & Kubernetes configs
└── .github/workflows/           # CI/CD pipelines
```

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **OCR** | PaddleOCR, Tesseract, EasyOCR, TrOCR, Surya |
| **NLP / LLM** | Transformers, Jais, Custom HybridSpellChecker |
| **Vision** | OpenCV, CLAHE, Scikit-image |
| **Backend** | Python 3.10+, FastAPI, Celery, PostgreSQL |
| **Frontend** | Gradio 4.x, PyQt6, Next.js |
| **Infrastructure** | Docker, Redis, Qdrant, Nginx |
| **Monitoring** | Prometheus, Grafana, Tempo (tracing) |
| **CI/CD** | GitHub Actions, HuggingFace Spaces |
| **Deployment** | Docker Compose, Kubernetes, HF Spaces |

## Configuration

Copy the example environment file and customize:
```bash
cp .env.example .env
```

Key variables:
| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | PostgreSQL password | (required) |
| `SECRET_KEY` | FastAPI secret key | (required) |
| `ENABLE_LLM` | Enable Jais proofreader | `false` |
| `HF_TOKEN` | HuggingFace token for dataset upload | (optional) |

See [`.env.example`](.env.example) for the full list.

## Documentation

| Document | Content |
|----------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, data flow, package map |
| [PIPELINE.md](PIPELINE.md) | Full OCR processing pipeline |
| [MODES.md](MODES.md) | Operation modes (lite, standard, full) |
| [DEPLOY.md](DEPLOY.md) | Deployment guide (Docker, K8s, HF) |
| [MODEL_CARD.md](MODEL_CARD.md) | Model card with benchmarks |
| [ROADMAP.md](ROADMAP.md) | Development roadmap & milestones |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guidelines |
| [CLEANUP_LOG.md](CLEANUP_LOG.md) | Repository consolidation history |

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/ --ignore=tests/loadtest -q

# Run linter
ruff check src/ packages/ app/

# Local development server
make dev
```

## Roadmap

- [x] **v1.0** — Monorepo consolidation (6 repos merged)
- [x] **v1.1** — CI/CD + Docker + HF Space deployment
- [x] **v1.2** — Testing infrastructure + ruff + mypy + PyQt6 desktop app
- [ ] **v1.3** — Multi-page PDF + table extraction
- [ ] **v1.4** — Weekly auto-retraining pipeline
- [ ] **v2.0** — Real-time collaboration + RBAC + audit log

See [ROADMAP.md](ROADMAP.md) for details.

## Requirements

- Python 3.10+
- 8 GB RAM minimum (16 GB recommended)
- CUDA optional (GPU acceleration for TrOCR / Jais)
- Docker + Docker Compose (for containerized deployment)

## License

[MIT](LICENSE) &copy; 2026 Dr. Abdulmalek

---

<p align="center">
  <sub>Built with passion for Arabic medical NLP</sub>
</p>