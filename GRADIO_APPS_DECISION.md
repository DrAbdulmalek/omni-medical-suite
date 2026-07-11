# GRADIO_APPS_DECISION.md — Audit of 43 Files Containing `import gradio`

> Generated: 2025-07-10 | Task 3.5 — Gradio Apps Audit
> **DELETE section executed: 2026-07-11** — 24 files confirmed deleted, 20 remaining (2 KEEP + 18 PENDING)

## Summary

| Metric | Count |
|--------|-------|
| Total files with `import gradio` (original) | 43 |
| **KEEP** | 2 |
| **DELETE** ~~(24)~~ — **EXECUTED, confirmed** | 0 remaining |
| **PENDING HUMAN REVIEW** (unique functionality) | 18 |
| **Current files with `import gradio`** | **20** (verified via `find . -name "*.py" -exec grep -l "import gradio" {} \;`)|

## Decision Rules Applied

1. **KEEP**: Official app (`app/gradio_full_hitl.py`) and deployed HF Space (`hf-space/app.py`)
2. **KEEP**: Any file used in tests (none found — no test references `gradio` at all)
3. **DELETE**: Files inside merged-remnant packages (`file_processor/`, `handwriting/`, `omnifile/`, `doc_processor/`) that are copies
4. **DELETE**: False positives (`import gradio` only in a docstring/comment, not functional code)
5. **PENDING**: Any file with unique functionality not present in the official app

## Decision Table

### KEEP (2 files)

| # | File | Lines | Decision | Reason |
|---|------|------:|----------|--------|
| 1 | `app/gradio_full_hitl.py` | 944 | **KEEP** | Official app — the single canonical Gradio interface |
| 2 | `hf-space/app.py` | 664 | **KEEP** | Deployed on HuggingFace Space — CPU-optimized variant (no LLM, no HF upload, no dictionary update) |

### DELETE (24 files) — ✅ EXECUTED

> All 24 files below were deleted in commit `f8dab72`. Verified: `find . -name "*.py" -exec grep -l "import gradio" {} \;` returns exactly 20 files (2 KEEP + 18 PENDING).

| # | File | Lines | Decision | Reason |
|---|------|------:|----------|--------|
| 3 | `packages/file_processor/hf_app.py` | 1995 | **DELETE** | Merged-remnant copy (in `file_processor/`) |
| 4 | `packages/file_processor/src/gradio_ui.py` | 794 | **DELETE** | Merged-remnant copy |
| 5 | `packages/file_processor/modules/ui/gradio_app.py` | 580 | **DELETE** | Merged-remnant copy |
| 6 | `packages/file_processor/run.py` | 85 | **DELETE** | Merged-remnant launcher — imports from merged packages |
| 7 | `packages/file_processor/tools/review_dashboard.py` | 129 | **DELETE** | Merged-remnant copy |
| 8 | `packages/file_processor/modules/vision/medical_ocr_gradio.py` | 105 | **DELETE** | Merged-remnant copy of `packages/vision/medical_ocr_gradio.py` |
| 9 | `packages/file_processor/modules/nlp/translation_corrector/arabic_translation_processor.py` | 977 | **DELETE** | Merged-remnant copy |
| 10 | `packages/file_processor/legacy/mobile_review/split/05-review-systems/review_dashboard.py` | 73 | **DELETE** | Merged-remnant legacy copy |
| 11 | `packages/handwriting/hf_app.py` | 1799 | **DELETE** | Merged-remnant copy |
| 12 | `packages/handwriting/src/gradio_ui.py` | 772 | **DELETE** | Merged-remnant copy |
| 13 | `packages/omnifile/hf_app.py` | 1277 | **DELETE** | Merged-remnant copy |
| 14 | `packages/omnifile/src/gradio_ui.py` | 772 | **DELETE** | Merged-remnant copy (identical MD5 to `packages/handwriting/src/gradio_ui.py`) |
| 15 | `packages/vision/medical_ocr_gradio.py` | 106 | **DELETE** | Merged-remnant copy |
| 16 | `packages/nlp/translation_corrector/arabic_translation_processor.py` | 976 | **DELETE** | Merged-remnant copy |
| 17 | `packages/core/progress_tracker.py` | 2001 | **DELETE** | **FALSE POSITIVE** — `import gradio` only in a docstring example (line 1870) |
| 18 | `packages/file_processor/modules/core/progress_tracker.py` | 2006 | **DELETE** | **FALSE POSITIVE** — `import gradio` only in a docstring example |
| 19 | `hf-space/packages/core/progress_tracker.py` | 2010 | **DELETE** | **FALSE POSITIVE** — `import gradio` only in a docstring example |
| 20 | `hf-space/packages/nlp/translation_corrector/arabic_translation_processor.py` | 978 | **DELETE** | Merged-remnant copy — not imported by `hf-space/app.py` |
| 21 | `hf-space/packages/vision/medical_ocr_gradio.py` | 105 | **DELETE** | Merged-remnant copy — not imported by `hf-space/app.py` |
| 22 | `apps/handwriting-demo/variants/handwriting-ocr/hf_app.py` | 1799 | **DELETE** | Exact copy of `packages/handwriting/hf_app.py` (same MD5) |
| 23 | `apps/handwriting-demo/variants/handwriting-ocr/src/gradio_ui.py` | 772 | **DELETE** | Exact copy of `packages/handwriting/src/gradio_ui.py` (same MD5) |
| 24 | `labs/omniparse_study/omniparse/demo.py` | 738 | **DELETE** | Variant copy of `packages/omniparse/omniparse/demo.py` (minor diff only) |
| 25 | `labs/omniparse_study/server.py` | 88 | **DELETE** | Variant copy of `packages/omniparse/server.py` (minor diff only) |
| 26 | `apps/ocr-pipeline/app/gradio_hitl.py` | 47 | **DELETE** | Trivial 3-function wrapper — no unique functionality |

