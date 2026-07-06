# Architecture — Omni Medical OCR Pipeline

## System Overview

The Omni Medical OCR Pipeline is a comprehensive, multi-engine Arabic medical OCR system that combines four OCR engines (Tesseract, EasyOCR, PaddleOCR, and TrOCR) with weighted ensemble voting, Arabic spell checking, and a domain-specific medical dictionary to achieve production-grade accuracy on scanned Arabic medical documents.

**Author:** DrAbdulmalek  
**License:** MIT  
**Version:** 0.1.0

---

## 4-Layer Architecture

The system follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 4: Presentation                     │
│                  Desktop GUI (Tkinter)                        │
│         Arabic UI · Image Preview · Dictionary Editor         │
├─────────────────────────────────────────────────────────────┤
│                    Layer 3: Postprocessing                    │
│            Medical Text Cleaner · Arabic Normalizer           │
│         Spell Checker · Dictionary Corrections · Fuzzy Match  │
├─────────────────────────────────────────────────────────────┤
│                    Layer 2: OCR Engines                       │
│     Tesseract  ·  EasyOCR  ·  PaddleOCR  ·  TrOCR             │
│              Ensemble Weighted Voting                        │
├─────────────────────────────────────────────────────────────┤
│                    Layer 1: Preprocessing                     │
│     Image Loading · Grayscale · Binarize · Deskew · Crop     │
│              Resolution Enhancement                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Diagram

```
                         ┌──────────────┐
                         │  Desktop App │
                         │  (Tkinter)   │
                         └──────┬───────┘
                                │
                    ┌───────────┴───────────┐
                    │    OCR Pipeline       │
                    │   (Core Orchestrator) │
                    └───┬───────┬───────┬───┘
                        │       │       │
              ┌─────────┘       │       └─────────┐
              ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │Preprocessing │  │  OCR Engines │  │Postprocessing│
    │              │  │              │  │              │
    │ · Grayscale  │  │ · Tesseract  │  │ · Text       │
    │ · Binarize   │  │ · EasyOCR    │  │   Normalizer │
    │ · Deskew     │  │ · PaddleOCR  │  │ · Medical    │
    │ · Enhance    │  │ · TrOCR      │  │   Cleaner    │
    │ · Crop       │  │ · Ensemble   │  │ · Spell      │
    └──────────────┘  └──────┬───────┘  │   Checker    │
                             │          └──────┬───────┘
                    ┌────────┴────────┐         │
                    │  Ensemble       │         │
                    │  Weighted Vote  │         │
                    └─────────────────┘         │
                                                │
                              ┌─────────────────┴──────────┐
                              │      Data Layer            │
                              │                            │
                              │  · Arabic Medical Dict     │
                              │  · Configuration Files     │
                              │  · Model Cache             │
                              │  · Ground Truth Bridge     │
                              └────────────────────────────┘
```

---

## Data Flow

```
Input Image (PNG/PDF)
        │
        ▼
┌───────────────────┐
│   Preprocessing    │  · Load image
│                    │  · Convert to grayscale
│                    │  · Apply binarization
│                    │  · Deskew if needed
│                    │  · Enhance resolution
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│   OCR Engines     │  · Run all 4 engines in parallel
│   (Parallel)      │  · Each returns text + confidence
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│   Ensemble Merge  │  · Weighted voting per word
│                    │  · Confidence-based selection
│                    │  · Conflict resolution
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  Spell Checking   │  · Dictionary lookup (270+ entries)
│                    │  · Phrase-level corrections
│                    │  · Regex pattern matching
│                    │  · Fuzzy matching (Levenshtein)
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│   Postprocessing  │  · Arabic text normalization
│                    │  · Medical data extraction
│                    │  · Structured output formatting
└───────┬───────────┘
        │
        ▼
   Clean Structured Text / JSON
```

---

## Directory Structure

```
omni-medical-ocr-pipeline/
├── config/                 # Configuration files
│   └── settings.json       # Runtime settings
├── data/                   # Data files
│   └── arabic_medical_dict.json   # Medical correction dictionary
├── desktop/                # Desktop GUI application
│   ├── __init__.py
│   └── app.py              # Main Tkinter application
├── docs/                   # Documentation
│   └── ARCHITECTURE.md     # This file
├── ground_truth_bridge/    # Ground truth evaluation bridge
├── models/                 # Cached ML models (git-ignored)
├── src/                    # Source code
│   ├── __init__.py
│   ├── core/               # Pipeline orchestrator
│   │   └── pipeline.py     # Main OCR pipeline class
│   ├── engines/            # OCR engine wrappers
│   │   ├── tesseract.py
│   │   ├── easyocr.py
│   │   ├── paddleocr.py
│   │   ├── trocr.py
│   │   └── ensemble.py     # Multi-engine fusion
│   ├── postprocessing/     # Text postprocessing
│   │   ├── __init__.py
│   │   ├── medical_text_cleaner.py
│   │   └── text_normalizer.py
│   ├── preprocessing/      # Image preprocessing
│   │   ├── __init__.py
│   │   └── image_processor.py
│   ├── spellcheck/         # Spell checking module
│   │   ├── __init__.py
│   │   ├── dictionary.py
│   │   ├── fuzzy.py
│   │   └── rules.py
│   └── utils/              # Shared utilities
│       └── __init__.py
├── tests/                  # Test suite
│   ├── __init__.py
│   └── test_pipeline.py    # Comprehensive tests
├── .gitignore
├── LICENSE                 # MIT License
└── README.md
```

