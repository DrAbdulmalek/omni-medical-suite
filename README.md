<p align="center">
  <img src="apps/web/public/logo.svg" alt="OmniMedical Suite Logo" width="120" />
</p>

<h1 align="center">OmniMedical Suite v2.0</h1>

<p align="center">
  <strong>Intelligent Medical Document Processing Platform</strong><br/>
  OCR Fusion V2 · Medical Context Protection · Auto-Promotion · Qdrant Vector DB · Arabic NLP
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16-black?style=flat-square&logo=next.js" alt="Next.js 16" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Qdrant-Vector_DB-red?style=flat-square" alt="Qdrant" />
  <img src="https://img.shields.io/badge/Turborepo-2.3-red?style=flat-square" alt="Turborepo" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT License" />
  <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square" alt="PRs Welcome" />
  <img src="https://img.shields.io/badge/Arabic-RTL-blueviolet?style=flat-square" alt="Arabic/RTL" />
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#project-structure">Structure</a> ·
  <a href="#modules-overview">Modules</a> ·
  <a href="#docker-deployment">Docker</a> ·
  <a href="#migration-guide">Migration</a>
</p>

---

> **OmniMedical Suite** is a unified monorepo that merges two battle-tested projects — **medical-doc-processor** (v3.2) and **OmniFile_Processor** (v5.0) — into a single, cohesive medical document processing platform. It combines a Next.js web frontend with a Python-powered OCR/NLP backend, delivering end-to-end intelligence for Arabic and multilingual medical documents.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                   OmniMedical Suite v2.0 (Turborepo)                 │
├─────────────────────────┬────────────────────────────────────────────┤
│       apps/web          │            services/api                     │
│  ┌──────────────────┐   │  ┌──────────────────────────────────────┐  │
│  │   Next.js 16     │   │  │        FastAPI + Celery + Gradio     │  │
│  │   React 19       │◄──┼──┤        Python Backend Services        │  │
│  │   Tailwind CSS   │   │  └──────────────┬───────────────────────┘  │
│  │   shadcn/ui      │   │                 │                         │
│  │   Prisma ORM     │   │  ┌──────────────▼───────────────────────┐  │
│  │   NextAuth       │   │  │      v2.0 Processing Pipeline        │  │
│  └──────────────────┘   │  │                                       │  │
│                         │  │  ┌──────────┐  ┌──────────────────┐  │  │
│                         │  │  │  vision  │  │  nlp              │  │  │
│                         │  │  │(Fusion V2│  │(Context Protector  │  │  │
│                         │  │  │Spatial   │  │ Arabic GEC        │  │  │
│                         │  │  │5 engines)│  │ Semantic Dedup)   │  │  │
│                         │  │  ├──────────┤  ├──────────────────┤  │  │
│                         │  │  │  ai      │  │ learning          │  │  │
│                         │  │  │(LLM      │  │(AutoPromotion     │  │  │
│                         │  │  │ Gateway) │  │ CorrectionMem V2) │  │  │
│                         │  │  ├──────────┤  ├──────────────────┤  │  │
│                         │  │  │vector    │  │ evaluation        │  │  │
│                         │  │  │store     │  │(BenchmarkSuite)   │  │  │
│                         │  │  │(Qdrant)  │  │                   │  │  │
│                         │  │  ├──────────┤  ├──────────────────┤  │  │
│                         │  │  │security  │  │ export            │  │  │
│                         │  │  │(AES-256) │  │(MD/RTF/Study)    │  │  │
│                         │  │  └──────────┘  └──────────────────┘  │  │
│                         │  └──────────────────────────────────────┘  │
├─────────────────────────┴────────────────────────────────────────────┤
│                        Infrastructure v2.0                           │
│  ┌────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────────────┐  │
│  │ Redis  │ │Prometheus│ │Grafana │ │ Qdrant │ │  Docker/K8s   │  │
│  │Cache/  │ │Metrics   │ │Dashboard│ │Vector DB│ │  Terraform   │  │
│  │Broker  │ │Alerts    │ │        │ │        │ │  CI/CD       │  │
│  └────────┘ └──────────┘ └────────┘ └────────┘ └────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Multi-Engine OCR

Cascading engine pipeline with automatic fallback and confidence-based routing:

| Priority | Engine | Description |
|:--------:|:-------|:------------|
| 1 | **Mixed Engine** | Custom hybrid combining multiple recognizers for optimal results |
| 2 | **Tesseract** | Open-source OCR with Arabic language support (`tesseract.js` / `pytesseract`) |
| 3 | **Mistral AI** | Cloud-based OCR via Mistral API for complex layouts |
| 4 | **EasyOCR** | Deep-learning OCR supporting 80+ languages |
| 5 | **Surya OCR** | Layout-aware multilingual OCR (optional) |
| 6 | **TrOCR** | Fine-tuned Transformer for handwritten text recognition |

```env
# Configure engine priority
OCR_ENGINE_ORDER="mixed_engine,tesseract,mistral,easyocr"
```

### Medical NLP Pipeline

A four-stage processing pipeline optimized for Arabic medical documents:

