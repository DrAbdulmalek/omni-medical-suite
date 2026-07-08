# System Architecture

## Overview

Omni Medical Suite is a monorepo that consolidates 6+ former repositories into a unified platform for Arabic medical OCR. The system follows a layered architecture with clear separation between core engines, processing packages, applications, and infrastructure.

```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATIONS LAYER                       │
│  ┌──────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │  Gradio   │ │  OCR Demo    │ │  Trainer   │ │  Collector   │  │
│  │  HITL UI  │ │  Multi-Engine│ │  UI        │ │  Data App    │  │
│  └────┬─────┘ └──────┬───────┘ └─────┬──────┘ └──────┬───────┘  │
├───────┴──────────────┴───────────────┴───────────────┴──────────┤
│                        SERVICES LAYER                            │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  FastAPI  │ │  Celery    │ │  Postgres│ │  Redis Queue    │  │
│  │  REST API │ │  Workers   │ │  + RBAC  │ │  + Cache        │  │
│  └────┬─────┘ └─────┬──────┘ └──────────┘ └──────────────────┘  │
├───────┴──────────────┴──────────────────────────────────────────┤
│                        PACKAGES LAYER                            │
│                                                                  │
│  ┌─── OCR & Vision ────────────────────────────────────────┐   │
│  │  scanner_fixer │ ocr_postprocess │ vision │ handwriting │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── NLP & AI ────────────────────────────────────────────┐   │
│  │  nlp (spell) │ ai-fuel │ bilingual │ medical │ llm     │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Training & Evaluation ───────────────────────────────┐   │
│  │  training │ training_hub │ gt_core │ benchmark_core     │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Infrastructure ──────────────────────────────────────┐   │
│  │  core │ config │ security │ audit │ export │ omnifile   │   │
│  └────────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────────┤
│                        CORE LIBRARY (src/)                      │
│  ┌──────────┐ ┌─────┐ ┌──────┐ ┌────────┐ ┌───────────────┐  │
│  │    OCR   │ │ NER │ │ LLM  │ │ Layout │ │  Benchmarks   │  │
│  │  Engine  │ │     │ │      │ │        │ │               │  │
│  └──────────┘ └─────┘ └──────┘ └────────┘ └───────────────┘  │
├────────────────────────────────────────────────────────────────┤
│                        INFRASTRUCTURE                           │
│  Docker │ PostgreSQL │ Redis │ Qdrant │ Prometheus │ Grafana  │
└────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Input Image
     │
     ▼
┌─────────────┐
│ Scanner     │  deskew, crop, CLAHE, denoise
│ Fixer       │  (packages/scanner_fixer)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ OCR         │  4 engines: PaddleOCR, Tesseract,
│ Ensemble    │  EasyOCR, TrOCR + Surya
│ (src/ocr)   │  (packages/ocr_postprocess)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Text        │  Arabic RTL handling, mixed
│ Processing  │  language detection
│ (packages/  │
│  nlp)       │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Spell Check │  Hybrid: dictionary + Jais LLM
│ + Medical   │  Protected medical vocabulary
│ Context     │  (packages/nlp, packages/medical)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ NER +       │  Entity extraction, structure
│ Structured  │  parsing, export to JSON/CSV
│ Output      │  (src/ner, packages/export)
└──────┬──────┘
       │
       ▼
  Final Output
  (JSON / CSV / XLSX / PDF)
```

## Package Directory Map

### Applications (`apps/`)

| Directory | Source | Description |
|-----------|--------|-------------|
| `collector/` | — | HITL data collection interface |
| `handwriting-demo/` | handwriting-ocr | Gradio demo for handwriting recognition |
| `ocr-demo/` | — | Multi-engine OCR comparison demo |
| `ocr-pipeline/` | omni-medical-ocr-pipeline | Full end-to-end OCR pipeline |
| `trainer-ui/` | medical-ocr-trainer | Model training & evaluation UI |

### Core Packages (`packages/`)

| Directory | Purpose |
|-----------|---------|
| `ai-fuel/` | AI content generation engine |
| `bilingual/` | Arabic/English bilingual text extraction |
| `core/` | Shared utilities and base classes |
| `doc-processor/` | Document processing and parsing |
| `evaluation/` | Model evaluation metrics |
| `export/` | Data export (CSV, XLSX, JSONL, HF Hub) |
| `file_processor/` | File format detection and routing |
| `gt_core/` | Ground truth management |
| `handwriting/` | Handwriting recognition models |
| `medical/` | Medical domain logic and dictionaries |
| `nlp/` | NLP: spell checking, correction, translation |
| `ocr_postprocess/` | OCR post-processing and result fusion |
| `omnifile/` | Unified file processing (from OmniFile_Processor) |
| `scanner_fixer/` | Pre-OCR image normalization |
| `security/` | RBAC and authentication |
| `training/` | Model training framework |
| `training_hub/` | Continuous retraining pipeline |
| `vision/` | Computer vision utilities |

