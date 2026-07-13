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
  <a href="docs/ROADMAP.md"><b>Roadmap</b></a> &middot;
  <a href="CONTRIBUTING.md"><b>Contributing</b></a>
</p>

---

## What It Does

Omni Medical Suite extracts, corrects, and structures Arabic text from medical documents and handwritten prescriptions. It now combines a **routed multi-engine OCR stack** with AI-powered spell correction, field-aware deduplication, semantic search, and medical context protection.

```
  Prescription Image
         |
    [Scanner Fixer]         deskew, crop, CLAHE, denoise
         |
    [OCR Router]            EasyOCR + PaddleOCR + Tesseract + TrOCR + QARI + Nougat + Qwen handwritten OCR
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
| **Routed OCR Stack** | EngineRouter chooses among EasyOCR, PaddleOCR, Tesseract, TrOCR, QARI, Nougat, and Arabic-handwritten-OCR (Qwen) |
| **Arabic Handwriting Recognition** | Qwen handwritten OCR first, with TrOCR / QARI fallback |
| **Medical Spell Checker** | HybridSpellChecker protects medical terms from false corrections |
| **Jais LLM Proofreading** | AI-powered Arabic proofreading via Jais model |
| **Image Preprocessing** | Deskew, CLAHE contrast, line removal, perspective correction |
| **Named Entity Recognition** | Extracts drugs, dosages, dates, and diagnoses |
| **Advanced Review App** | Gradio app with Compare + Search + Review tabs |
| **Field-Aware Deduplication** | Patient-sensitive weighting prevents same-template / different-patient false positives |
| **HITL Feedback Loop** | Human corrections feed back into training data |
| **Multi-Page PDF + Tables** | Batch processing with table extraction |
| **Desktop + Web + API** | PyQt6 desktop app, Gradio web UI, FastAPI REST API |
| **Continuous Retraining** | Weekly model improvement from accumulated corrections |

## Quick Start

### Option 1: Official Gradio HITL UI
```bash
git clone --recursive https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
# If you cloned without --recursive:
# git submodule update --init
pip install -r requirements/gradio.txt
python app/gradio_full_hitl.py
```
Open `http://localhost:7860`

### Option 1b: Experimental Review UI (Compare/Search/Review tabs)
```bash
python app/advanced_review_app.py
```
> **Note:** This is an experimental app. It does not yet support image upload, Jais proofreading, HF Dataset save, medical translation, or dictionary update. Use `gradio_full_hitl.py` for production.

### Option 2: Desktop App (PyQt6)
```bash
git clone --recursive https://github.com/DrAbdulmalek/omni-medical-suite.git
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
git clone --recursive https://github.com/DrAbdulmalek/omni-medical-suite.git
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
├── app/                         # Gradio review applications
├── src/                         # Core library
│   ├── ocr/                     #   OCR engine routing, RTL fixing, extraction, dedup
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
| [docs/PIPELINE.md](docs/PIPELINE.md) | Full OCR processing pipeline |
| [docs/MODES.md](docs/MODES.md) | Operation modes (lite, standard, full) |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deployment guide (Docker, K8s, HF) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Development roadmap & milestones |
| [docs/ROADMAP_2026_Q3.md](docs/ROADMAP_2026_Q3.md) | July 2026 implementation plan for routing, review UI, and dedup |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Version changelog & repository history |

## Deployment

### Architecture Overview

```
                  ┌─────────────────────┐
                  │   GitHub (main)     │
                  └────────┬────────────┘
                           │ push (paths filter)
                  ┌────────▼────────────┐
                  │ GitHub Actions       │
                  │ deploy-to-hf.yml    │
                  └────────┬────────────┘
                           │ git push
                  ┌────────▼────────────┐
                  │ HF Spaces           │
                  │ omni-medical-ocr    │
                  │ (Docker + Gradio)   │
                  └─────────────────────┘
```

### Docker Images

| Image | Dockerfile | Description | Size |
|-------|-----------|-------------|------|
| `omni-ocr` | `Dockerfile.gradio` | Multi-stage Gradio HITL app | ~1.8 GB |
| `omni-api` | `Dockerfile.api` | FastAPI backend | ~1.2 GB |

### Quick Start with Docker Compose

```bash
# Gradio only (lightweight — no databases)
docker-compose up gradio