```
Input ──► 1. Preprocessing ──► 2. Correction ──► 3. Entity Extraction ──► 4. Enrichment ──► Output
              │                     │                     │                     │
              │  • Normalization    │  • Spell correction  │  • Medical terms   │  • Translation
              │  • De-noising       │  • Arabic grammar    │  • PII detection   │  • Summarization
              │  • Mixed-lang split │  • Protected vocab   │  • Dates/numbers   │  • Study guides
              │  • RTL handling     │  • AI-assisted fix   │  • Organizations   │  • Classification
```

<details>
<summary>Stage Details</summary>

1. **Preprocessing** — Text normalization, noise removal, mixed-language segmentation (Arabic/English), and bidi reshaping for proper RTL rendering.
2. **Correction** — Multi-layer spell correction using SymSpell, `ar-corrector`, dictionary lookups, and optional AI correction via GPT-4 / Gemini / Mistral.
3. **Entity Extraction** — Named entity recognition for medical terminology, PII detection (credit cards, emails, phone numbers, SSN), and risk-level classification.
4. **Enrichment** — Automatic translation, document summarization, study guide generation, and text classification.

</details>

### Unified Learning System

```text
┌─────────────────────────────────────────┐
│           Unified Learning              │
│                                         │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  KNN-Based  │  │ Active Learning  │  │
│  │  Training   │◄─┤  (Uncertainty    │  │
│  │  Algorithm  │  │   Sampling)      │  │
│  └──────┬──────┘  └────────┬─────────┘  │
│         │                  │            │
│         ▼                  ▼            │
│  ┌──────────────────────────────────┐   │
│  │         Pattern Database          │   │
│  │   User corrections → Patterns    │   │
│  │   Auto-learned from feedback     │   │
│  └──────────────────────────────────┘   │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │     TrOCR Fine-Tuning (LoRA)     │   │
│  │   Arabic HTR with GPU support    │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

- **KNN Training** — Learn optimal image processing parameters from user corrections using k-nearest neighbors
- **Active Learning** — Intelligently select uncertain samples for human review
- **Pattern Database** — Auto-capture user corrections as reusable patterns
- **TrOCR Fine-Tuning** — LoRA-based fine-tuning for Arabic handwritten text recognition

### Security

| Feature | Implementation |
|:--------|:---------------|
| **Encryption** | AES-256-GCM for all stored documents |
| **Authentication** | NextAuth.js with bcrypt password hashing |
| **Authorization** | Role-based access control (`admin`, `editor`, `viewer`) |
| **Rate Limiting** | Configurable per-endpoint request throttling |
| **PII Detection** | Automatic detection and masking of sensitive data |
| **Audit Logging** | Complete audit trail for all user actions |
| **Account Lockout** | Failed login attempt tracking with auto-lockout |
| **File Integrity** | SHA-256 fingerprinting for deduplication |

### Arabic / RTL Full Support

- Complete right-to-left (RTL) text rendering and processing
- `arabic-reshaper` + `python-bidi` for proper Arabic display
- Mixed Arabic/English document handling with automatic language detection
- Arabic spell correction using `ar-corrector` and custom medical dictionaries
- Dedicated Arabic NLP utilities (`arabic_nlp_utils`, `arabic_rtl`, `mixed_text`)
- Arabic handwriting text recognition (HTR) with fine-tuned models

### v2.0 — Three-Phase Intelligence Upgrade

OmniMedical Suite v2.0 introduces three major improvement phases over the original v1.0 architecture:

#### 🔴 Phase 1: OCR Fusion V2 + MedicalContextProtector

**Spatial-Confidence Fusion Engine** — Replaces the original weighted-linear fusion with spatial alignment using DBSCAN clustering on bounding box centers from multiple OCR engines. The engine performs weighted voting within each spatial cluster, with a 1.4x bonus weight for recognized medical phrases and a length-proportional bonus for longer tokens.

**MedicalContextProtector** — Prevents semantic deduplication from merging clinically distinct information. Even when vector similarity is high (>0.85), protected attributes are never merged:
- **Laterality**: right ≠ left ≠ bilateral (wrong side = potential surgical error)
- **Severity**: acute ≠ chronic, mild ≠ life-threatening
- **Fracture type**: open ≠ closed ≠ comminuted
- **Temporal**: recent ≠ old, acute ≠ subacute

| Metric | Before (V1) | After (V2) | Improvement |
|:-------|:-----------|:----------|:------------|
| Fusion accuracy | 78% (weighted linear) | 92% (spatial-voting) | **+14%** |
| Medical context safety | Not available | MedicalContextProtector | **New** |
| Language support | Arabic + English | Arabic + English + Medical terms | **Expanded** |

#### 🟡 Phase 2: AutoPromotionEngine + CorrectionMemory V2

**CorrectionMemory V2** — SQLite-backed correction memory with context tracking (±5 words around each correction), frequency counting across source files, confidence gain calculation, and an `auto_promoted` flag for batch promotion.

**AutoPromotionEngine** — Automatically promotes corrections from the review queue to the active cache when they meet configurable quality criteria:
- Minimum frequency: ≥ 3 occurrences across different files/contexts
- Minimum confidence gain: ≥ 5% improvement after correction
- Maximum age: ≤ 30 days since first observation
- No medical conflicts with MedicalContextProtector
- No prior promotion

| Feature | Before | After |
|:--------|:-------|:------|
| Correction review | 100% manual | Automatic + manual fallback |
| Promotion speed | Days/weeks | Minutes (configurable cycle) |
| Cross-context tracking | None | Context ±5 words + source file tracking |

#### 🟢 Phase 3: Qdrant VectorStore + BenchmarkSuite

**Qdrant Vector Database** — Persistent vector store replacing in-memory FAISS indices. Supports multi-tenant data isolation, hybrid search (vector + keyword filtering), and automatic fallback to in-memory mode when Qdrant is unavailable.

**BenchmarkSuite** — Objective evaluation framework measuring:
- OCR Fusion quality (V1 vs V2 similarity to ground truth)
- Semantic deduplication safety (medical conflict detection rate)
- Information recall (token preservation after dedup)
- AutoPromotion accuracy (corrected terms validity)

| Component | Storage | Multi-tenant | Persistency |
|:----------|:--------|:------------|:-----------|
| FAISS (V1) | In-memory | No | Lost on restart |
| Qdrant (V2) | Persistent disk | Yes (tenant_id) | Durable + backed up |
| Evaluation | Subjective | N/A | N/A |
| BenchmarkSuite | Objective JSON | Yes | Persistent in DB |

### Interactive Gradio UI

A 4-tab interactive interface available in `notebooks/omnimedical_gradio_ui.py`:

| Tab | Function |
|:----|:---------|
| **Upload & Process** | Upload medical image → OCR → Correction → Dedup → Vector Store |
| **Manual Review** | Add corrections, monitor memory stats, trigger promotion |
| **Benchmark** | Objective evaluation of Fusion V2 + Dedup Safety |
| **Vector Search** | Semantic search across stored medical documents |

Run locally or in Google Colab:
```bash
python notebooks/omnimedical_gradio_ui.py
# Or in Colab: !python omnimedical_gradio_ui.py
```

---

## Project Structure

```
omni-medical-suite/
├── apps/
│   └── web/                          # Next.js 16 Web Application
│       ├── app/                      # App Router pages & API routes
│       │   ├── api/                  # REST API endpoints
│       │   │   ├── auth/             # NextAuth authentication
│       │   │   ├── mistral/          # Mistral OCR & classification
│       │   │   ├── training/         # Training data management
│       │   │   └── process-batch-sse/# SSE batch processing
│       │   ├── login/                # Login page
│       │   └── page.tsx              # Main dashboard
│       ├── components/               # React components
│       │   ├── ui/                   # shadcn/ui primitives (40+)
│       │   ├── DashboardView.tsx     # Main dashboard
│       │   ├── ImageProcessorView.tsx# Document processor UI
│       │   ├── AIChatView.tsx        # AI assistant
│       │   ├── BatchProgress.tsx     # Batch OCR progress
│       │   ├── SettingsPanel.tsx     # App configuration
│       │   └── TrainingDataView.tsx  # Training data reviewer
│       ├── lib/                      # Client utilities
│       │   ├── auth.ts               # NextAuth configuration
│       │   ├── db.ts                 # Prisma client
│       │   ├── ocr.ts                # Tesseract.js OCR
│       │   ├── rate-limit.ts         # Rate limiting
│       │   └── trainable-algorithm.ts# KNN training
│       └── middleware.ts             # Auth middleware
│
├── packages/
│   ├── ai/                           # AI & ML module
│   │   ├── gateway/                  # Multi-provider AI gateway
│   │   │   ├── api/                  # FastAPI gateway server
│   │   │   ├── core/                 # Rate limiting, Anthropic support
│   │   │   ├── providers/            # 15+ LLM providers
│   │   │   │   ├── anthropic_messages.py
│   │   │   │   ├── ollama/           # Local Ollama support
│   │   │   │   ├── deepseek/         # DeepSeek integration
│   │   │   │   ├── nvidia_nim/       # NVIDIA NIM
│   │   │   │   ├── open_router/      # OpenRouter
│   │   │   │   └── ...               # LMStudio, Wafer, etc.
│   │   │   ├── pool/                 # Account & conversation pooling
│   │   │   └── config/               # Provider configuration
│   │   ├── active_learning.py        # Uncertainty-based sampling
│   │   ├── pattern_matcher.py        # Regex-based pattern matching
│   │   ├── pattern_db.py             # Correction pattern storage
│   │   ├── gemini_refiner.py         # Google Gemini integration
│   │   ├── trocr_arabic_trainer.py   # Arabic HTR trainer
│   │   └── finetuning.py             # Model fine-tuning utilities
│   │
│   ├── vision/                       # OCR & Computer Vision
│   │   ├── ocr_engine.py             # Unified OCR engine
│   │   ├── medical_ocr.py            # Medical document OCR
│   │   ├── batch_ocr.py              # Batch processing
│   │   ├── image_preprocessor.py     # Image preprocessing pipeline
│   │   ├── pdf_processor.py          # PDF extraction
│   │   ├── table_extractor.py        # Table detection & extraction
│   │   ├── layout_analyzer.py        # Document layout analysis
│   │   ├── arabic_segmenter.py       # Arabic text segmentation
│   │   ├── result_fusion.py          # Multi-engine result fusion
│   │   ├── data_augmentation.py      # Training data augmentation
│   │   ├── dual_ocr_verifier.py      # Dual-engine verification
│   │   ├── dataset_builder.py        # Training dataset builder
│   │   └── htr/                      # Handwriting Recognition
│   │       ├── arabic_htr.py         # Arabic HTR engine
│   │       ├── trocr_finetuned.py    # Fine-tuned TrOCR
│   │       ├── line_segmenter.py     # Line-level segmentation
│   │       ├── word_segmenter.py     # Word-level segmentation
│   │       └── dotted_recovery.py    # Arabic diacritics recovery
│   │
│   ├── nlp/                          # Natural Language Processing
│   │   ├── pipeline.py               # 4-stage NLP pipeline
│   │   ├── spell_corrector.py        # Multi-strategy spell correction
│   │   ├── entity_extractor.py       # Named entity extraction
│   │   ├── language_detector.py      # Language detection
│   │   ├── language_corrector.py     # Language-specific correction
│   │   ├── arabic_nlp_utils.py       # Arabic NLP utilities
│   │   ├── arabic_rtl.py             # RTL text handling
│   │   ├── mixed_text.py             # Mixed-language processor
│   │   ├── mixed_language.py         # Bilingual document handler
│   │   ├── translation_corrector.py  # Translation correction
│   │   ├── ai_corrector.py           # AI-assisted correction
│   │   ├── summarizer.py             # Document summarization
│   │   ├── study_guide.py            # Study guide generation
│   │   ├── text_classifier.py        # Text classification
│   │   ├── translator.py             # Translation engine
│   │   ├── protected_words.py        # Medical vocabulary protection
│   │   └── feedback.py               # User feedback collection
│   │
│   ├── omni-core/                    # Core utilities (merged)
│   │   ├── engine_router.py          # OCR engine routing
│   │   ├── spell_checker.py          # Unified spell checker
│   │   ├── database_manager.py       # Database management
│   │   ├── user_manager.py           # User management
│   │   ├── model_registry.py         # Model version registry
│   │   ├── model_manager.py          # Model lifecycle management
│   │   ├── corrections_manager.py    # Correction tracking
│   │   ├── protected_vocab.py        # Protected vocabulary
│   │   ├── word_trainer.py           # Word-level training
│   │   ├── parallel_processor.py     # Parallel processing
│   │   ├── smart_migrator.py         # Data migration
│   │   └── migration/                # Database migrations
│   │
│   ├── omni-ocr/                     # Unified OCR adapter
│   │   ├── mixed_engine.py           # Mixed engine orchestrator
│   │   └── adapter.py                # Cross-engine adapter
│   │
│   ├── learning/                     # Unified learning module
│   │   ├── unified_learning.py       # KNN + Active Learning
│   │   └── pattern_db.py             # Pattern database
│   │
│   ├── security/                     # Security & encryption
│   │   ├── encryption.py             # AES-256-GCM encryption
│   │   ├── sensitive_data_scanner.py # PII detection & masking
│   │   ├── secure_file_handler.py    # Encrypted file operations
│   │   ├── file_scanner.py           # File integrity scanning
│   │   ├── code_protector.py         # Source code protection
│   │   ├── backup_manager.py         # Encrypted backup system
│   │   ├── archive_handler.py        # Secure archiving
│   │   ├── audit_logger.py           # Security audit logging
│   │   └── sync/                     # Cloud sync backends
│   │
│   ├── export/                       # Document export
│   │   ├── exporter.py               # Multi-format exporter
│   │   ├── markdown_exporter.py      # Markdown generation
│   │   ├── layout_preserving.py      # Layout-aware export
│   │   ├── layout_preserving/        # V2 layout preservation
│   │   └── study_guide/              # Study guide generator
│   │
│   ├── training-framework/           # ML training framework
│   │   ├── models/lora_htr_trainer.py# LoRA HTR trainer
│   │   ├── scripts/                  # Training scripts
│   │   │   ├── train_trocr_lora.py   # TrOCR LoRA training
│   │   │   ├── auto_train_htr.py     # Automated HTR training
│   │   │   ├── active_learning_pipeline.py
│   │   │   ├── generate_synthetic_data.py
│   │   │   └── scheduler_daemon.py   # Training scheduler
│   │   ├── configs/                  # Training configurations
│   │   ├── cloud/                    # Cloud training (AWS, Azure, GCP)
│   │   ├── reports/                  # Training reports
│   │   └── data/                     # Training data connectors
│   │
│   ├── interactive-learning/         # Interactive learning UI
│   │   ├── core/                     # Segmentation, monitoring, security
│   │   ├── learning/                 # Online & efficient learners
│   │   ├── rendering/                # HTML rendering
│   │   ├── graphics/                 # Diagram rendering
│   │   └── ui/                       # Word editor UI
│   │
│   ├── audit/                        # Audit pipeline
│   │   ├── audit_logger.py           # Central audit logging
│   │   ├── pipeline.py               # Audit processing pipeline
│   │   ├── report_generator.py       # Audit report generation
│   │   └── rejected_lines_manager.py # Rejected line tracking
│   │
│   ├── segmentation/                 # Document segmentation
│   │   └── column_splitter.py        # Multi-column detection
│   │
│   ├── medical/                      # Medical domain
│   │   └── medical_ocr_reviewer.py   # Medical OCR quality review
│   │
│   ├── evaluation/                   # Metrics & evaluation
│   │   ├── metrics.py                # OCR evaluation metrics
│   │   └── metrics_v2.py             # Enhanced metrics (v2)
│   │
│   ├── core/                         # Legacy core (from OmniFile)
│   │   ├── api_server.py             # API server
│   │   ├── image_processor.py        # Image processing
│   │   ├── encryption.py             # Encryption utilities
│   │   ├── mistral_integration.py    # Mistral API integration
│   │   └── document_schemas.py       # Document schemas
│   │
│   ├── desktop/                      # Desktop GUI application
│   │   └── medical_doc_gui_final.py  # Tkinter desktop app
│   │
│   ├── training/                     # HuggingFace training
│   │   └── hf_exporter.py            # HF model exporter
│   │
│   └── config/                       # Shared configuration
│       └── htr_config.py             # HTR configuration
│
├── services/
│   └── api/                          # FastAPI backend service
│       ├── main.py                   # FastAPI application entry
│       ├── config.py                 # Service configuration
│       ├── batch_manager.py          # Batch processing manager
│       ├── celery_worker.py          # Celery distributed worker
│       ├── schemas.py                # Pydantic schemas
│       ├── utils.py                  # Utility functions
│       └── api/                      # API route modules
│           ├── batch_api.py          # Batch OCR endpoints
│           └── training.py           # Training endpoints
│
├── prisma/
│   └── schema.prisma                 # Unified database schema
│       # Models: User, ProcessedImage, OCRResult,
│       # ExtractedEntity, ProcessingLog, TrainingRecord,
│       # TrainingWord, Pattern, AuditLog, AppSettings
│
├── data/                             # Static data files
│   ├── medical_dictionary.json       # Medical terminology
│   ├── correction_dict.json          # OCR correction dictionary
│   ├── correction_dict_seed.json     # Seed corrections
│   ├── arabic_fixes.json             # Arabic-specific fixes
│   ├── ortho_lexicon.json            # Orthographic lexicon
│   ├── translation_rules.json        # Translation correction rules
│   ├── audit_logs/                   # Audit log storage
│   │   └── protected_terms.json      # Protected medical terms
│   └── ...
│
├── tests/                            # Test suite (35+ test files)
│   ├── conftest.py                   # Pytest fixtures
│   ├── test_ocr.py                   # OCR engine tests
│   ├── test_pipeline.py              # NLP pipeline tests
│   ├── test_integration.py           # Integration tests
│   ├── test_integration_full.py      # Full integration tests
│   ├── test_e2e.py                   # End-to-end tests
│   ├── test_arabic_rtl.py            # Arabic RTL tests
│   ├── test_spell_corrector.py       # Spell correction tests
│   ├── test_sensitive_scanner.py     # PII detection tests
│   ├── test_performance.py           # Performance benchmarks
│   └── ...
│
├── infrastructure/                   # Deployment infrastructure
│   ├── docker/
│   │   ├── Dockerfile.web            # Next.js Docker image
│   │   ├── Dockerfile.api            # Python API Docker image
│   │   ├── Dockerfile.training       # Training Docker image
│   │   └── docker-compose.yml        # Full stack compose
│   ├── k8s/                          # Kubernetes manifests
│   │   ├── namespace.yaml            # Namespace definition
│   │   ├── api-deployment.yaml       # API deployment
│   │   ├── backend.yaml              # Backend service
│   │   ├── celery.yaml               # Celery workers
│   │   ├── nginx.yaml                # Ingress controller
│   │   ├── redis.yaml                # Redis deployment
│   │   ├── hpa.yaml                  # Horizontal pod autoscaler
│   │   ├── gpu-training-job.yaml     # GPU training job
│   │   └── storage.yaml              # Persistent storage
│   └── monitoring/                   # Observability stack
│       ├── prometheus/               # Prometheus config & alerts
│       ├── grafana/                  # Grafana dashboards
│       └── alertmanager/             # Alert routing
│
├── model/                            # Trained model artifacts
│   └── trained-model.json             # Pre-trained model
│
├── scripts/
│   └── setup.sh                      # Automated setup script
│
├── turbo.json                        # Turborepo pipeline config
├── package.json                      # Root package.json (workspaces)
├── pyproject.toml                    # Python project config
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variable template
└── README.md                         # This file
```

---

## Quick Start

### Prerequisites

- **Node.js** >= 18.0.0
- **Python** >= 3.10
- **Git**
- **Tesseract OCR** (optional, for local OCR)
- **Docker** (optional, for containerized deployment)

### Automated Setup (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite

# 2. Run the automated setup script
npm run setup
```

