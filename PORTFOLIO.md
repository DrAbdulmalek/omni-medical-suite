# Dr. Abdulmalek — Project Portfolio

> **Medical Document Intelligence Ecosystem**
> Unified architecture for Arabic/English medical OCR, NLP, and AI-powered document processing.
> 
> **Last Updated**: June 2026 | **Restructuring Status**: Phase 4 Complete ✅

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PLATFORM LAYER                                   │
│  omni-medical-suite (Main Platform — Monorepo)                      │
│  Next.js 16 + FastAPI + Celery + Redis + Qdrant                     │
│  ✅ Production env templates, secrets generator, pre-deploy checks    │
└──────────┬──────────────────────────────────┬───────────────────────┘
           │                                  │
┌──────────▼──────────┐        ┌──────────────▼──────────────────────┐
│  APPLICATION LAYER   │        │  CORE ENGINES LAYER                │
│                      │        │                                      │
│  medical-handwriting │        │  medical-ocr-postprocessor v2.2.0   │
│  -ocr (Production)   │───────▶│  ✅ Installable package (pip)        │
│  ✅ Postprocessor     │        │  ✅ Stable API: correct_text(),      │
│    integration       │        │     mask_phi(), batch_process()      │
│  medical-ocr-trainer │        │     mask_phi(), batch_process()      │
│  (Evaluation + Data) │───────▶│  ✅ 56 golden tests + benchmarks    │
│  ✅ CER/WER metrics  │        │  ✅ GitHub Actions CI/CD            │
│  ✅ Benchmark suite   │        │                                      │
└──────────┬──────────┘        └──────────────┬──────────────────────┘
           │                                  │
┌──────────▼──────────┐        ┌──────────────▼──────────────────────┐
│  DEPLOYMENT LAYER   │        │  BENCHMARKS LAYER (NEW)              │
│                      │        │                                      │
│  medical-ocr-trainer │        │  medical-ocr-benchmarks v1.0.0       │
│  -hf (HF Space)      │        │  ✅ CER, WER, Medical Term Accuracy  │
│                      │        │  ✅ Latency profiling (p95/p99)      │
└──────────┬──────────┘        │  ✅ Golden datasets (EN, AR, Mixed)  │
           │                  │  ✅ Multi-engine comparison          │
┌──────────▼──────────┐        │  ✅ Markdown/JSON/HTML reports       │
│  INDEPENDENT        │        └──────────────────────────────────────┘
│  IntelliFile-app    │
│  (File Manager)     │
└─────────────────────┘

LEGACY (Migration Source — Tagged ✅):
  OmniFile_Processor → merged into omni-medical-suite
  medical-doc-processor → migrating to omni-medical-suite

---

## Restructuring Progress

| Phase | Status | Key Changes |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Descriptions, topics, READMEs, PORTFOLIO.md across all 10 repos |
| **Phase 2** | ✅ Complete | Package conversion, evaluation toolkit, legacy tagging, production templates |
| **Phase 3** | ✅ Complete | GitHub Actions CI/CD, unified benchmarks, new benchmark repo |
| **Phase 4** | ✅ Complete | handwriting-ocr postprocessor integration, Docker/Makefile verified |

### Phase 2 Completed (June 2026)

| Repository | Change | Commit |
|-----------|--------|--------|
| **medical-ocr-postprocessor** | Converted to installable package with stable API | `ba3a6c2` |
| **medical-ocr-trainer** | Refocused as evaluation & data collection toolkit | `414442f` |
| **OmniFile_Processor** | Tagged as legacy with migration map | `b8817bf` |
| **medical-doc-processor** | Tagged as legacy with merge notice | `d3309f1` |
| **omni-medical-suite** | Added production env templates & deployment scripts | `76e8d92` |

### Phase 3 Completed (June 2026)

| Repository | Change | Commit |
|-----------|--------|--------|
| **medical-ocr-postprocessor** | GitHub Actions CI/CD (lint, test, benchmark, release) | `0359535` |
| **medical-ocr-trainer** | GitHub Actions CI/CD (lint, test, package) | `4f9e31b` |
| **medical-ocr-benchmarks** | NEW — Unified benchmark suite created | (new repo) |

### Phase 4 Completed (June 2026)

| Repository | Change | Commit |
|-----------|--------|--------|
| **medical-handwriting-ocr** | Integrated postprocessor as post-OCR correction engine | `b800558` |
| **omni-medical-suite** | Docker Compose + Makefile already present (verified) | (existing) |

---

## Decision Matrix