# Full stack (Gradio + API + PostgreSQL + Redis + Qdrant)
docker-compose --profile infra up
```

### CI/CD Pipeline

| Step | Trigger | Action |
|------|---------|--------|
| Path filter | Push to `main` with changes in `hf-space/`, `Dockerfile.gradio`, `packages/` | Triggers deploy |
| Sync files | Copies `app.py`, `src/`, `packages/`, `config/` from monorepo to HF Space | Preserves HF Dockerfile |
| Push | Auto-commits and pushes to `DrAbdulmalek/omni-medical-ocr` | Space rebuilds |

### Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `omni_dev_pass` | PostgreSQL password |
| `SECRET_KEY` | *(dev placeholder)* | API auth secret |
| `ENABLE_LLM` | `false` | Enable Jais proofreader (requires GPU) |
| `HF_TOKEN` | — | HuggingFace token for dataset upload |

### HuggingFace Spaces

The Gradio app auto-deploys to [omni-medical-ocr](https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr) on every push to `main` that modifies `hf-space/` or `Dockerfile.gradio`.

**Live Demo:** [https://drabdulmalek-omni-medical-ocr.hf.space](https://drabdulmalek-omni-medical-ocr.hf.space)

#### HF Space Features
| Feature | Description |
|---------|-------------|
| **OCR Processing** | PaddleOCR + Tesseract ensemble, preprocessing, spell check, NER |
| **Translation** | Arabic ↔ English ↔ German (MarianMT, lazy-loaded) |
| **Accuracy Metrics** | CER/WER calculator with jiwer verification |
| **Save to Dataset** | Upload corrections to `DrAbdulmalek/arabic-medical-ocr-corrections` |

#### Manual Deploy to HF Spaces
```bash
# Clone the Space
git clone https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
cd omni-medical-ocr