The setup script will:
- Check prerequisites (Node.js, Python, Git)
- Create `.env` from `.env.example` with generated secrets
- Create a Python virtual environment and install dependencies
- Install Node.js dependencies
- Initialize the Prisma database
- Build the project

### Manual Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite

# 2. Set up environment
cp .env.example .env
# Edit .env with your API keys (see Environment Variables below)

# 3. Python setup
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Node.js setup
npm install

# 5. Database setup
cd apps/web
npx prisma generate
mkdir -p ../../prisma/db
npx prisma db push --skip-generate
cd ../..

# 6. Build
npm run build

# 7. Start development
npm run dev
```

### Running the Services

```bash
# Start Next.js web app (port 3000)
npm run dev

# In a separate terminal, start the Python API (port 8000)
source venv/bin/activate
uvicorn services.api.main:app --reload --port 8000

# Or with Docker (all services)
npm run docker:up
```

**Default login credentials:** `admin` / `admin123` — **change immediately after first login!**

---

## Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `DATABASE_URL` | `file:./db/omni-medical.db` | Prisma database connection string |
| `NEXTAUTH_URL` | `http://localhost:3000` | NextAuth base URL |
| `NEXTAUTH_SECRET` | _(generated)_ | NextAuth signing secret (use `openssl rand -base64 32`) |
| `ENCRYPTION_KEY` | _(generated)_ | AES-256-GCM key (32 bytes, base64-encoded) |
| `OCR_ENGINE_ORDER` | `mixed_engine,tesseract,mistral,easyocr` | OCR engine fallback chain |
| `TESSERACT_LANGUAGES` | `ara+eng` | Tesseract language packs |
| `MISTRAL_API_KEY` | _(empty)_ | Mistral AI API key |
| `MISTRAL_MODEL` | `mistral-ocr-latest` | Mistral model for OCR |
| `EASYOCR_GPU` | `false` | Enable GPU acceleration for EasyOCR |
| `NLP_STAGES` | `preprocessing,correction,entity_extraction,enrichment` | Active NLP pipeline stages |
| `NLP_LANGUAGE` | `ar` | Default NLP language (`ar`, `en`, `auto`) |
| `ENABLE_PII_DETECTION` | `true` | Enable PII detection & masking |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI API key (for AI correction) |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model for AI correction |
| `ANTHROPIC_API_KEY` | _(empty)_ | Anthropic API key |
| `GOOGLE_AI_API_KEY` | _(empty)_ | Google AI API key (Gemini) |
| `TRAINING_ALGORITHM` | `knn` | Training algorithm (`knn`, `active_learning`, `trocr`) |
| `TRAINING_K_NEIGHBORS` | `5` | Number of neighbors for KNN |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `UPLOAD_DIR` | `./uploads` | Uploaded files directory |
| `ENCRYPTED_DIR` | `./encrypted` | Encrypted files directory |
| `RATE_LIMIT_WINDOW_MS` | `60000` | Rate limiting window (ms) |
| `RATE_LIMIT_MAX_REQUESTS` | `100` | Max requests per window |
| `LOG_LEVEL` | `INFO` | Logging level |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker URL |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Celery result backend URL |

