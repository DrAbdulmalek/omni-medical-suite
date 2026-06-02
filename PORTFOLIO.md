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