| Question | Answer |
|----------|--------|
| Need OCR text correction? | `pip install medical-ocr-postprocessor` → `correct_text()` |
| Need PHI masking? | `from medical_ocr_toolkit import mask_phi` |
| Need to evaluate OCR quality? | `medical-ocr-trainer` → CER, WER, Medical Term Accuracy |
| Need full document platform? | `omni-medical-suite` → Web + API + Training |
| Need production handwriting OCR? | `medical-handwriting-ocr` → PaddleOCR + TrOCR + postprocessor |
| Need to run benchmarks? | `medical-ocr-benchmarks` → `ocr-bench` CLI |
| Legacy code reference? | `OmniFile_Processor` → See MIGRATION_MAP.md |
| Need Lite/Standard/GPU modes? | `medical-handwriting-ocr` → `docker/profiles/lite|standard|gpu-production/` |

---

## 📋 سجل التحديثات الأخيرة (Recent Changes Log)

### تاريخ: يونيو 2026

#### ✅ المهام المُنجزة

| # | المستودع | التغيير | Commit |
|---|----------|---------|--------|
| 1 | `omni-medical-suite` | إضافة `docker-compose.prod.yml` (9 خدمات، إعدادات إنتاجية كاملة) | `4b3cb4e` |
| 2 | `omni-medical-suite` | إضافة `hf-space/` (5 ملفات لنشر Hugging Face Space) | 5 commits |
| 3 | `omni-medical-suite` | إضافة Ultra Quick Start في README (تشغيل بخطوة واحدة) | `168bd84` |
| 4 | `medical-ocr-trainer` | ربط رسمي مع `medical-ocr-benchmarks` كاعتمادية | `1db1495`, `0d7072` |
| 5 | `medical-ocr-trainer` | ترقية الإصدار إلى v1.1.0 | `1db1495` |
| 6 | `medical-ocr-benchmarks` | إضافة Nightly CI مع كشف التراجعات (regression detection) | `504e0c` |
| 7 | `medical-ocr-postprocessor` | إصدار GitHub Release v2.2.0 (أول إصدار مستقر) | Release |

#### 🆕 الملفات الجديدة

| المستودع | الملف | الوصف |
|----------|-------|-------|
| `omni-medical-suite` | `docker-compose.prod.yml` | إعدادات إنتاج كاملة (PostgreSQL, Nginx, Redis auth, Qdrant, Worker, Beat, Monitoring) |
| `omni-medical-suite` | `hf-space/app.py` | تطبيق FastAPI لنشر HF Space |
| `omni-medical-suite` | `hf-space/Dockerfile` | صورة Docker للـ HF Space |
| `omni-medical-suite` | `hf-space/requirements.txt` | اعتماديات HF Space |
| `omni-medical-suite` | `hf-space/README.md` | وصف HF Space بالعربية والإنجليزية |
| `omni-medical-suite` | `hf-space/DEPLOY.md` | دليل نشر HF Space خطوة بخطوة |
| `medical-ocr-benchmarks` | `.github/workflows/nightly-benchmarks.yml` | سير عمل يومي للمعايير مع كشف التراجعات |

#### 🔗 التبعيات المُحدثة

```
medical-handwriting-ocr ──depends-on──▶ medical-ocr-postprocessor
medical-ocr-trainer ──depends-on──────▶ medical-ocr-benchmarks
omni-medical-suite ──depends-on──────▶ medical-ocr-postprocessor (via hf-space)
medical-ocr-benchmarks ──depends-on──▶ medical-ocr-postprocessor (optional)
```

#### 🚀 واجهة التشغيل الفائق (Ultra Quick Start)

مستخدم جديد يمكنه الآن تشغيل المنصة بخطوة واحدة:

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
make dev
# → http://localhost:8000
```

#### 🌐 Hugging Face Space

جميع الملفات الجاهزة للنشر في `hf-space/`:
```bash
huggingface-cli repo create medical-ocr-demo --type space --space_sdk docker
git clone https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo
cp -r omni-medical-suite/hf-space/* medical-ocr-demo/
cd medical-ocr-demo && git add . && git commit -m "deploy" && git push
```

#### 📊 إحصائيات المنظومة النهائية

| المقياس | القيمة |
|---------|--------|
| إجمالي المستودعات النشطة | 7 (من 10) |
| إجمالي Commits في التحسين | 20+ |
| إجمالي الأسطر المضافة | 7,000+ |
| مستودعات مع CI/CD | 4/7 |
| مستودعات مع Release | 1/7 (postprocessor v2.2.0) |
| Legacy موثقة | 2 (OmniFile_Processor, medical-doc-processor) |
