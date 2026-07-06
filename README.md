<!-- ARCHIVE BANNER - AUTO-GENERATED -->
<div align="center">

# ⚠️ This repository has been archived

**Post-processor merged into omni-medical-suite/backend/postprocessor/**

This project has been consolidated into the unified **[omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)** monorepo.

All active development, bug fixes, and new features continue there.

</div>

---

> **Archived on: 2026-06-28** | **Active project:** [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)

---

> **⚠️ هذا المستودع مؤرشف. استخدم [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) بدلاً منه.**
> **⚠️ ARCHIVED: This repository is archived. Use [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) instead.**

---

# Medical OCR Postprocessor

> معالج ما بعد OCR للأ نصوص الطبية — Post-processing engine for medical OCR results

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-medical--ocr--postprocessor-orange.svg)](https://pypi.org/project/medical-ocr-postprocessor/)

## التثبيت / Installation

```bash
pip install medical-ocr-postprocessor
```

### تثبيت مع الإضافات / Install with extras

```bash
# Development tools (testing, linting, formatting)
pip install medical-ocr-postprocessor[dev]

# Monitoring (Prometheus metrics)
pip install medical-ocr-postprocessor[monitoring]

# Production (Celery + Redis workers)
pip install medical-ocr-postprocessor[production]

# All extras
pip install medical-ocr-postprocessor[all]
```

---

## البدء السريع / Quick Start

### تصحيح كلمة واحدة / Correct a single word

```python
from medical_ocr_postprocessor import PostProcessor

pp = PostProcessor(confidence_threshold=0.85)

# تصحيح كلمة عربية / Correct an Arabic word
result = pp.correct_word("متفورمن", ocr_confidence=0.6)
print(f"Original: {result.original}")    # متفورمن
print(f"Corrected: {result.corrected}")  # ميتفورمين
print(f"Confidence: {result.confidence}")  # 0.83
print(f"Source: {result.source}")        # fuzzy_match
```

### تصحيح مجموعة كلمات / Batch correct words

```python
words = ["سكري", "ضغط الدم", "متفورمن", "ارتفاع الضغط"]
results = pp.batch_correct(words)

for r in results:
    status = "✏️" if r.is_modified else "✅"
    print(f"{status} {r.original} → {r.corrected} ({r.confidence:.0%})")
```

### التحقق من النص العربي / Validate Arabic text

```python
validation = pp.validate_arabic("مريض يعاني من السكري وارتفاع ضغط الدم")
print(f"Valid: {validation['is_valid']}")
print(f"Word count: {validation['metrics']['word_count']}")
print(f"Arabic ratio: {validation['metrics']['arabic_ratio']:.1%}")
print(f"Issues: {validation['issues']}")
```

### التحقق من المصطلحات الطبية / Validate medical terms

```python
medical = pp.validate_medical_terms("مريض يعاني من السكري النوع الثاني")
print(f"Coverage: {medical['coverage']:.1%}")
print(f"Found terms: {medical['found_terms']}")
print(f"Suggestions: {medical['suggestions']}")
```

---

## واجهة سطر الأوامر / CLI

### تصحيح ملف / Correct a file

```bash
medical-ocr-postprocess correct \
    --input ocr_results.json \
    --output corrected.json \
    --confidence 0.85
```

Input JSON format (supported):

```json
{
  "words": ["سكري", "متفورمن", "ضغط"],
  "confidences": [0.95, 0.6, 0.9],
  "text": "سكري متفورمن ضغط"
}
```

Or simple list:

```json
["سكري", "متفورمن", "ضغط"]
```

### المعالجة الدفعية / Batch processing

```bash
# معالجة دفعة واحدة / Single-worker batch
medical-ocr-postprocess batch \
    --input-dir pages/ \
    --output-dir output/ \
    --confidence 0.85

# معالجة متعددة العمال / Multi-worker batch
medical-ocr-postprocess batch \
    --input-dir backlog/ \
    --output-dir processed/ \
    --workers 4 \
    --confidence 0.85 \
    --pattern "*.json"
```

### التحقق / Validate

```bash
medical-ocr-postprocess validate \
    --text "مستند طبي يحتوي على تشخيص السكري" \
    --lang ar \
    --check-terms \
    --output validation_report.json
```

---

## المقارنة بين الأوضاع / Mode Comparison

| الميزة | الوضع التفاعلي (Interactive) | الوضع الدفعي (Batch) |
|--------|---------------------------|-------------------|
| **الاستخدام** | ملف واحد أو كلمات قليلة | آلاف الملفات |
| **مراجعة بشرية** | نعم — كل كلمة | لا — تلقائي بالكامل |
| **سرعة المعالجة** | بطيئة (بسبب الانتظار) | سريعة (متوازية) |
| **حد الثقة** | قابل للتعديل لكل كلمة | عتبة موحدة لكل الدفعة |
| **إشارات المراجعة** | فورية | ملف منفصل `flagged/` |
| **العمال المتوازيين** | 1 | 1-8+ |
| **مناسب لـ** | جودة عالية، حجم صغير | حجم كبير، جودة مقبولة |
| **الأمر** | `medical-ocr-postprocess correct` | `medical-ocr-postprocess batch` |

---

## ملفات الدفعية / Batch Output Structure

```
output/
├── page_001.json          # Corrected results
├── page_002.json
├── page_003.json
├── flagged/               # Low-confidence items for review
│   ├── page_002.json      # Words below confidence threshold
│   └── ...
└── reports/
    └── batch_summary.json # Aggregate metrics
```

---

## ملفات القاموس / Dictionary Files

### تحميل قاموس مخصص / Load custom dictionary

```python
# من ملف / From file (one term per line)
pp.load_medical_terms_from_file("custom_medical_terms.txt")

# برمجياً / Programmatically
pp.add_medical_terms(["مصطلح1", "مصطلح2", "term3"])
```

### تنسيق ملف القاموس / Dictionary file format

```text
# Medical terms dictionary / قاموس المصطلحات الطبية
# Lines starting with # are comments
سكري
ضغط الدم
ميتفورمين
أملوديبين
diabetes
hypertension
```

---

## الملفات الشخصية للقياس / Scale Profiles

### عامل واحد / Single-Worker Profile

```
مناسب لـ / Suitable for:
  - أقل من 100 صفحة / < 100 pages
  - المعالجة اليومية / Daily processing
  - التطوير والاختبار / Development & testing

الأداء / Performance:
  - السرعة: ~50-100 صفحة/دقيقة / ~50-100 pages/min
  - الذاكرة: ~200 ميغابايت / ~200 MB RAM
  - الاستخدام / Usage: --workers 1 (default)
```

### عمال متعددون / Multi-Worker Profile

```
مناسب لـ / Suitable for:
  - 100-10,000+ صفحة / 100-10,000+ pages
  - المعالجة المجمعة للمستندات / Bulk document processing
  - البيئات الإنتاجية / Production environments

الأداء / Performance:
  - السرعة: ~200-500 صفحة/دقيقة لكل عامل / ~200-500 pages/min per worker
  - الذاكرة: ~200 ميغابايت لكل عامل / ~200 MB RAM per worker
  - الاستخدام / Usage: --workers 4 (or CPU cores)

تثبيت / Installation:
  pip install medical-ocr-postprocessor[production]
```

---

## دليل استنزاف القائمة / Queue Draining Guide

عند وجود تراكم كبير من الملفات المنتظرة / When there's a large backlog:

### الخطوة 1: تقييم حجم التراكم / Assess backlog size

```bash
find backlog/ -name "*.json" | wc -l
```

### الخطوة 2: اختيار عدد العمال / Choose worker count

| حجم التراكم / Backlog Size | العمال / Workers | الوقت المتوقع / Est. Time |
|---------------------------|-----------------|--------------------------|
| < 100 ملف | 1 | < 2 دقيقة |
| 100-500 ملف | 2-4 | 2-10 دقائق |
| 500-2,000 ملف | 4-6 | 10-30 دقيقة |
| 2,000-10,000 ملف | 6-8 | 30 دقيقة - ساعتان |
| > 10,000 ملف | 8+ | ساعتان+ (قسّم إلى دفعات) |

### الخطوة 3: التشغيل / Run

```bash
medical-ocr-postprocess batch \
    --input-dir backlog/ \
    --output-dir processed/ \
    --workers 8 \
    --confidence 0.85 \
    --pattern "*.json"
```

### الخطوة 4: مراجعة العناصر المعلّمة / Review flagged items

```bash
# Check how many items need review
ls processed/flagged/ | wc -l

# Review flagged items interactively
medical-ocr-postprocess correct \
    --input processed/flagged/ \
    --output processed/reviewed/
```

### الخطوة 5: فحص التقرير / Check summary report

```bash
cat processed/reports/batch_summary.json
```

---

## مقاييس التراكم / Backlog Metrics

| المقياس / Metric | الوصف / Description | الهدف / Target |
|-----------------|--------------------|--------------|
| `queue_depth` | عدد الملفات المنتظرة / Pending files | 0 (فارغ / empty) |
| `processing_rate` | ملفات/دقيقة / Files per minute | > 100 |
| `avg_latency` | متوسط وقت الانتظار / Avg wait time | < 5 دقائق |
| `error_rate` | نسبة الأخطاء / Error percentage | < 1% |
| `auto_accept_rate` | نسبة القبول التلقائي / Auto-accept rate | > 80% |
| `correction_rate` | نسبة التصحيحات / Corrections rate | 5-20% |

---

## التكامل / Integration

### مع medical-ocr-trainer

```python
# After OCR produces results, pipe to postprocessor
from medical_ocr_postprocessor import PostProcessor

def process_ocr_results(ocr_output: dict) -> dict:
    pp = PostProcessor(confidence_threshold=0.85)
    words = [w["text"] for w in ocr_output["words"]]
    confidences = [w.get("confidence", 0.5) for w in ocr_output["words"]]

    results = pp.batch_correct(words, confidences)

    return {
        "corrected_words": [r.corrected for r in results],
        "corrections": [r.to_dict() for r in results],
        "stats": pp.get_stats(),
    }
```

### مع medical-handwriting-ocr

```python
# Integrate with handwriting OCR API response
import requests
from medical_ocr_postprocessor import PostProcessor

pp = PostProcessor()

def process_handwriting(image_path: str) -> dict:
    # Send to handwriting OCR service
    response = requests.post(
        "http://localhost:8000/api/ocr",
        files={"image": open(image_path, "rb")},
    )
    ocr_data = response.json()

    # Post-process results
    words = [r["text"] for r in ocr_data.get("results", [])]
    corrected = pp.batch_correct(words)

    return {
        "original": words,
        "corrected": [r.corrected for r in corrected],
        "confidence": [r.confidence for r in corrected],
        "needs_review": [r.confidence < 0.85 for r in corrected],
    }
```

---

## التطوير / Development

```bash
# Clone the repository
git clone https://github.com/DrAbdulmalek/medical-ocr-postprocessor.git
cd medical-ocr-postprocessor

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check src/
black --check src/

# Format code
black src/
ruff check --fix src/
```

---

## هيكل المشروع / Project Structure

```
medical-ocr-postprocessor/
├── pyproject.toml                    # Package configuration
├── README.md                         # This file
├── LICENSE                           # MIT License
├── .gitignore
├── src/
│   └── medical_ocr_postprocessor/
│       ├── __init__.py               # Package version & exports
│       ├── core.py                   # PostProcessor class
│       ├── batch.py                  # BatchProcessor class
│       └── cli.py                    # CLI interface
└── tests/
    └── test_core.py                  # Unit tests
```

---

## الترخيص / License

MIT License — see [LICENSE](LICENSE) file.

---

## الشكر / Acknowledgments

- [rapidfuzz](https://github.com/maxbachmann/RapidFuzz) — Fast fuzzy string matching
- [python-Levenshtein](https://github.com/ztane/python-Levenshtein) — Levenshtein distance
- Part of the [Omni Medical Suite](https://github.com/DrAbdulmalek) ecosystem