### PENDING HUMAN REVIEW (18 files)

| # | File | Lines | Decision | Reason / Unique Feature |
|---|------|------:|----------|--------------------------|
| 27 | `app/hf_app.py` | 1990 | **PENDING** | Has **EasyOCR + TrOCR** engines, **PDF OCR**, **language detection**, `_ocr_ensemble()` — none in official app |
| 28 | `app/gradio_ui.py` | 152 | **PENDING** | Minimal 4-function OCR UI — possible simple demo/prototype to keep or delete |
| 29 | `apps/handwriting-demo/hf-deploy/app/gradio_app.py` | 731 | **PENDING** | Has **clinical Q&A** (`ask_clinical_question`), **document parsing**, **correction suggestions** — unique LLM integration |
| 30 | `apps/ocr-demo/app.py` | 849 | **PENDING** | Has `ensemble_vote()`, **JSON/TXT export**, `get_system_info()` — unique |
| 31 | `apps/ocr-pipeline/app.py` | 650 | **PENDING** | Has **batch OCR**, **diff HTML**, **engine comparison**, **dictionary search/add** — unique |
| 32 | `desktop/gradio_scanner_app.py` | 281 | **PENDING** | **Document scanner**: shadow removal, perspective correction, denoising, contrast enhancement — unique domain |
| 33 | `notebooks/omnimedical_gradio_ui.py` | 623 | **PENDING** | Has `OCRFusionV2`, `MedicalContextProtector`, `CorrectionMemoryV2` classes — unique OCR fusion approach |
| 34 | `packages/file_processor/src/correction_trainer_ui.py` | 588 | **PENDING** | **Word-level correction trainer** — spell check, DB integration, undo, word cards — unique |
| 35 | `packages/file_processor/modules/ui/batch_correction_ui.py` | 214 | **PENDING** | **BatchCorrectionUI** — load/save/navigate corrections in batch — unique |
| 36 | `packages/file_processor/modules/ui/dual_ocr_interface.py` | 237 | **PENDING** | **DualOCR** — side-by-side engine comparison with line navigation — unique |
| 37 | `packages/file_processor/legacy/mobile_review/split/06-pwa-features/gradio_pwa_wrapper.py` | 43 | **PENDING** | **PWA wrapper** — service worker injection, manifest, installable on mobile — unique |
| 38 | `packages/file_processor/legacy/translation_corrector/app.py` | 977 | **PENDING** | **TranslationRule** system — rule-based Arabic translation correction with regex — unique |
| 39 | `packages/file_processor/notebooks/Medical_OCR_Review_Colab.py` | 810 | **PENDING** | Standalone **AdvancedMedicalOCR** class for Colab — image enhancement, confidence scoring — unique |
| 40 | `packages/doc_processor/download/medical-image-ai-suite/gradio_phase2_enhanced.py` | 409 | **PENDING** | Has **draw_boxes** on images, document processing — in doc_processor (merged-remnant pkg) but unique |
| 41 | `packages/doc_processor/download/medical-image-ai-suite/omni_gradio_fusion_v3.py` | 364 | **PENDING** | **3-engine comparison** (Tesseract + EasyOCR + PaddleOCR) — unique |
| 42 | `packages/omniparse/omniparse/demo.py` | 738 | **PENDING** | **Omniparse** document parser (tables, equations, images) — different domain from medical OCR |
| 43 | `packages/omniparse/server.py` | 88 | **PENDING** | Omniparse FastAPI server — support file for #42 |
| 44 | `tools/ops/telegram_forwarder/app.py` | 614 | **PENDING** | **Telegram bot manager** — different domain entirely (not medical OCR) |