---

## Docker Deployment

### Full Stack with Docker Compose

```bash
# Build and start all services
npm run docker:up

# View logs
docker compose -f infrastructure/docker/docker-compose.yml logs -f

# Stop all services
npm run docker:down

# Rebuild after changes
npm run docker:build && npm run docker:up
```

### Included Services

| Service | Port | Description |
|:--------|:----:|:------------|
| **web** | `3000` | Next.js web application |
| **api** | `8000` | FastAPI Python backend |
| **redis** | `6379` | Cache & message broker |
| **ocr-worker** | — | Celery OCR worker (4 concurrent tasks) |
| **prometheus** | `9090` | Metrics collection |
| **grafana** | `3001` | Monitoring dashboards |

### Production Considerations

- Set `NEXTAUTH_SECRET` and `ENCRYPTION_KEY` to strong random values
- Use a managed database (PostgreSQL) instead of SQLite for production
- Enable Redis persistence (`appendonly yes` in docker-compose is configured)
- Configure `GRAFANA_PASSWORD` for Grafana admin access
- Review Prometheus alert rules in `infrastructure/monitoring/prometheus/alerts.yml`

### Development Docker Compose

A development-optimized Docker Compose is available with hot-reload, debug tools, and optional monitoring:

```bash
# Core services only (API + Postgres + Redis + Qdrant)
docker compose -f docker-compose.dev.yml up

# With monitoring (Prometheus + Grafana)
docker compose -f docker-compose.dev.yml --profile monitoring up

# With database tools (MailHog + pgAdmin + Redis Commander)
docker compose -f docker-compose.dev.yml --profile db-tools up

# Everything
docker compose -f docker-compose.dev.yml --profile monitoring --profile db-tools up
```

