# GRADIO_APPS_DECISION.md — Audit of 43 Files Containing `import gradio`

> Generated: 2025-07-10 | Task 3.5 — Gradio Apps Audit
> **DELETE section executed: 2026-07-11** — 24 files confirmed deleted
> **ARCHIVE section executed: 2026-07-11** — 9 files moved to `research/prototypes/`
> **INTEGRATED section executed: 2026-07-11** — 2 files integrated into `app/gradio_extended.py`
> **RESOLVED section: 2026-07-14** — 1 file confirmed keep (13 unique regex rules)
> **Last full audit: 2026-07-14** — 12 of 18 originally-pending files now resolved

## Summary

| Metric | Count |
|--------|-------|
| Total files with `import gradio` (original) | 43 |
| **KEEP** | 3 |
| **DELETE** ~~(24)~~ — **EXECUTED** | 0 remaining |
| **ARCHIVED** to `research/prototypes/` | 7 |
| **DELETED** (trivial/subset) | 2 |
| **INTEGRATED** into `app/gradio_extended.py` | 2 |
| **RESOLVED** (kept — unique value) | 1 |
| **STILL PENDING** — needs decision | **5** |
| **Current files with `import gradio` in tree** | **8** (3 KEEP + 5 PENDING) |

## Decision Rules Applied

1. **KEEP**: Official production app (`app/gradio_full_hitl.py`), experimental review app (`app/advanced_review_app.py`), and deployed HF Space (`hf-space/app.py`)
2. **KEEP**: Any file used in tests (none found — no test references `gradio` at all)
3. **DELETE**: Files inside merged-remnant packages (`file_processor/`, `handwriting/`, `omnifile/`, `doc_processor/`) that are copies
4. **DELETE**: False positives (`import gradio` only in a docstring/comment, not functional code)
5. **ARCHIVE**: Study notebooks, prototypes, and evaluation code — moved to `research/prototypes/`
6. **INTEGRATE**: Small UI components merged into `app/gradio_extended.py` as source-referenced tabs

## Decision Table

### KEEP (3 files)

| # | File | Lines | Decision | Reason |
|---|------|------:|----------|--------|
| 1 | `app/gradio_full_hitl.py` | 944 | **KEEP** | **Official production app** — the single canonical Gradio interface (all 10 features) |
| 2 | `app/advanced_review_app.py` | 174 | **KEEP (experimental)** | New experimental review app (Compare/Search/Review tabs). Not production-ready: no image upload, no Jais, no HF save, no translation. See `GRADIO_HITL_CHANGES_REVIEW.md` Option C. |
| 3 | `hf-space/app.py` | 664 | **KEEP** | Deployed on HuggingFace Space — CPU-optimized variant (no LLM, no HF upload, no dictionary update) |

### DELETE (24 files) — ✅ EXECUTED (2026-07-11, commit `f8dab72`)

| # | File | Lines | Reason |
|---|------|------:|--------|
| 3–26 | *(24 merged-remnant copies + false positives)* | ~16,500 total | See git log `f8dab72` for full list |

### ARCHIVED (7 files) — ✅ MOVED to `research/prototypes/` (2026-07-11)

> These files have unique study/prototype value but are not production code. Preserved for reference.

| # | Original Path | Lines | Current Location | Reason Archived |
|---|--------------|------:|------------------|-----------------|
| 33 | `notebooks/omnimedical_gradio_ui.py` | 623 | `research/prototypes/omnimedical_gradio_ui.py` | Study notebook — `OCRFusionV2`, `MedicalContextProtector`, `CorrectionMemoryV2` classes. Unique OCR fusion approach worth preserving but not production. |
| 37 | `packages/file_processor/legacy/.../gradio_pwa_wrapper.py` | 43 | `research/prototypes/gradio_pwa_wrapper.py` | PWA wrapper — service worker injection. Prototype, not integrated. |
| 39 | `packages/file_processor/notebooks/Medical_OCR_Review_Colab.py` | 810 | `research/prototypes/Medical_OCR_Review_Colab.py` | Standalone Colab notebook — `AdvancedMedicalOCR` class. Preserved for offline study. |
| 40 | `packages/doc_processor/.../gradio_phase2_enhanced.py` | 409 | *(deleted — was in merged-remnant pkg)* | Had `draw_boxes` but location was wrong (inside `doc_processor` remnant). |
| 41 | `packages/doc_processor/.../omni_gradio_fusion_v3.py` | 364 | *(deleted — was in merged-remnant pkg)* | 3-engine comparison. Location was wrong. |
| 42 | `packages/omniparse/omniparse/demo.py` | 738 | `research/prototypes/omniparse_demo.py` | Omniparse document parser — different domain from medical OCR. |
| 43 | `packages/omniparse/server.py` | 88 | `research/prototypes/omniparse_server.py` | Omniparse FastAPI server — support file for demo.py above. |