## Files Deleted (24 files, ~16,500 lines removed)

```bash
git rm packages/file_processor/hf_app.py
git rm packages/file_processor/src/gradio_ui.py
git rm packages/file_processor/modules/ui/gradio_app.py
git rm packages/file_processor/run.py
git rm packages/file_processor/tools/review_dashboard.py
git rm packages/file_processor/modules/vision/medical_ocr_gradio.py
git rm packages/file_processor/modules/nlp/translation_corrector/arabic_translation_processor.py
git rm packages/file_processor/legacy/mobile_review/split/05-review-systems/review_dashboard.py
git rm packages/handwriting/hf_app.py
git rm packages/handwriting/src/gradio_ui.py
git rm packages/omnifile/hf_app.py
git rm packages/omnifile/src/gradio_ui.py
git rm packages/vision/medical_ocr_gradio.py
git rm packages/nlp/translation_corrector/arabic_translation_processor.py
git rm packages/core/progress_tracker.py
git rm packages/file_processor/modules/core/progress_tracker.py
git rm hf-space/packages/core/progress_tracker.py
git rm hf-space/packages/nlp/translation_corrector/arabic_translation_processor.py
git rm hf-space/packages/vision/medical_ocr_gradio.py
git rm apps/handwriting-demo/variants/handwriting-ocr/hf_app.py
git rm apps/handwriting-demo/variants/handwriting-ocr/src/gradio_ui.py
git rm labs/omniparse_study/omniparse/demo.py
git rm labs/omniparse_study/server.py
git rm apps/ocr-pipeline/app/gradio_hitl.py
```

## PENDING Files — Recommended Groupings for Human Decision

### Group A: Should Merge Into Official App (high value)
These contain functionality that could enhance `app/gradio_full_hitl.py`:
- `app/hf_app.py` — EasyOCR/TrOCR engines, PDF support
- `packages/file_processor/src/correction_trainer_ui.py` — Word-level trainer
- `apps/ocr-pipeline/app.py` — Batch OCR, diff view, dictionary management

### Group B: Standalone Apps Worth Keeping (different use cases)
- `desktop/gradio_scanner_app.py` — Scanner (desktop use case)
- `apps/handwriting-demo/hf-deploy/app/gradio_app.py` — Handwriting + Clinical Q&A
- `tools/ops/telegram_forwarder/app.py` — Telegram bot (ops tool)

### Group C: Evaluation / Study (can be archived)
- `notebooks/omnimedical_gradio_ui.py` — Study notebook
- `packages/omniparse/omniparse/demo.py` + `server.py` — Omniparse (different tool)
- `packages/file_processor/notebooks/Medical_OCR_Review_Colab.py` — Colab notebook

### Group D: Small Components (integrate or delete)
- `app/gradio_ui.py` (152 lines) — Subset of official, probably delete
- `packages/file_processor/modules/ui/batch_correction_ui.py` — Merge into official?
- `packages/file_processor/modules/ui/dual_ocr_interface.py` — Merge into official?
- `packages/file_processor/legacy/mobile_review/split/06-pwa-features/gradio_pwa_wrapper.py` — PWA support
- `packages/file_processor/legacy/translation_corrector/app.py` — Rule-based translator

### Group E: In Merged-Remnant Packages (unique but location is wrong)
- `packages/doc_processor/download/.../gradio_phase2_enhanced.py`
- `packages/doc_processor/download/.../omni_gradio_fusion_v3.py`
- `apps/ocr-demo/app.py`