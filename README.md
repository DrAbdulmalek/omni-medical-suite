<p align="center">
  <h1>Omni Medical Suite</h1>
  <strong>Unified Medical OCR Platform</strong><br/>
  <sub>Next.js + FastAPI + Gradio + Qdrant + Redis</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python" />
  <img src="https://img.shields.io/badge/Gradio-5.x-orange?style=flat-square&logo=gradio" />
  <img src="https://img.shields.io/badge/Arabic-RTL-blueviolet?style=flat-square" />
  <img src="https://img.shields.io/badge/Packages-31-informational?style=flat-square" />
  <img src="https://img.shields.io/badge/Apps-5-success?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
  <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square" />
</p>

<p align="center">
  <a href="#-features">Features</a> &middot;
  <a href="#-quick-start">Quick Start</a> &middot;
  <a href="#-structure">Structure</a> &middot;
  <a href="#-deployment">Deployment</a> &middot;
  <a href="#-tech-stack">Tech Stack</a>
</p>

---

# Omni Medical Suite

**The Comprehensive Arabic Medical Platform** — A monorepo for medical document processing and handwritten prescription recognition.

## Features

- **Advanced OCR**: 4 engines + Ensemble fusion
- **Intelligent Correction**: HybridSpellChecker + Jais LLM proofreading
- **Image Processing**: deskew, CLAHE, line removal, perspective correction
- **HITL**: Gradio + PyQt6 human-in-the-loop interfaces
- **Training**: Custom TrOCR fine-tuning + Ground Truth pipeline
- **Deployment**: Docker + HF Spaces + Kubernetes

## Quick Start

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
pip install -r requirements.txt
python app/gradio_hitl.py
```

Then open `http://localhost:7860` in your browser.

## Structure

```
omni-medical-suite/
├── apps/              — Applications (Gradio, API, Desktop)
│   ├── collector/         # HITL data collector
│   ├── handwriting-demo/  # Handwriting OCR demo
│   ├── ocr-demo/          # Multi-engine OCR demo
│   ├── ocr-pipeline/      # Full OCR pipeline
│   └── trainer-ui/        # Model training UI
├── packages/           — Reusable Python packages (31)
│   ├── ai-fuel/           # AI content engine
│   ├── bilingual/         # Arabic/English text extractor
│   ├── core/              # Shared utilities
│   ├── doc-processor/     # Document processing
│   ├── handwriting/       # Handwriting recognition
│   ├── medical/           # Medical domain logic
│   ├── nlp/               # NLP correction & spell check
│   ├── ocr_postprocess/   # OCR post-processing
│   ├── omnifile/          # File processing & export
│   ├── scanner_fixer/     # Pre-OCR image normalization
│   ├── training/          # Model training framework
│   └── vision/            # Computer vision utilities
├── src/                — Core library (OCR, NER, LLM, Layout)
├── app/                — Main Gradio application
├── services/           — Backend services
├── infra/              — Docker + k8s configurations
├── config/             — Model configs, Prometheus, Grafana
├── tests/              — Unit & integration tests (40+ files)
├── docs/               — Full documentation
├── hf-space/           — HuggingFace Spaces deployment
└── .github/workflows/  — CI/CD pipelines
```

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **OCR** | PaddleOCR, Tesseract, EasyOCR, TrOCR, Surya |
| **NLP** | Transformers, Jais LLM, Custom Spell Checker |
| **Vision** | OpenCV, CLAHE, Deskew, Line Removal |
| **Backend** | Python, FastAPI, Celery, PostgreSQL, Redis |
| **Frontend** | Next.js, Gradio, PyQt6 |
| **Vector DB** | Qdrant |
| **Monitoring** | Prometheus, Grafana, Tempo |
| **Deployment** | Docker, Kubernetes, HuggingFace Spaces |

## Deployment

### Docker (Recommended)
```bash
docker-compose up -d
```

### Docker Lite (OCR only, no monitoring stack)
```bash
docker-compose -f docker-compose.lite.yml up -d
```

### HuggingFace Spaces
```bash
cd hf-space
docker build -t medical-ocr .
```

### Local Development
```bash
make dev
```

## Documentation

| File | Content |
|------|---------|
| `docs/ARCHITECTURE.md` | System architecture & data flow |
| `PIPELINE.md` | Full processing pipeline |
| `MODES.md` | Operation modes |
| `DEPLOY.md` | Deployment guide |
| `CONTRIBUTING.md` | Contribution guidelines |
| `MODEL_CARD.md` | Model card |
| `CLEANUP_LOG.md` | Repository consolidation log |

## Requirements

- Python 3.10+
- CUDA (optional, for GPU acceleration)
- 8+ GB RAM (16+ GB recommended for large models)

## License

This project is licensed under the [MIT](LICENSE) license.

---

## Migrated Repositories (2026-07-07)

| Original Repository | New Location | Status |
|---------------------|--------------|--------|
| omni-medical-ocr-pipeline | apps/ocr-pipeline/ | Merged |
| OmniFile_Processor | packages/omnifile/ | Merged |
| bilingual-extractor | packages/bilingual/ | Merged |
| ai-fuel-engine | packages/ai-fuel/ | Merged |
| medical-doc-processor | packages/doc-processor/ | Merged |
| handwriting-ocr | packages/handwriting/ | Merged |

Archive: [medical-ocr-archived](https://github.com/DrAbdulmalek/medical-ocr-archived)