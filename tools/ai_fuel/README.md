<!-- STATUS: ARCHIVED -->
<div align="center">

| Status | Type | Absorbed Into |
|--------|------|---------------|
| <img src="https://img.shields.io/badge/status-archived-inactive" alt="Archived" /> | Pipeline Component | [omni-medical-suite/backend/ai/](https://github.com/DrAbdulmalek/omni-medical-suite/tree/main/backend/ai) |

</div>

> **Archived on 2026-06-28** — Code preserved for reference. All development continues in **[omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)**.

---

<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/DR-ABDULMALEK/ai-fuel-engine/ci.yml?branch=main&style=flat-square" alt="Build Status" />
  <img src="https://img.shields.io/codecov/c/github/DR-ABDULMALEK/ai-fuel-engine?style=flat-square" alt="Coverage" />
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/python-3.9+-green?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/status-archived-inactive?style=flat-square" alt="Status" />
</p>

<h1 align="center">🧪 AI Fuel Engine</h1>

<p align="center">
  <strong>Transform scanned medical books into AI-ready datasets</strong><br/>
  <strong>تحويل الكتب الطبية الممسوحة ضوئياً إلى مجموعات بيانات جاهزة للذكاء الاصطناعي</strong>
</p>

<p align="center">
  <a href="#architecture--الهيكلية">Architecture</a> •
  <a href="#features--المميزات">Features</a> •
  <a href="#quick-start--البدء-السريع">Quick Start</a> •
  <a href="#installation--التثبيت">Installation</a> •
  <a href="#usage--الاستخدام">Usage</a> •
  <a href="#modules--الوحدات">Modules</a> •
  <a href="#configuration--الإعدادات">Configuration</a> •
  <a href="#development--التطوير">Development</a> •
  <a href="#docker--النشر">Docker</a>
</p>

---

## 📖 Overview — نظرة عامة

**AI Fuel Engine** is a comprehensive Python pipeline designed to transform scanned medical textbooks into structured, classified, and deduplicated datasets ready for training large language models and NLP systems. It supports **Arabic** and **English** medical texts and handles the full lifecycle from raw scanned PDFs to clean, exportable datasets.

**محرك وقود الذكاء الاصطناعي** هو نظام متكامل مصمم لتحويل الكتب الطبية الممسوحة ضوئياً إلى مجموعات بيانات منظمة ومصنفة وخالية من التكرار، جاهزة لتدريب نماذج اللغة الكبيرة وأنظمة معالجة اللغة الطبيعية. يدعم النظام النصوص الطبية العربية والإنجليزية ويغطي دورة حياة كاملة من ملفات PDF الخام إلى مجموعات بيانات نظيفة قابلة للتصدير.

---

## 🏗 Architecture — الهيكلية

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        AI FUEL ENGINE PIPELINE                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌───────────┐    ┌────────────┐    ┌───────────────┐  │
│  │  INPUT   │───▶│ SEGMENTER  │───▶│ CLASSIFIER │───▶│ DEDUPLICATOR  │  │
│  │          │    │            │    │            │    │               │  │
│  │ • PDF    │    │ • Fixed    │    │ • Keyword  │    │ • Exact       │  │
│  │ • Images │    │   size     │    │   router   │    │ • Semantic    │  │
│  │ • Text   │    │ • Sentence │    │ • Embedding│    │ • MinHash     │  │
│  │ • Arabic │    │ • Page     │    │ • LLM      │    │ • Fuzzy       │  │
│  │ • English│    │   aware    │    │   assist   │    │               │  │
│  └─────────┘    └───────────┘    └────────────┘    └───────────────┘  │
│                                                          │              │
│  ┌────────────────────────────────────────────────────────▼──────────┐  │
│  │                         EXPORT LAYER                             │  │
│  │  ┌──────┐  ┌────────┐  ┌─────────┐  ┌────────┐  ┌───────────┐  │  │
│  │  │ JSONL│  │ Parquet│  │   CSV   │  │  Excel │  │  Markdown │  │  │
│  │  └──────┘  └────────┘  └─────────┘  └────────┘  └───────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     SUPPORTING SERVICES                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │  │
│  │  │ Active       │  │  Monitoring  │  │  Database / Storage    │  │  │
│  │  │ Learning     │  │  (Prometheus)│  │  (SQLite / Qdrant)    │  │  │
│  │  └──────────────┘  └──────────────┘  └───────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Processing Flow — مسار المعالجة

```
Raw PDFs  →  OCR Extraction  →  Text Segmentation  →  Classification
                                                           │
                    ┌──────────────────────────────────────┘
                    ▼
            Deduplication  →  Quality Filter  →  Export (JSONL/Parquet/CSV)
                                                             │
                    ┌────────────────────────────────────────┘
                    ▼
              AI-Ready Dataset  ←  Active Learning Loop  ←  Human Review
```

---

## ✨ Features — المميزات

### Core Pipeline — المسار الأساسي
- **📖 Multi-format Input** — PDF, images, raw text, and pre-extracted OCR output
- **✂️ Smart Segmentation** — Configurable chunking with overlap, sentence-aware splitting, and page-boundary awareness
- **🏷️ Multi-strategy Classification** — Keyword routing, embedding-based classification, and LLM-assisted tagging
- **🔍 Deduplication** — Exact matching, semantic similarity, MinHash LSH, and fuzzy matching
- **📦 Multi-format Export** — JSONL, Parquet, CSV, Excel, and Markdown

### Bilingual Support — الدعم ثنائي اللغة
- **🇸🇦 Arabic + 🇬🇧 English** — Full support for Arabic and English medical text
- **🔤 Bidirectional text handling** — Proper RTL/LTR text processing
- **🌍 Medical terminology** — Keyword dictionaries for both Arabic and English medical domains

### Quality & Intelligence — الجودة والذكاء
- **🧠 Active Learning** — Human-in-the-loop feedback for continuous model improvement
- **📊 Quality Metrics** — Confidence scoring, coverage analysis, and dataset statistics
- **📈 Monitoring** — Prometheus-compatible metrics for pipeline health
- **🗄️ Persistent Storage** — SQLite for metadata, Qdrant for vector search

### Developer Experience — تجربة المطور
- **⚙️ Configuration-driven** — YAML/ENV configuration for all pipeline parameters
- **🔌 Modular architecture** — Use individual modules or the full pipeline
- **🧪 Comprehensive tests** — Unit, integration, and benchmark tests
- **🐳 Docker support** — Fully containerized deployment with Docker Compose

---

<details>
<summary>Historical documentation (preserved for reference)</summary>

## 🚀 Quick Start — البدء السريع

### Prerequisites — المتطلبات الأساسية
- Python 3.9 or higher (Python 3.11 recommended)
- pip or pipenv
- Tesseract OCR (optional, for PDF processing)

### Install & Run — التثبيت والتشغيل

```bash
# Clone the repository
git clone https://github.com/DR-ABDULMALEK/ai-fuel-engine.git
cd ai-fuel-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -e .

# Process a single document
ai-fuel process --input data/medical_book.pdf --output datasets/output.jsonl

# Or use the Python API
python -c "
from core.engine import AIFuelEngine
engine = AIFuelEngine()
engine.process('data/medical_book.pdf', 'datasets/output.jsonl')
"
```

---

## 📦 Installation — التثبيت

### Standard Installation — التثبيت القياسي

```bash
# Install from source
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# Install with GPU support (CUDA required)
pip install -e ".[gpu]"

# Install everything
pip install -e ".[all]"
```

### Docker Installation — التثبيت عبر Docker

```bash
# Build and run with Docker Compose
cd docker
docker-compose up -d

# The API will be available at http://localhost:8000
```

### Tesseract OCR (Optional) — محرك التعرف الضوئي

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara

# macOS
brew install tesseract tesseract-lang

# Verify installation
tesseract --version
```

---

## 🛠 Usage — الاستخدام

### Python API — واجهة برمجة بايثون

```python
from core.engine import AIFuelEngine
from core.config import AIFuelConfig

# Initialize with custom configuration
config = AIFuelConfig(
    chunk_size=512,
    chunk_overlap=50,
    language="ar",
    qdrant_url="http://localhost:6333",
)

engine = AIFuelEngine(config)

# Process a single file
result = engine.process(
    input_path="data/textbook.pdf",
    output_path="datasets/output.jsonl",
)

print(f"Processed: {result.total_chunks} chunks")
print(f"Classified: {result.classified} chunks")
print(f"Duplicates removed: {result.duplicates_removed}")
print(f"Exported: {result.exported} chunks")

# Process a directory
results = engine.process_directory(
    input_dir="data/",
    output_dir="datasets/",
    file_pattern="*.pdf",
)

# Process with specific modules only
from segmenter.segmenter import DocumentSegmenter
from classifier.keyword_router import KeywordRouter
from dedup.exact_dedup import ExactDeduplicator
from export.jsonl_exporter import JSONLExporter

# Step 1: Segment
segmenter = DocumentSegmenter(chunk_size=512, chunk_overlap=50)
chunks = segmenter.segment("raw extracted text from your document...")

# Step 2: Classify
router = KeywordRouter()
for chunk in chunks:
    result = router.classify(chunk.text, chunk.id)
    chunk.category = result.category
    chunk.confidence = result.confidence

# Step 3: Deduplicate
dedup = ExactDeduplicator()
unique_chunks = [c for c in chunks if not dedup.add(c.text, c.id).is_duplicate]

# Step 4: Export
exporter = JSONLExporter()
exporter.export(unique_chunks, "datasets/output.jsonl")
```

### CLI — سطر الأوامر

```bash
# Process a single file
ai-fuel process --input data/book.pdf --output datasets/output.jsonl

# Process with options
ai-fuel process \
  --input data/book.pdf \
  --output datasets/output.jsonl \
  --chunk-size 1024 \
  --chunk-overlap 100 \
  --language ar \
  --format jsonl \
  --no-dedup

# Process a directory
ai-fuel process-dir \
  --input-dir data/ \
  --output-dir datasets/ \
  --pattern "*.pdf" \
  --recursive

# Classify existing chunks
ai-fuel classify \
  --input datasets/chunks.jsonl \
  --output datasets/classified.jsonl \
  --method keyword

# Deduplicate a dataset
ai-fuel dedup \
  --input datasets/classified.jsonl \
  --output datasets/clean.jsonl \
  --method exact

# Export to different format
ai-fuel export \
  --input datasets/clean.jsonl \
  --output datasets/clean.parquet \
  --format parquet

# Active learning: start review session
ai-fuel review \
  --input datasets/uncertain.jsonl \
  --db data/reviews.db

# Show pipeline statistics
ai-fuel stats --db data/engine.db
```

### Using the Segmenter — استخدام المقسم

```python
from segmenter.segmenter import DocumentSegmenter

segmenter = DocumentSegmenter(
    chunk_size=512,
    chunk_overlap=50,
    respect_sentence_bounds=True,
)

chunks = segmenter.segment_by_size(
    text="Your extracted medical text goes here...",
    source_file="medical_textbook.pdf",
)

for chunk in chunks:
    print(f"[{chunk.chunk_index}] ({chunk.token_count} tokens) {chunk.text[:80]}...")
```

### Using the Classifier — استخدام المصنف

```python
from classifier.keyword_router import KeywordRouter
from classifier.embedding_classifier import EmbeddingClassifier

# Keyword-based classification
router = KeywordRouter()
result = router.classify("The patient has cardiac arrhythmia", chunk_id="c1")
print(f"Category: {result.category}")     # "cardiology"
print(f"Confidence: {result.confidence}") # e.g., 0.85

# Embedding-based classification
embedder = EmbeddingClassifier(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    qdrant_url="http://localhost:6333",
)
result = embedder.classify("The patient requires a cardiac stent")
print(f"Category: {result.category}")
print(f"Confidence: {result.confidence}")
```

### Using the Deduplicator — استخدام أداة إزالة التكرار

```python
from dedup.exact_dedup import ExactDeduplicator
from dedup.semantic_dedup import SemanticDeduplicator

# Exact deduplication
dedup = ExactDeduplicator(case_sensitive=False, strip_whitespace=True)
result = dedup.add("Cardiac arrhythmia is dangerous.", chunk_id="c1")
print(result.is_duplicate)  # False

result = dedup.add("Cardiac arrhythmia is dangerous.", chunk_id="c2")
print(result.is_duplicate)  # True
print(result.duplicate_of)  # "c1"

print(f"Unique: {dedup.unique_count} texts")

# Semantic deduplication
semantic = SemanticDeduplicator(
    similarity_threshold=0.95,
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
```

### Using the Exporter — استخدام أداة التصدير

```python
from export.jsonl_exporter import JSONLExporter
from export.parquet_exporter import ParquetExporter
from export.csv_exporter import CSVExporter
from export.excel_exporter import ExcelExporter

# JSONL export
jsonl_exporter = JSONLExporter(include_metadata=True)
jsonl_exporter.export(chunks, "datasets/output.jsonl")

# Parquet export
parquet_exporter = ParquetExporter()
parquet_exporter.export(chunks, "datasets/output.parquet")

# CSV export
csv_exporter = CSVExporter()
csv_exporter.export(chunks, "datasets/output.csv")

# Excel export
excel_exporter = ExcelExporter()
excel_exporter.export(chunks, "datasets/output.xlsx", sheet_name="Medical Data")
```
</details>

---

## 📚 Modules — الوحدات

### `core/` — Engine Core — المحرك الأساسي

| File | Description |
|------|-------------|
| `engine.py` | Main orchestration engine — coordinates all pipeline stages |
| `config.py` | Configuration management (ENV, YAML, defaults) |
| `schemas.py` | Pydantic models for TextChunk, ClassificationResult, etc. |
| `database.py` | Database interface for metadata and persistence |
| `monitoring.py` | Prometheus metrics and health checks |

### `segmenter/` — Text Segmentation — تقسيم النص

| File | Description |
|------|-------------|
| `segmenter.py` | Main DocumentSegmenter with multiple strategies |
| `strategies.py` | Fixed-size, sentence-aware, and page-aware strategies |
| `tokenizer.py` | Tokenization utilities (tiktoken wrapper) |

### `classifier/` — Text Classification — تصنيف النص

| File | Description |
|------|-------------|
| `keyword_router.py` | Fast keyword-based medical text classifier |
| `embedding_classifier.py` | Semantic classification using sentence embeddings |
| `llm_classifier.py` | LLM-assisted classification for ambiguous texts |
| `categories.py` | Medical category definitions (Arabic + English) |
| `qdrant_store.py` | Qdrant vector database interface for embeddings |

### `dedup/` — Deduplication — إزالة التكرار

| File | Description |
|------|-------------|
| `exact_dedup.py` | Exact string matching deduplication |
| `semantic_dedup.py` | Embedding-based semantic deduplication |
| `minhash_dedup.py` | MinHash LSH for large-scale approximate dedup |
| `fuzzy_dedup.py` | Fuzzy string matching for near-duplicates |

### `export/` — Data Export — تصدير البيانات

| File | Description |
|------|-------------|
| `jsonl_exporter.py` | JSON Lines format exporter |
| `parquet_exporter.py` | Apache Parquet exporter (columnar) |
| `csv_exporter.py` | CSV format exporter |
| `excel_exporter.py` | Excel (.xlsx) format exporter |
| `markdown_exporter.py` | Markdown format exporter |

### `active_learning/` — Active Learning — التعلم النشط

| File | Description |
|------|-------------|
| `review_queue.py` | Priority queue for human review |
| `feedback_store.py` | SQLite storage for review feedback |
| `sampler.py` | Uncertainty and diversity sampling strategies |
| `labeler.py` | Label management and propagation |

---

## ⚙️ Configuration — الإعدادات

### Environment Variables — متغيرات البيئة

```bash
# Pipeline settings
CHUNK_SIZE=512              # Default chunk size in tokens
CHUNK_OVERLAP=50           # Overlap between chunks
BATCH_SIZE=32              # Processing batch size
LANGUAGE=en                # Default language (en/ar)

# Storage
DB_PATH=data/engine.db     # SQLite database path
QDRANT_URL=http://localhost:6333   # Qdrant vector DB URL
REDIS_URL=redis://localhost:6379    # Redis URL (optional)

# Classification
CLASSIFICATION_METHOD=keyword      # keyword/embedding/llm
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
SIMILARITY_THRESHOLD=0.8

# Export
DEFAULT_FORMAT=jsonl       # Default export format
OUTPUT_DIR=datasets/       # Default output directory

# Logging
LOG_LEVEL=INFO             # DEBUG/INFO/WARNING/ERROR

# Monitoring
PROMETHEUS_PORT=9090       # Prometheus metrics port

# LLM API Keys (optional)
OPENAI_API_KEY=sk-...      # OpenAI API key
GOOGLE_API_KEY=...         # Google Generative AI key
```

### Configuration File — ملف الإعدادات

```yaml
# config.yaml
pipeline:
  chunk_size: 512
  chunk_overlap: 50
  batch_size: 32
  language: "ar"

storage:
  db_path: "data/engine.db"
  qdrant_url: "http://localhost:6333"

classifier:
  method: "keyword"
  embedding_model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
  similarity_threshold: 0.8

export:
  format: "jsonl"
  include_metadata: true

dedup:
  method: "exact"
  case_sensitive: false

logging:
  level: "INFO"
```

---

<details>
<summary>Historical documentation (preserved for reference)</summary>

## 🧪 Development — التطوير

### Setup Development Environment — إعداد بيئة التطوير

```bash
# Clone and install
git clone https://github.com/DR-ABDULMALEK/ai-fuel-engine.git
cd ai-fuel-engine

# Install with dev dependencies
pip install -e ".[dev]"

# Verify installation
ai-fuel --version
```

### Project Structure — هيكل المشروع

```
ai-fuel-engine/
├── core/                    # Engine core and orchestration
├── segmenter/               # Text segmentation module
├── classifier/              # Text classification module
├── dedup/                   # Deduplication module
├── export/                  # Data export module
├── active_learning/         # Active learning loop
├── tests/                   # Test suite
├── data/                    # Input data directory (gitignored)
├── datasets/                # Output datasets directory (gitignored)
├── docker/                  # Docker configuration
├── notebooks/               # Jupyter notebooks for exploration
├── .github/workflows/       # CI/CD pipelines
├── pyproject.toml           # Project metadata and config
├── requirements.txt          # Python dependencies
├── setup.py                 # Setup wrapper
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

### Code Style — أسلوب الكود

```bash
# Format code with Black
black core/ segmenter/ classifier/ dedup/ export/ active_learning/

# Lint with flake8
flake8 core/ segmenter/ classifier/ dedup/ export/ active_learning/ --max-line-length=100

# Type check with mypy
mypy core/ --ignore-missing-imports
```

---

## 🧪 Testing — الاختبار

### Running Tests — تشغيل الاختبارات

```bash
# Run all tests
pytest tests/ -v

# Run only unit tests (fast)
pytest tests/ -m unit -v

# Run integration tests
pytest tests/ -m integration -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_classifier.py -v

# Run specific test class
pytest tests/test_segmenter.py::TestSegmentBySize -v

# Run specific test
pytest tests/test_dedup.py::TestExactDeduplicatorAdd::test_add_unique_text -v
```

### Test Markers — علامات الاختبار

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Fast unit tests |
| `@pytest.mark.integration` | Slow integration tests (requires services) |
| `@pytest.mark.benchmark` | Performance benchmarks |

### Writing Tests — كتابة الاختبارات

```python
import pytest

class TestMyFeature:
    """Test suite for MyFeature."""

    def test_basic_functionality(self):
        """Test that the feature works with basic input."""
        # Arrange
        input_data = "sample text"

        # Act
        result = my_function(input_data)

        # Assert
        assert result is not None
        assert len(result) > 0

    @pytest.mark.unit
    def test_edge_case(self):
        """Test edge case handling."""
        result = my_function("")
        assert result == expected_empty_result

    @pytest.mark.integration
    def test_with_external_service(self):
        """Test integration with Qdrant."""
        # This test requires a running Qdrant instance
        result = classify_with_embeddings("medical text")
        assert result.category in valid_categories
```

---

## 🐳 Docker — النشر

### Quick Start with Docker Compose — البدء السريع مع Docker

```bash
# Start all services
cd docker
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Available Services — الخدمات المتاحة

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | Main AI Fuel Engine API |
| `qdrant` | 6333 | Vector database for embeddings |
| `redis` | 6379 | Cache and task queue |

### Build Custom Image — بناء صورة مخصصة

```bash
# Build the image
docker build -f docker/Dockerfile -t ai-fuel-engine .

# Run the container
docker run -d \
  -p 8000:8000 \
  -v ./data:/app/data \
  -v ./datasets:/app/datasets \
  -e QDRANT_URL=http://host.docker.internal:6333 \
  ai-fuel-engine
```
</details>

---

## 🤝 Contributing — المساهمة

This repository is archived. Please contribute to [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) instead.

---

## 📄 License — الرخصة

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2024 Dr. Abdulmalek

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

## 🙏 Acknowledgments — الشكر

- **Tesseract OCR** — Open-source optical character recognition engine
- **Sentence Transformers** — State-of-the-art text embeddings
- **Qdrant** — High-performance vector similarity search engine
- **Pydantic** — Data validation using Python type annotations

---

<p align="center">
  Built with ❤️ by <strong>Dr. Abdulmalek</strong><br/>
  <em>صُنع بحب بواسطة د. عبدالمالك</em>
</p>