### Core Library (`src/`)

| Directory | Purpose |
|-----------|---------|
| `ocr/` | OCR engine routing and ensemble logic |
| `ner/` | Named Entity Recognition |
| `llm/` | LLM integration (Jais, Gemini) |
| `layout/` | Document layout analysis |
| `benchmarks/` | Benchmarking utilities |

## Infrastructure

### Docker Compose Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `api` | build (Dockerfile) | 8000 | FastAPI REST API |
| `celery-worker` | build (Dockerfile) | — | Async task processing |
| `celery-beat` | build (Dockerfile) | — | Scheduled tasks |
| `postgres` | postgres:16-alpine | 5432 | Primary database |
| `redis` | redis:7-alpine | 6379 | Queue + cache |
| `qdrant` | qdrant/qdrant | 6333 | Vector search |
| `prometheus` | prom/prometheus | 9090 | Metrics collection |
| `grafana` | grafana/grafana | 3000 | Dashboards |
| `tempo` | grafana/tempo | 3200 | Distributed tracing |
| `nginx` | nginx:alpine | 80 | Reverse proxy |

### Configuration Tiers

| File | Tier | Services |
|------|------|----------|
| `docker-compose.lite.yml` | Lite | API + Postgres + Redis only |
| `docker-compose.standard.yml` | Standard | + Qdrant + Celery |
| `docker-compose.yml` | Full | + Monitoring (Prometheus, Grafana, Tempo) |
| `docker-compose.medical-infra.yml` | Medical Infra | Specialized medical processing |
| `docker-compose.prod.yml` | Production | Production-optimized settings |

## API Endpoints

### OCR Processing
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ocr/process` | Process single image |
| `POST` | `/api/v1/ocr/batch` | Process multiple images |
| `POST` | `/api/v1/ocr/pdf` | Process multi-page PDF |
| `GET`  | `/api/v1/ocr/status/{task_id}` | Check async task status |

### Spell Correction
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/correct` | Correct Arabic medical text |
| `POST` | `/api/v1/correct/batch` | Batch correction |
| `GET`  | `/api/v1/dictionary` | Get medical dictionary |
| `POST` | `/api/v1/dictionary/add` | Add terms to dictionary |

### NER
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ner/extract` | Extract named entities |
| `GET`  | `/api/v1/ner/supported-types` | List entity types |

### Training
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/training/submit-correction` | Submit HITL correction |
| `POST` | `/api/v1/training/start` | Trigger retraining |
| `GET`  | `/api/v1/training/status` | Check training status |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Health check |
| `GET`  | `/metrics` | Prometheus metrics |

## Database Schema (PostgreSQL)

```
users
  ├── id, username, email, password_hash
  ├── role (admin, reviewer, viewer)
  └── created_at, last_login

documents
  ├── id, user_id, filename, file_hash
  ├── ocr_result_json, corrected_text
  ├── confidence_score, processing_time_ms
  └── created_at, updated_at

corrections
  ├── id, document_id, user_id
  ├── original_text, corrected_text
  ├── correction_type (spelling, medical, layout)
  └── created_at

medical_dictionary
  ├── id, term_arabic, term_english
  ├── category, frequency
  └── is_protected (bool)

training_runs
  ├── id, status, base_model
  ├── dataset_size, epochs, metrics_json
  └── started_at, completed_at
```

## Error Handling Strategy

| Error Type | HTTP Status | Handling |
|------------|-------------|----------|
| Invalid image | 400 | Return validation errors with field details |
| OCR engine failure | 422 | Fall back to next engine, report partial results |
| LLM timeout | 504 | Return OCR-only results with `llm_corrected: false` |
| Auth failure | 401/403 | JWT validation, RBAC enforcement |
| Rate limit | 429 | Redis-based rate limiting per user |

## Key Design Decisions

1. **Monorepo over Multi-repo**: All 6+ former repositories consolidated for simpler dependency management and atomic commits across packages.

2. **Git Subtree Merges**: Each migrated repo was merged with `--squash` into its designated `packages/` or `apps/` prefix, preserving file history within the subtree.

3. **Medical Vocabulary Protection**: The spell checker treats medical terms as protected vocabulary, preventing "correction" of valid medical terminology.

4. **Multi-Engine OCR Ensemble**: Results from 4+ OCR engines are fused using confidence-based voting, with the ensemble consistently outperforming any single engine.

5. **HITL Feedback Loop**: Human corrections feed back into training data, enabling continuous model improvement through `training_hub` and `gt_core`.