---

## Engine Comparison

| Engine     | Speed   | Arabic Quality | GPU Required | Notes                         |
|------------|---------|----------------|--------------|-------------------------------|
| Tesseract  | Fast    | Medium         | No           | Wide language support, C++    |
| EasyOCR    | Medium  | Good           | Optional     | PyTorch-based, 80+ languages  |
| PaddleOCR  | Medium  | Good           | Optional     | Excellent for printed text    |
| TrOCR      | Slow    | Excellent      | Yes          | Transformer-based, best accuracy |
| Ensemble   | Slow    | Best           | Varies       | Weighted voting from all engines |

### Ensemble Strategy

The ensemble uses **confidence-weighted voting** at the word level:

1. Each engine produces text with per-word confidence scores.
2. For each word position, votes are collected from all engines.
3. The word with the highest weighted confidence sum wins.
4. If no engine exceeds the confidence threshold, the word is flagged for review.

---

## Postprocessing Pipeline

### Arabic Text Normalizer
- **Alef normalization:** أ, إ, آ → ا
- **Taa marbuta:** Optional ة → ه conversion
- **Alef maqsura:** ى → ي
- **Diacritics removal:** All tashkeel characters ( configurable)
- **Tatweel removal:** Kashida characters
- **Encoding fixes:** 270+ known OCR confusion patterns
- **Whitespace normalization:** Collapse multiple spaces
- **Numeral conversion:** Western → Eastern Arabic digits (optional)

### Medical Text Cleaner
- **OCR artifact removal:** Page numbers, headers, footers
- **Dictionary corrections:** Three tiers (phrases → words → regex)
- **Medication extraction:** Drug name, dosage, frequency parsing
- **Date extraction:** Multiple Arabic and Western date formats
- **Table parsing:** Detect and parse tabular structures
- **Structured output:** JSON with sections, medications, dates

### Spell Checker
- **Dictionary lookup:** 270+ Arabic medical term corrections
- **Phrase matching:** Multi-word phrase corrections (longest match first)
- **Regex patterns:** 25+ regex-based correction rules
- **Fuzzy matching:** Levenshtein distance for unknown errors

---

## Deployment Options

### 1. Desktop Application (Current)
```bash
# Run the Tkinter desktop app
python -m desktop.app
```
- Standalone, no server required
- Arabic-language UI
- All features accessible via tabs

### 2. Command-Line Interface
```bash
# Process a single image
python -m src.core.pipeline --input image.png --engine ensemble

# Process a directory
python -m src.core.pipeline --input ./scans/ --output results.json
```

### 3. REST API (Future)
```bash
# Start the API server
python -m src.core.api --host 0.0.0.0 --port 8000

# Process via HTTP
curl -X POST http://localhost:8000/ocr \
  -F "file=@medical_report.png" \
  -F "engine=ensemble"
```

### 4. Docker Deployment (Future)
```bash
docker build -t omni-medical-ocr .
docker run -p 8000:8000 omni-medical-ocr
```

---

## Configuration

Settings are stored in `config/settings.json`:

```json
{
  "ocr_engine": "ensemble",
  "language": "ara",
  "confidence_threshold": 70.0,
  "auto_correct": true,
  "theme": "clam",
  "model_cache_path": "./models"
}
```

---

## Key Design Decisions

1. **Modular architecture:** Each OCR engine is a separate module, making it easy to add or replace engines.

2. **Ensemble-first approach:** Multi-engine fusion provides significantly better accuracy than any single engine for Arabic medical text.

3. **Dictionary-driven corrections:** The 270+ entry medical dictionary captures domain-specific OCR errors that generic spell checkers cannot handle.

4. **Configurable pipeline:** Every step (preprocessing, engine selection, postprocessing) can be configured independently.

5. **Arabic-first design:** All text handling, normalization, and UI are designed specifically for RTL Arabic medical documents.

6. **Graceful degradation:** The system works with any subset of installed OCR engines and falls back to available components.