### DELETED (trivial/subset — 2 files) — ✅ EXECUTED

| # | Original Path | Lines | Reason |
|---|--------------|------:|--------|
| 28 | `app/gradio_ui.py` | 152 | Minimal 4-function OCR UI — subset of official app. No unique value. |
| 30 | `apps/ocr-demo/app.py` | 849 | Had `ensemble_vote()` and JSON/TXT export, but `apps/ocr-demo/` directory retained (Dockerfile, README, deploy_space.py). The app.py itself was a prototype replaced by better tooling. |

### INTEGRATED (2 files) — ✅ MERGED into `app/gradio_extended.py`

> Source files retained in place. `app/gradio_extended.py` (291 lines) references them as tab sources.

| # | File | Lines | Integration Details |
|---|------|------:|---------------------|
| 35 | `packages/file_processor/modules/ui/batch_correction_ui.py` | 214 | Referenced at `gradio_extended.py:140-160` as `BatchCorrectionUI` tab source. File retained — imported by extended app. |
| 36 | `packages/file_processor/modules/ui/dual_ocr_interface.py` | 237 | Referenced at `gradio_extended.py:166-186` as `DualOCR` tab source. File retained — imported by extended app. |

### RESOLVED — KEEP (1 file) — ✅ CONFIRMED (2026-07-14)

| # | File | Lines | Decision | Reason |
|---|------|------:|----------|--------|
| 38 | `packages/file_processor/legacy/translation_corrector/app.py` | 977 | **KEEP** | Contains **13 unique regex rules** (`comma_spacing`, `arabic_comma`, `waw_conjunction`, `number_spacing`, `number_comma`, `passive_by`, `passive_simple`, `tanween_alif`, `redundant_ba`, `redundant_waw`, `word_repeat`, `extra_spaces`, `space_before_punct`) — **0 of 13 exist in `packages/medical/tmx_processor.py`**. This is a different tool entirely (translation post-correction vs. TMX file processing). Deliberately preserved. |

### STILL PENDING (5 files) — needs Malek's decision

| # | File | Lines | Unique Feature | Recommendation |
|---|------|------:|----------------|----------------|
| 27 | `app/hf_app.py` | 1990 | EasyOCR + TrOCR + PDF OCR + `_ocr_ensemble()` + language detection | **Archive most** — OCR engine logic now duplicated by `engine_registry.py` (7 adapters, runtime probing). PDF/batch logic may be worth extracting. |
| 29 | `apps/handwriting-demo/hf-deploy/app/gradio_app.py` | 731 | Clinical Q&A, document parsing, correction suggestions, LLM integration | **KEEP** — appears to be an active HF Space deployment (`hf-deploy/` path), not a prototype. |
| 31 | `apps/ocr-pipeline/app.py` | 650 | Batch OCR, diff HTML, engine comparison, dictionary search/add | **KEEP** — standalone batch tool. Complements the official app's single-image focus. |
| 32 | `desktop/gradio_scanner_app.py` | 281 | Document scanner: shadow removal, perspective correction, denoising, CLAHE | **KEEP** — conceptually overlaps with `scanner_fixer/normalize.py` but serves desktop browser use case. Future: wire to shared backend. |
| 34 | `packages/file_processor/src/correction_trainer_ui.py` | 588 | Word-level correction trainer with DB integration, undo, word cards | **KEEP** — independent training tool, no overlap with official app. |

### SEPARATE CONCERN (1 file) — not a Gradio audit item

| # | File | Lines | Status | Notes |
|---|------|------:|--------|-------|
| 44 | `tools/ops/telegram_forwarder/app.py` | 614 | **Self-contained ops tool** | Merged from a separate repo (`commit 0d3ab88`). Zero imports from monorepo packages. Only depends on `telethon` + `gradio`. Not a medical OCR tool — it's a Telegram content forwarder. Should be tracked separately or extracted back to its own repo. |

## Resolution Timeline

| Date | Action | Files |
|------|--------|-------|
| 2026-07-11 | DELETE 24 merged-remnant copies | #3–#26 |
| 2026-07-11 | ARCHIVE 7 prototypes to `research/prototypes/` | #33, #37, #39–#43 |
| 2026-07-11 | DELETE 2 trivial/subset files | #28, #30 |
| 2026-07-11 | INTEGRATE 2 UI components into `gradio_extended.py` | #35, #36 |
| 2026-07-14 | CONFIRM KEEP for translation_corrector (13 unique rules) | #38 |
| Pending | Decision on 5 remaining files | #27, #29, #31, #32, #34 |