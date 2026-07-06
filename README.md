<!-- STATUS: ARCHIVED -->
<div align="center">

| Status | Type | Absorbed Into |
|--------|------|---------------|
| <img src="https://img.shields.io/badge/status-archived-inactive" alt="Archived" /> | NLP Module | [omni-medical-suite/backend/nlp/](https://github.com/DrAbdulmalek/omni-medical-suite/tree/main/backend/nlp) |

</div>

> **Archived on 2026-06-28** — Code preserved for reference. All development continues in **[omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)**.

---

# BilingualExtractor

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Arabic-English Medical Parallel Corpus Extraction System**

BilingualExtractor is a comprehensive system designed to extract and process **Arabic-English parallel medical terminology** from scanned medical textbooks and documents. It combines advanced NLP techniques with domain-specific medical knowledge to create high-quality bilingual corpora for research and AI training.

## ✨ Features

### 📖 Core Extraction Modules
- **TextPreprocessor**: Arabic text normalization, OCR error correction, and text cleaning
- **PatternExtractor**: Detects and extracts bilingual (Arabic-English) term pairs
- **MorphologicalAnalyzer**: Categorizes medical terms by domain (Anatomy, Pharmacology, Pathology, etc.)
- **StatisticalFilter**: Confidence scoring, deduplication, and quality filtering

### 🔧 Export Capabilities
- **CSV** format for spreadsheet analysis
- **TSV** format for tab-separated data
- **JSON** format for API integration
- **Excel** (.xlsx) format for Microsoft Office
- **Database** integration (PostgreSQL support)

### 🌐 Language Support
- **Arabic** (Modern Standard + Dialectal variants)
  - Egyptian Arabic
  - Levantine Arabic
  - Gulf Arabic
- **English** (Medical terminology)
- **Bilingual** pair extraction and alignment

### 📚 Medical Domain Coverage
- Comprehensive medical terminology dictionaries
- Historical terminology evolution tracking
- Domain-specific categorization (20+ medical specialties)

### 🛠️ Developer Tools
- **CLI Interface**: Batch processing from command line
- **Jupyter Notebook**: Interactive Google Colab notebook for exploration
- **Database Schema**: PostgreSQL schema for corpus management
- **Bilingual Documentation**: Arabic + English documentation

## 🚀 Quick Start

### Installation

#### From PyPI (Recommended)
```bash
pip install bilingual-extractor
```

#### From Source
```bash
git clone https://github.com/DrAbdulmalek/bilingual-extractor.git
cd bilingual-extractor
pip install -e .
```

### Basic Usage

#### Command Line Interface
```bash
# Extract terms from a PDF file
bilingual-extract --input medical_book.pdf --output extracted_terms.csv

# Process a directory of files
bilingual-extract --input ./documents/ --output ./results/ --format json

# Use GPU acceleration (requires torch)
pip install bilingual-extractor[gpu]
bilingual-extract --input document.pdf --gpu
```

#### Python API
```python
from term_extractor import TermExtractor

# Initialize extractor
extractor = TermExtractor()

# Extract terms from text
text = "... medical text ..."
terms = extractor.extract(text)

# Save to CSV
terms.to_csv("output.csv")

# Get bilingual pairs
bilingual_pairs = extractor.get_bilingual_pairs()
```

## 📦 Requirements

### Core Dependencies
- Python 3.8+
- sentence-transformers >= 2.2.0
- scipy >= 1.9.0
- pandas >= 1.5.0
- openpyxl >= 3.0.0

### Optional Dependencies
- **GPU Support**: torch >= 2.0.0, transformers >= 4.25.0
- **Development**: pytest, pytest-cov, black, flake8

See [requirements.txt](requirements.txt) for full dependency list.

## 🏗️ Project Structure

```
bilingual-extractor/
├── term_extractor/          # Main extraction modules
│   ├── __init__.py
│   ├── text_preprocessor.py
│   ├── pattern_extractor.py
│   ├── morphological_analyzer.py
│   └── statistical_filter.py
├── database/                # Database schema and migrations
├── docs/                    # Documentation
├── notebooks/               # Jupyter notebooks
├── templates/               # Export templates
├── setup.py
├── requirements.txt
└── README.md
```

## 📊 Use Cases

### 1. Medical Research
- Build parallel corpora for medical NLP research
- Analyze terminology usage across languages
- Track evolution of medical terms

### 2. AI Training
- Create training data for medical translation models
- Fine-tune language models on medical domain
- Improve OCR accuracy for medical documents

### 3. Education
- Create bilingual medical glossaries
- Develop educational materials
- Support medical students learning terminology

### 4. Healthcare Applications
- Build medical chatbots
- Create patient education materials
- Develop clinical decision support systems

## 🎯 Roadmap

### ✅ What Was Built (v1.0.0)
- Pattern-based term extraction
- Arabic text normalization
- OCR error correction
- Bilingual pair detection
- Medical domain categorization
- Multiple export formats
- CLI interface
- Jupyter notebook
- Database schema

## 🤝 Contributing

This repository is archived. Please contribute to [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) instead.

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Medical terminology dictionaries from various open sources
- NLP research community
- Open source contributors

## 📞 Contact

For questions, please use [omni-medical-suite Discussions](https://github.com/DrAbdulmalek/omni-medical-suite/discussions)

---

**© 2026 BilingualExtractor Team**

*Built with ❤️ for the medical NLP community*