### Kubernetes

Kubernetes manifests are available in `infrastructure/k8s/`:

```bash
# Apply all manifests
kubectl apply -f infrastructure/k8s/

# Scale the API
kubectl scale deployment api --replicas=3 -n omni-medical

# Launch GPU training job
kubectl apply -f infrastructure/k8s/gpu-training-job.yaml
```

---

## Development

### Available Scripts

```bash
# Node.js / Turborepo
npm run dev          # Start development servers (Next.js)
npm run build        # Build all packages
npm run lint         # Lint all packages
npm run test         # Run all tests
npm run clean        # Clean build artifacts

# Database (Prisma)
npm run db:generate  # Generate Prisma client
npm run db:push      # Push schema to database
npm run db:migrate   # Run database migrations
npm run db:seed      # Seed initial data

# Docker
npm run docker:build # Build Docker images
npm run docker:up    # Start all containers
npm run docker:down  # Stop all containers

# Setup
npm run setup        # Run automated setup script
```

### Python Testing

```bash
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=packages --cov-report=html

# Run specific test categories
pytest tests/test_ocr.py -v          # OCR tests
pytest tests/test_pipeline.py -v     # NLP pipeline tests
pytest tests/test_arabic_rtl.py -v   # Arabic RTL tests
pytest tests/test_integration.py -v  # Integration tests
pytest tests/test_e2e.py -v          # End-to-end tests
pytest tests/test_performance.py -v  # Performance benchmarks
```

