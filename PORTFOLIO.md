# Dr. Abdulmalek — Project Portfolio

> **Medical Document Intelligence Ecosystem**
> Unified architecture for Arabic/English medical OCR, NLP, and AI-powered document processing.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PLATFORM LAYER                                   │
│  omni-medical-suite (Main Platform — Monorepo)                      │
│  Next.js 16 + FastAPI + Celery + Redis + Qdrant                     │
└──────────┬──────────────────────────────────┬───────────────────────┘
           │                                  │
┌──────────▼──────────┐        ┌──────────────▼──────────────────────┐
│  APPLICATION LAYER   │        │  CORE ENGINES LAYER                │
│                      │        │                                      │
│  medical-handwriting │        │  medical-ocr-postprocessor          │
│  -ocr (Production)   │───────▶│  (Correction + PHI Masking)        │
│                      │        │                                      │
│  medical-ocr-trainer │        │                                      │
│  (Data Collection)   │───────▶│                                      │
│                      │        │                                      │
│  medical-doc-        │        │                                      │
│  processor (Review)   │        │                                      │
└──────────┬──────────┘        └──────────────┬──────────────────────┘
           │                                  │
┌──────────▼──────────┐        ┌──────────────▼──────────────────────┐
│  DEPLOYMENT LAYER   │        │  STUDY / RESEARCH LAYER             │
│                      │        │                                      │
│  medical-ocr-trainer │        │  omniparse (Fork/Study)              │
│  -hf (HF Space)      │        │  omniparse-study (Analysis)          │
└──────────┬──────────┘        └──────────────────────────────────────┘
           │
┌──────────▼──────────┐
│  INDEPENDENT        │
│  IntelliFile-app    │
│  (File Manager)     │
└─────────────────────┘

LEGACY (Migration Source):
  OmniFile_Processor → merged into omni-medical-suite
  medical-doc-processor → migrating to omni-medical-suite