# Copy deployment files from monorepo
cp -r ../omni-medical-suite/hf-space/* .

# Push (triggers Docker rebuild on HF)
git add . && git commit -m "Update from monorepo" && git push
```

#### Enable Auto-Deploy (CI/CD)
1. Go to GitHub repo → Settings → Secrets and variables → Actions
2. Add `HF_TOKEN` with your HuggingFace access token
3. Every push to `main` that changes `hf-space/` will auto-deploy

---

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/ --ignore=tests/loadtest -q

# Run linter
ruff check src/ packages/ app/

# Run type checker
mypy . --ignore-missing-imports

# Local development server
make dev
```

## Monitoring & Maintenance

### Health Checks

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `/health` | Full health check | `{"status": "healthy"}` |
| `/health/liveness` | Liveness probe | `{"status": "alive"}` |
| `/health/readiness` | Readiness probe | `{"status": "ready"}` |

### Monitoring Stack

Start with:
```bash
docker-compose -f docker-compose.yml -f infra/monitoring/docker-compose.monitoring.yml up -d
```

| Service | URL | Description |
|---------|-----|-------------|
| Prometheus | http://localhost:9090 | Metrics collection (15s scrape) |
| Grafana | http://localhost:3000 | Dashboards (admin / `${GRAFANA_ADMIN_PASSWORD}`) |
| Node Exporter | http://localhost:9100 | System metrics |

### Backup Strategy

- **Frequency:** Daily at 2:00 AM (configurable)
- **Retention:** 30 days
- **Location:** `/app/backups/`
- **Components:** Database (pg_dump), Redis (RDB snapshot), Critical files
- **Manual trigger:** `python -m scripts.backup`

### Update Mechanism

- **Check interval:** Every hour
- **Notification:** Logged via structured logging
- **Auto-update:** Disabled (manual approval required)
- **Manual check:** `python -m scripts.update_checker`

### Documentation

- **RUNBOOK:** [docs/RUNBOOK.md](docs/RUNBOOK.md) — Operations guide
- **Maintenance Log:** [docs/MAINTENANCE.md](docs/MAINTENANCE.md) — Schedule & benchmarks
- **API Docs:** `/docs` — Swagger UI
- **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Roadmap

- [x] **v1.0** — Monorepo consolidation (6 repos merged)
- [x] **v1.1** — CI/CD + Docker + HF Space deployment
- [x] **v1.2** — Testing infrastructure + ruff + mypy + PyQt6 desktop app
- [x] **v1.3** — Monitoring + Maintenance (Prometheus, Grafana, Health Checks, Backup)
- [ ] **v1.4** — Multi-page PDF + table extraction
- [ ] **v1.5** — Weekly auto-retraining pipeline
- [ ] **v2.0** — Real-time collaboration + RBAC + audit log

See [docs/ROADMAP.md](docs/ROADMAP.md) for details.

## Requirements

- Python 3.10+
- 8 GB RAM minimum (16 GB recommended)
- CUDA optional (GPU acceleration for TrOCR / Jais)
- Docker + Docker Compose (for containerized deployment)

## License

[MIT](LICENSE) &copy; 2026 Dr. Abdulmalek

---

## Standalone Tools

The following Gradio-based tools serve different use cases and are independent
from the main OCR pipeline. They are **not** part of the canonical app but are
available for specific workflows.

### Scanner Fixer Pro (`desktop/gradio_scanner_app.py`)

Web-based alternative to the Tkinter desktop scanner app. Provides the same
image enhancement pipeline via the browser.

**Features:**
- Shadow removal, deskew, perspective correction
- Denoising (fastNlMeans), CLAHE contrast enhancement, auto-crop
- Per-option toggles and processing metrics

**Run:**
```bash
python desktop/gradio_scanner_app.py
```

### Medical Data Analysis Platform (`apps/handwriting-demo/hf-deploy/app/gradio_app.py`)

Interactive HuggingFace Spaces deployment with clinical AI features.

**Features:**
- OCR Correction — annotated bounding boxes, editable word crops, ground truth collection
- Document Parser — extract structured text from PDF/DOCX/PPTX
- Medical Analysis — extract vitals, medications, diagnoses from free-form text
- Clinical Q&A — evidence-based clinical questions with citations

### Telegram Content Forwarder (`tools/ops/telegram_forwarder/app.py`)

Gradio UI for the Telegram content forwarding tool (ops utility).

**Features:**
- Download-Upload technique to bypass "Restrict Saving Content" on protected channels
- Real-time progress tracking, session string export for HF Spaces
- Configurable delay, media/text filtering, reverse order
- Rate-limit warnings and cancel support

---

## Archived Prototypes

Formerly PENDING Gradio files with unique but non-production code have been
moved to `research/prototypes/`. See that directory for details.

## Legacy Translation Corrector Notes

The file `packages/file_processor/legacy/translation_corrector/app.py` (977
lines) contains a `TranslationRule`-based Arabic translation post-correction
system with **13 unique regex patterns** not present in
`packages/medical/tmx_processor.py`. The tmx_processor handles TMX file
import/export and has only 3 language-detection regexes — it is a different
tool entirely.

**Unique regex rules in the legacy file:**

| Pattern | Purpose |
|---------|---------|
| `comma_spacing` | Normalize comma whitespace |
| `arabic_comma` | Normalize Arabic comma (،) spacing |
| `waw_conjunction` | Fix waw after punctuation |
| `number_spacing` | Merge split digits |
| `number_comma` | Handle decimal commas in numbers |
| `passive_by` | Detect English passive voice (was/were/by) |
| `passive_simple` | Detect English passive (was/is/are + -ed) |
| `tanween_alif` | Detect incorrect tanween alif |
| `redundant_ba` | Remove redundant "بواسطة" |
| `redundant_waw` | Fix redundant waw after certain words |
| `word_repeat` | Remove consecutive duplicate words |
| `extra_spaces` | Collapse multiple spaces |
| `space_before_punct` | Remove space before Arabic punctuation |

These rules are preserved in the legacy file for future reference.

---

<p align="center">
  <sub>Built with passion for Arabic medical NLP</sub>
</p>