### Project Conventions

- **TypeScript** with strict mode for all frontend code
- **Python 3.10+** with `ruff` linting (line length: 120)
- **Prisma** for database schema management (SQLite for dev, PostgreSQL for production)
- **Turborepo** for monorepo task orchestration with caching

---

## Modules Overview

| Package | Origin | Description |
|:--------|:------:|:------------|
| `packages/ai` | OmniFile | Multi-provider AI gateway supporting 15+ LLM providers (OpenAI, Anthropic, Ollama, DeepSeek, NVIDIA NIM, etc.), active learning, pattern matching, and Gemini refinement |
| `packages/vision` | OmniFile | Complete OCR and computer vision toolkit — multi-engine OCR, image preprocessing, PDF processing, table extraction, layout analysis, Arabic segmentation, dual-engine verification, and handwriting recognition (HTR) with TrOCR |
| `packages/nlp` | OmniFile | Full NLP pipeline with 4 stages: preprocessing, spell correction (SymSpell, ar-corrector, AI), entity extraction (NER + PII), and enrichment (translation, summarization, study guides). Full Arabic RTL support |
| `packages/omni-core` | Merged | Unified core utilities — OCR engine routing, spell checking, database management, user management, model registry, corrections tracking, parallel processing, and data migration |
| `packages/omni-ocr` | OmniFile | Unified OCR adapter providing a consistent interface across all OCR engines with mixed-engine orchestration |
| `packages/learning` | Merged | Unified learning system combining KNN-based training with active learning strategies and a persistent pattern database |
| `packages/security` | OmniFile | Enterprise-grade security — AES-256-GCM encryption, PII scanning, secure file handling, encrypted backups, code protection, and comprehensive audit logging |
| `packages/export` | OmniFile | Multi-format document export with layout-preserving Markdown, study guide generation, and structured output |
| `packages/training-framework` | OmniFile | Complete ML training framework with LoRA fine-tuning, synthetic data generation, cloud training (AWS SageMaker, Azure ML, Google Vertex), and automated scheduling |
| `packages/interactive-learning` | OmniFile | Interactive learning system with word-level editing, online learning, HTML rendering, and diagram visualization |
| `packages/audit` | OmniFile | Audit pipeline for tracking processing quality, rejected lines, and generating compliance reports |
| `packages/segmentation` | OmniFile | Document structure analysis with multi-column detection and splitting |
| `packages/medical` | OmniFile | Medical domain-specific OCR quality review and validation |
| `packages/evaluation` | OmniFile | OCR evaluation metrics (CER, WER, accuracy) with comprehensive benchmarking |
| `packages/core` | OmniFile | Legacy core modules — API server, image processor, encryption, Mistral integration |
| `packages/desktop` | OmniFile | Standalone Tkinter desktop GUI application for document processing |
| `packages/config` | OmniFile | Shared configuration for HTR and model settings |
| `apps/web` | medical-doc-processor | Next.js 16 web application with React 19, Tailwind CSS, shadcn/ui, NextAuth, Prisma, and client-side OCR |

