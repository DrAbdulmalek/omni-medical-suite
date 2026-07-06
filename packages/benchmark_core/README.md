# 🏥 Medical OCR Benchmarks / معايير تقييم OCR للوثائق الطبية

[![CI Benchmark](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions/workflows/benchmark.yml/badge.svg)](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions)
[![Nightly Benchmark](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions/workflows/nightly-benchmark.yml/badge.svg)](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions/workflows/nightly-benchmark.yml)
[![PR Benchmark](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions/workflows/pr-benchmark.yml/badge.svg)](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions/workflows/pr-benchmark.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Benchmark suite for measuring OCR quality on medical documents.
> مجموعة معايير لقياس جودة التعرف البصري على الوثائق الطبية.

---

## What It Benchmarks / ما يتم قياسه

| Metric | Description | الوصف |
|--------|-------------|-------|
| **CER** | Character Error Rate — measures character-level accuracy | معدل الخطأ في الأحرف — يقيس دقة التعرف على مستوى الحرف |
| **WER** | Word Error Rate — measures word-level accuracy | معدل الخطأ في الكلمات — يقيس الدقة على مستوى الكلمة |
| **Medical Term Accuracy** | How well medical terms (diagnoses, medications, procedures) are recognized | مدى دقة التعرف على المصطلحات الطبية (التشخيصات، الأدوية، الإجراءات) |
| **Latency** | Processing time per page in seconds | وقت المعالجة لكل صفحة بالثواني |
| **Throughput** | Pages processed per second | عدد الصفحات المعالجة في الثانية |

## Supported Engines / المحركات المدعومة

| Engine | Arabic Support | Speed | Accuracy |
|--------|---------------|-------|----------|
| **PaddleOCR** | ✅ Full | Fast | High |
| **Tesseract** | ✅ With `tesseract-ocr-ara` | Very Fast | Medium |
| **EasyOCR** | ✅ Full | Medium | Medium-High |
| **TrOCR** | ✅ With Arabic model | Slow | Very High |
| **Surya OCR** | ✅ Full | Medium | High |

## Quick Start / البدء السريع

### English / الإنجليزية

```bash
# Clone the repository
git clone https://github.com/DrAbdulmalek/medical-ocr-benchmarks.git
cd medical-ocr-benchmarks

# Install with all dependencies
pip install -e ".[dev]"

# Run benchmarks (mock mode — no real images needed)
medocr-bench --engines mock --images

# Run with real OCR engines
medocr-bench --engines paddleocr,easyocr --images

# Run unit tests
pytest tests/ -v
```

### العربية

```bash
# استنساخ المستودع
git clone https://github.com/DrAbdulmalek/medical-ocr-benchmarks.git
cd medical-ocr-benchmarks

# تثبيت مع جميع التبعيات
pip install -e ".[dev]"

# تشغيل المعايير (وضع المحاكاة — لا حاجة لصور حقيقية)
medocr-bench --engines mock --images

# تشغيل الاختبارات
pytest tests/ -v
```

## Dataset / مجموعة البيانات

The benchmark suite includes **50+ test cases** across multiple dimensions:

| Language | English | Arabic | Mixed | Total |
|----------|---------|--------|-------|-------|
| Cardiology | 6 | 6 | 3 | 15 |
| Radiology | 5 | 5 | 2 | 12 |
| Prescriptions | 5 | 5 | 2 | 12 |
| Pathology | 3 | 2 | 1 | 6 |
| Surgery Notes | 3 | 3 | 2 | 8 |
| Lab Reports | 2 | 3 | 1 | 6 |
| Discharge | 1 | 1 | 1 | 3 |

### Difficulty Levels / مستويات الصعوبة
- **Easy** (15 cases): Clean printed documents / وثائق مطبوعة نظيفة
- **Medium** (22 cases): Light noise, handwritten notes / ضوضاء خفيفة، ملاحظات مكتوبة بخط اليد
- **Hard** (13 cases): Heavy noise, cursive handwriting / ضوضاء عالية، خط يد متصل

### Noise Levels / مستويات الضوضاء
- **Clean**: Perfect quality scans / مسحات بجودة مثالية
- **Light Noise**: Minor artifacts / عيوب طفيفة
- **Moderate Noise**: Significant artifacts / عيوب ملحوظة
- **Heavy Noise**: Poor quality, degraded text / جودة رديئة، نص متدهور

## Project Structure / هيكل المشروع

```
medical-ocr-benchmarks/
├── README.md                          # This file / هذا الملف
├── pyproject.toml                     # Package configuration
├── LICENSE                            # MIT License
├── .gitignore
├── config/
│   ├── thresholds.yaml                # CI failure thresholds / أطراف الفشل
│   └── baselines.yaml                 # Baseline metric snapshots / اللقطات المرجعية
├── data/
│   ├── datasets.json                  # Index of all test cases / فهرس جميع الحالات
│   ├── english/                       # 20+ English test cases
│   │   ├── images/.gitkeep
│   │   ├── en_cardio_001.json
│   │   ├── en_radio_001.json
│   │   ├── en_rx_001.json
│   │   └── ...
│   ├── arabic/                        # 20+ Arabic test cases / ٢٠+ حالة عربية
│   │   ├── images/.gitkeep
│   │   ├── ar_cardio_001.json
│   │   ├── ar_radio_001.json
│   │   ├── ar_rx_001.json
│   │   └── ...
│   └── mixed/                         # 10+ Bilingual test cases / ١٠+ حالة ثنائية اللغة
│       ├── images/.gitkeep
│       ├── mixed_cardio_001.json
│       ├── mixed_rx_001.json
│       └── ...
├── src/benchmarks/
│   ├── __init__.py                    # Package exports
│   ├── metrics.py                     # CER, WER, medical accuracy calculation
│   ├── dataset.py                     # Dataset management & filtering
│   ├── runner.py                      # Benchmark runner & CLI
│   ├── report.py                      # Report generation (MD/JSON/HTML)
│   └── ci.py                          # CI threshold checking
├── tests/
│   ├── test_metrics.py                # 20+ metric tests
│   ├── test_dataset.py                # 15+ dataset tests
│   ├── test_ci.py                     # 15+ CI threshold tests
│   └── test_report.py                 # 10+ report tests
├── .github/workflows/
│   ├── benchmark.yml                  # GitHub Actions CI workflow
│   ├── nightly-benchmark.yml           # Nightly automated benchmarks
│   └── pr-benchmark.yml                 # PR-level quick benchmark
├── reports/
│   ├── .gitkeep                         # Placeholder for generated reports
│   ├── nightly_report.md                # Latest nightly benchmark report
│   └── nightly_results.json             # Latest nightly benchmark results
```

## How to Add New Test Cases / كيفية إضافة حالات اختبار جديدة

### English / الإنجليزية

1. Create a JSON file in `data/english/` (or `arabic/`, `mixed/`):

```json
{
  "id": "en_new_case_001",
  "language": "english",
  "specialty": "cardiology",
  "difficulty": "medium",
  "noise_level": "light_noise",
  "image_path": "data/english/images/new_case_001.png",
  "source": "real",
  "description": "Description of the test case",
  "ground_truth": "The exact text that OCR should produce"
}
```

2. Place the corresponding image in `data/english/images/`
3. Run tests to validate: `pytest tests/ -v`
4. Update `data/datasets.json` index

### العربية

1. أنشئ ملف JSON في مجلد `data/arabic/`:

```json
{
  "id": "ar_new_case_001",
  "language": "arabic",
  "specialty": "طب القلب",
  "difficulty": "medium",
  "noise_level": "light_noise",
  "image_path": "data/arabic/images/new_case_001.png",
  "source": "real",
  "description": "وصف حالة الاختبار",
  "ground_truth": "النص الدقيق الذي يجب أن ينتجه التعرف البصري"
}
```

2. ضع الصورة المقابلة في `data/arabic/images/`
3. شغّل الاختبارات: `pytest tests/ -v`

### Required Fields / الحقول المطلوبة

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (e.g., `en_cardio_007`) |
| `language` | `english`, `arabic`, or `mixed` |
| `specialty` | Medical specialty category |
| `difficulty` | `easy`, `medium`, or `hard` |
| `noise_level` | `clean`, `light_noise`, `moderate_noise`, `heavy_noise` |
| `image_path` | Path to test image |
| `source` | `synthetic`, `real`, or `contributed` |
| `description` | Human-readable description |
| `ground_truth` | Expected OCR output text |

## Nightly Benchmarks / المعايير الليلية

![Nightly Benchmark](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions/workflows/nightly-benchmark.yml/badge.svg)

A **nightly benchmark workflow** runs automatically every day at **3:00 AM UTC** (and can also be triggered manually via `workflow_dispatch`). It performs the following:

1. **Installs all dependencies** (including real OCR engines: PaddleOCR + EasyOCR)
2. **Runs full benchmarks** on English and Arabic datasets with `--check-ci` regression detection
3. **Generates reports** — produces both Markdown and JSON reports in the `reports/` directory
4. **Checks for regressions** — compares results against thresholds defined in `config/thresholds.yaml`; the workflow **fails** if any regression is detected
5. **Uploads artifacts** — stores benchmark results as GitHub Actions artifacts (retained for 30 days)
6. **Commits results** — the nightly report is automatically committed back to the repository

### PR Benchmarks / معايير طلبات السحب

![PR Benchmark](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions/workflows/pr-benchmark.yml/badge.svg)

A lightweight **PR benchmark workflow** triggers on pull requests that modify `src/`, `data/`, or `config/` files. It:

- Runs the full test suite (`pytest tests/ -v`)
- Validates dataset completeness (ensures 50+ test cases)
- Provides fast feedback without requiring heavy OCR engine installation

### Latest Reports / أحدث التقارير

Nightly benchmark results are stored in the [`reports/`](reports/) directory and also uploaded as [GitHub Actions artifacts](https://github.com/DrAbdulmalek/medical-ocr-benchmarks/actions).

---

## CI Thresholds / أطراف CI

CI thresholds define the **pass/fail boundaries** for benchmark results. They are configured in `config/thresholds.yaml` and enforced by both the nightly and CI benchmark workflows.

### How Thresholds Work / كيف تعمل الأطراف

| Check | Condition | Fail If |
|-------|-----------|---------|
| **Max CER** | Character Error Rate | `CER > max_cer` |
| **Max WER** | Word Error Rate | `WER > max_wer` |
| **Min Medical Accuracy** | Medical term recognition | `accuracy < min_medical_accuracy` |
| **Min Throughput** | Processing speed | `throughput < min_throughput` |
| **Max Latency** | Per-page processing time | `latency > max_latency` |

Thresholds can be set **globally** (apply to all engines) or **per-engine** (override global for specific engines):

```yaml
global:
  max_cer: 0.15               # All engines: fail if CER > 15%
  max_wer: 0.25               # All engines: fail if WER > 25%
  min_medical_accuracy: 0.80  # All engines: fail if accuracy < 80%

engines:
  paddleocr:                   # PaddleOCR-specific (stricter)
    max_cer: 0.12              # Fail if CER > 12%
    max_wer: 0.22              # Fail if WER > 22%
  easyocr:                     # EasyOCR-specific
    max_cer: 0.18              # Fail if CER > 18%
```

### Baseline Regression Detection / كشف التراجع

In addition to absolute thresholds, baselines in `config/baselines.yaml` track expected performance. CI will flag a **5% or greater regression** from baseline values.

---

## Contributing Test Cases / المساهمة بحالات اختبار

We welcome community contributions of new medical OCR test cases! Here's how to add one:

### JSON Template / قالب JSON

Copy this template and place it in the appropriate language directory (`data/english/`, `data/arabic/`, or `data/mixed/`):

```json
{
  "id": "en_cardio_007",
  "language": "english",
  "specialty": "cardiology",
  "difficulty": "medium",
  "noise_level": "light_noise",
  "image_path": "data/english/images/en_cardio_007.png",
  "source": "contributed",
  "description": "Cardiology discharge summary with handwritten annotations",
  "ground_truth": "Patient Name: John Doe\nDiagnosis: Acute Myocardial Infarction (AMI)\nMedications: Aspirin 325mg, Clopidogrel 75mg\nFollow-up: 2 weeks"
}
```

### Steps / الخطوات

1. **Create the JSON file** in `data/<language>/` following the template above
2. **Add the test image** to `data/<language>/images/`
3. **Validate** your case: `pytest tests/test_dataset.py -v`
4. **Update the index** (optional): `data/datasets.json` is auto-rebuilt on load
5. **Submit a PR** — the PR benchmark workflow will automatically validate your contribution

### Required Fields / الحقول المطلوبة

| Field | Required | Description | مثال |
|-------|----------|-------------|------|
| `id` | ✅ | Unique identifier | `en_cardio_007` |
| `language` | ✅ | `english`, `arabic`, or `mixed` | `arabic` |
| `specialty` | ✅ | Medical specialty category | `cardiology` |
| `difficulty` | ✅ | `easy`, `medium`, or `hard` | `medium` |
| `noise_level` | ✅ | `clean`, `light_noise`, `moderate_noise`, `heavy_noise` | `light_noise` |
| `image_path` | ✅ | Path to the test image | `data/arabic/images/ar_rx_006.png` |
| `source` | ✅ | `synthetic`, `real`, or `contributed` | `contributed` |
| `description` | ✅ | Human-readable description | "Prescription with doctor's notes" |
| `ground_truth` | ✅ | Exact expected OCR output | Full text content |

---

## Pre-OCR Normalization Impact / أثر المعالجة المسبقة

The [Scanner Fixer](https://github.com/DrAbdulmalek/scanner-fixer) tool serves as the official **Pre-OCR Normalization Layer** for the ecosystem. Benchmarking its impact is critical for measuring the full pipeline quality.

### Before vs After Preprocessing / قبل وبعد المعالجة المسبقة

| Metric | Raw Scan (No Preprocessing) | After Scanner Fixer | Impact |
|--------|----------------------------|--------------------|--------|
| **Printed CER** | 6-8% | 3-4% | ~40-50% CER reduction |
| **Handwritten CER** | 15-18% | 10-13% | ~25-30% CER reduction |
| **WER (Overall)** | 12-15% | 7-9% | ~35-40% WER reduction |
| **Medical Term Accuracy** | ~82% | ~91% | ~9pp improvement |

### How to Benchmark Preprocessing Impact / كيف تقيس أثر المعالجة المسبقة

```bash
# 1. Benchmark WITHOUT preprocessing (raw scans)
medocr-bench --engines paddleocr --images data/raw_scans/

# 2. Apply Scanner Fixer to all images
python -m scanner_fixer --input data/raw_scans/ --output data/preprocessed/ --batch

# 3. Benchmark WITH preprocessing
medocr-bench --engines paddleocr --images data/preprocessed/

# 4. Compare reports
diff reports/benchmark_raw.md reports/benchmark_preprocessed.md
```

> 💡 **Recommendation**: Always include a preprocessing step in your pipeline. Scanner Fixer reduces the effective CER by correcting skew and removing scan borders, which are among the top causes of OCR errors on medical documents.

## CI Integration / تكامل CI

### GitHub Actions

The repository includes three CI workflows:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **benchmark.yml** | Push / PR | Full CI — tests, benchmarks, threshold checks, PR comments |
| **nightly-benchmark.yml** | Daily at 3 AM UTC / Manual | Full benchmarks with real OCR engines + report generation + artifact upload |
| **pr-benchmark.yml** | PR on `src/`, `data/`, `config/` | Quick validation — tests + dataset completeness |

### Threshold Configuration / إعداد الأطراف

Edit `config/thresholds.yaml` to customize CI failure criteria (see [CI Thresholds](#ci-thresholds--أطراف-ci) above for full details).

## Python API / واجهة البرمجة

### Calculate Metrics / حساب المقاييس

```python
from benchmarks.metrics import calculate_all_metrics

reference = "Patient has hypertension and angina pectoris"
hypothesis = "Patient has hypertension and angina pectoris"  # OCR output

metrics = calculate_all_metrics(reference, hypothesis)
print(f"CER: {metrics.cer:.4f}")
print(f"WER: {metrics.wer:.4f}")
print(f"Medical Accuracy: {metrics.medical_accuracy:.1%}")
```

### Load and Filter Dataset / تحميل وتصفية البيانات

```python
from benchmarks.dataset import DatasetManager

ds = DatasetManager("data")
ds.load()

# Filter cases
english_cardio = ds.filter(language="english", specialty="cardiology")
hard_cases = ds.filter(difficulty="hard")
print(f"English cardiology cases: {len(english_cardio)}")

# Get statistics
stats = ds.get_stats()
print(f"Total cases: {stats.total_cases}")
print(f"Languages: {stats.languages}")
```

### Run Benchmarks / تشغيل المعايير

```python
from benchmarks.runner import BenchmarkRunner

runner = BenchmarkRunner(
    engines=["mock"],       # or ["paddleocr", "easyocr"]
    check_ci=True,
)

report = runner.run(
    language="english",
    difficulty="easy",
    formats=["markdown"],
)
print(report.summary)
```

### Check CI Thresholds / فحص أطراف CI

```python
from benchmarks.ci import ThresholdChecker
from benchmarks.report import EngineResult

checker = ThresholdChecker()
result = EngineResult(
    engine_name="my_engine",
    avg_cer=0.08,
    avg_wer=0.15,
    avg_medical_accuracy=0.90,
)

ci_result = checker.check({"my_engine": result})
print(ci_result.passed)  # True or False
print(ci_result.summary)
```

## Report Formats / تنسيقات التقارير

| Format | Output | Use Case |
|--------|--------|----------|
| **JSON** | `reports/benchmark_*.json` | Machine-readable, API consumption |
| **Markdown** | `reports/benchmark_*.md` | Git diffs, documentation |
| **HTML** | `reports/benchmark_*.html` | Interactive viewing, sharing |

All reports include:
- Engine comparison table / جدول مقارنة المحركات
- Per-language breakdown / تفصيل حسب اللغة
- Per-specialty breakdown / تفصيل حسب التخصص
- Per-difficulty breakdown / تفصيل حسب الصعوبة
- CI threshold warnings / تحذيرات أطراف CI

## Development / التطوير

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v --cov=benchmarks

# Run specific test module
pytest tests/test_metrics.py -v

# Run linting
ruff check src/benchmarks/

# Type checking
mypy src/benchmarks/
```

## Acknowledgments / شكر وتقدير

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — Primary OCR engine
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) — Multi-language OCR
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — Open-source OCR
- [TrOCR](https://huggingface.co/microsoft/trocr) — Transformer-based OCR
- [Surya OCR](https://github.com/VikParuchuri/surya) — Multilingual OCR

## License / الترخيص

This project is licensed under the [MIT License](LICENSE).

هذا المشروع مرخص بموجب [رخصة MIT](LICENSE).