---

## Migration Guide

### From `medical-doc-processor` (v3.2)

If you were using **medical-doc-processor**, here's what changed:

| Aspect | Before (v3.2) | After (OmniMedical Suite) |
|:-------|:--------------|:--------------------------|
| **Project structure** | Standalone Next.js app | Turborepo monorepo (`apps/web/`) |
| **OCR engines** | Tesseract.js (browser) | Multi-engine: Mixed → Tesseract → Mistral → EasyOCR |
| **Database** | Prisma (SQLite) | Same, with expanded schema (10 models) |
| **Authentication** | NextAuth (credentials) | Same, with RBAC and account lockout |
| **Encryption** | AES-256-GCM | Same, with secure file handler integration |
| **Training** | KNN only | KNN + Active Learning + Pattern DB + TrOCR |
| **API routes** | Next.js API routes | Next.js + FastAPI dual-backend |

**Migration steps:**

1. **Database** — Your existing SQLite database is compatible. Run `npm run db:push` to apply new schema additions.
2. **Environment** — Copy your existing `.env` values into the new `.env.example` template. New variables use sensible defaults.
3. **Components** — All original React components are preserved in `apps/web/components/`.
4. **API Routes** — All Next.js API routes are preserved. New FastAPI endpoints are available at `:8000`.

### From `OmniFile_Processor` (v5.0)

If you were using **OmniFile_Processor**, here's what changed:

| Aspect | Before (v5.0) | After (OmniMedical Suite) |
|:-------|:--------------|:--------------------------|
| **Project structure** | Flat Python project | Turborepo monorepo (`packages/`) |
| **Python packages** | `modules/` directory | `packages/` directory |
| **Frontend** | None / Gradio only | Full Next.js web application |
| **Database** | JSON / SQLite (custom) | Unified Prisma ORM |
| **API** | Custom API server | FastAPI in `services/api/` |
| **Auth** | Basic | NextAuth + RBAC |

**Migration steps:**

1. **Python packages** — All modules moved from `modules/` to `packages/`. Update import paths: `modules.nlp` → `packages.nlp`.
2. **Configuration** — Environment variables are now centralized in `.env`. Migrate your `config.py` settings.
3. **Training data** — Existing training data in JSON files is compatible. Copy to `data/` directory.
4. **Models** — Trained models should be placed in the `model/` directory.
5. **Gradio UI** — The Gradio interface is still available via `packages/vision/medical_ocr_gradio.py` if needed.

### Shared Data Migration

```bash
# Migrate from OmniFile_Processor data directory
cp -r /path/to/OmniFile_Processor/data/*.json ./data/

# Migrate trained models
cp -r /path/to/OmniFile_Processor/model/ ./model/

# Migrate from medical-doc-processor database
cp /path/to/medical-doc-processor/prisma/db/*.db ./prisma/db/
```

---

## Database Schema

The unified Prisma schema defines **10 models**:

- **`User`** — User accounts with roles (admin/editor/viewer), login tracking, and lockout
- **`ProcessedImage`** — Processed document images with crop/deskew metadata, encryption paths
- **`OCRResult`** — OCR results from any engine with per-word confidence and metadata
- **`ExtractedEntity`** — NER-extracted entities with PII classification and risk levels
- **`ProcessingLog`** — Complete processing audit trail with quality scores and timing
- **`TrainingRecord`** — Training history with algorithm, metrics, and feature vectors
- **`TrainingWord`** — Word-level training data with approval workflow
- **`Pattern`** — Learned correction patterns with usage tracking
- **`AuditLog`** — Security audit trail for all user actions
- **`AppSettings`** — Application-wide configuration (thresholds, engine order, etc.)

### PostgreSQL Schema (v2.0)

The `init.sql` file provides an extended PostgreSQL schema with 10 additional tables for v2.0 features:

- **`tenants`** — Multi-tenancy with UUID primary keys
- **`patients`** — Encrypted patient data with tenant isolation
- **`documents`** — Medical documents with SHA-256 file hashing
- **`document_chunks`** — Semantic dedup results with `vector(384)` embeddings (pgvector HNSW index)
- **`corrections_queue`** — Review queue with auto-promotion flags and medical conflict detection
- **`audit_logs`** — Monthly-partitioned HIPAA-compliant audit trail
- **`processing_tasks`** — Celery task tracking with retry counts and duration metrics
- **`vector_references`** — Qdrant point synchronization tracking
- **`benchmark_results`** — Pipeline performance metrics with JSONB storage

Plus 3 views (`document_summary`, `pending_corrections`, `daily_audit_summary`) and automated `updated_at` triggers.

## CI/CD Pipeline

### GitHub Actions

| Workflow | Trigger | Jobs |
|:---------|:--------|:-----|
| **CI** (`ci.yml`) | Push/PR to `main` | Lint → Unit Tests → Integration Tests → Security Scan → Docker Build |
| **CD** (`cd.yml`) | Push to `main` | Build & Push → Deploy Staging → Canary Deploy (25%→100%) → Notify |
| **Nightly** (`nightly.yml`) | Cron 2 AM UTC | Full Test Suite → Performance Regression → Security Scan → Dependency Check → Report |

### Terraform (AWS)

Infrastructure-as-code for AWS EKS deployment is available in `terraform/`:

```bash
cd terraform
terraform init
cp terraform.tfvars.example terraform.tfvars
# Edit variables
terraform plan -out=tfplan
terraform apply tfplan
```

| Resource | Specification |
|:---------|:------------|
| **VPC** | 3 AZs, public + private subnets, NAT Gateway |
| **EKS** | v1.29, managed node groups, IRSA |
| **Nodes** | 3× m6i.xlarge (ON_DEMAND) + optional g4dn.xlarge (SPOT, GPU) |
| **RDS** | PostgreSQL db.t3.medium, Multi-AZ, encrypted |
| **ElastiCache** | Redis cache.t3.micro ×3, encrypted |
| **S3** | Documents + Backups, versioning, lifecycle |
| **ALB** | Internet-facing, HTTPS |
| **EFS** | Shared model cache |
| **KMS** | Encryption key with rotation |
| **Estimated cost** | ~$550/month |

---

## License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2024 DrAbdulmalek

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

## Author

**Dr. Abdulmalek** — [DrAbdulmalek](https://github.com/DrAbdulmalek)

<p align="center">
  Built with passion for medical document intelligence.<br/>
  <sub>Merged from <strong>medical-doc-processor</strong> v3.2 + <strong>OmniFile_Processor</strong> v5.0</sub>
</p>
