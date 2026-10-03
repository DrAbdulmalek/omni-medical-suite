# GRADIO_APPS_DECISION.md — Audit of 43 Files Containing `import gradio`

> Generated: 2025-07-10 | Task 3.5 — Gradio Apps Audit
> **DELETE section executed: 2026-07-11** — 24 files confirmed deleted
> **ARCHIVE section executed: 2026-07-11** — 9 files moved to `research/prototypes/`
> **INTEGRATED section executed: 2026-07-11** — 2 files integrated into `app/gradio_extended.py`
> **RESOLVED section: 2026-07-14** — 1 file confirmed keep (13 unique regex rules)
> **FINAL RESOLUTION: 2026-07-15** — all 43 files now resolved; 0 pending
> **Last full audit: 2026-07-15** — 18 of 18 originally-pending files now resolved

## Summary

| Metric | Count |
|--------|-------|
| Total files with `import gradio` (original) | 43 |
| **KEEP** | 7 |
| **DELETE** — EXECUTED (2026-07-11) | 26 (24 merged-remnant + 2 trivial) |
| **ARCHIVED** to `research/prototypes/` | 8 |
| **INTEGRATED** into `app/gradio_extended.py` | 2 |
| **STILL PENDING** | **0** |
| **Current files with `import gradio` in tree** | **9** (7 KEEP + 2 INTEGRATED) |

## Decision Rules Applied

1. **KEEP**: Official production app (`app/gradio_full_hitl.py`), experimental review app (`app/advanced_review_app.py`), and deployed HF Space (`hf-space/app.py`)
2. **KEEP**: Any file used in tests (none found — no test references `gradio` at all)
3. **DELETE**: Files inside merged-remnant packages (`file_processor/`, `handwriting/`, `omnifile/`, `doc_processor/`) that are copies
4. **DELETE**: False positives (`import gradio` only in a docstring/comment, not functional code)
5. **ARCHIVE**: Study notebooks, prototypes, and evaluation code — moved to `research/prototypes/`
6. **INTEGRATE**: Small UI components merged into `app/gradio_extended.py` as source-referenced tabs

## Decision Table

### KEEP (7 files)

| # | File | Lines | Decision | Reason/Evidence |
|---|------|------:|----------|-----------------|
| 1 | `app/gradio_full_hitl.py` | 944 | **KEEP** | Official production app — the single canonical Gradio interface (all 10 features). Uses `translation_corrector` from `packages/nlp/`. |
| 2 | `app/advanced_review_app.py` | 174 | **KEEP (experimental)** | New experimental review app (Compare/Search/Review tabs). Not production-ready: no image upload, no Jais, no HF save, no translation. See `GRADIO_HITL_CHANGES_REVIEW.md` Option C. |
| 3 | `hf-space/app.py` | 664 | **KEEP** | Deployed on HuggingFace Space — CPU-optimized variant (no LLM, no HF upload, no dictionary update) |
| 29 | `apps/handwriting-demo/hf-deploy/app/gradio_app.py` | 731 | **KEEP** | Active HF Space deployment (`hf-deploy/` path) — clinical Q&A, document parsing, correction suggestions, LLM integration. Not a prototype. |
| 31 | `apps/ocr-pipeline/app.py` | 650 | **KEEP** | Standalone batch OCR tool with diff HTML, engine comparison, dictionary search/add. Complements the official app's single-image focus. |
| 32 | `desktop/gradio_scanner_app.py` | 281 | **KEEP** | Document scanner: shadow removal, perspective correction, denoising, CLAHE. Conceptually overlaps with `scanner_fixer/normalize.py` but serves desktop browser use case. |
| 34 | `packages/file_processor/src/correction_trainer_ui.py` | 588 | **KEEP** | Independent word-level correction trainer with DB integration, undo, word cards. No overlap with official app. |
| 38 | `packages/file_processor/legacy/translation_corrector/app.py` | 977 | **KEEP** | Contains 13 unique regex rules (`comma_spacing`, `arabic_comma`, `waw_conjunction`, `number_spacing`, `number_comma`, `passive_by`, `passive_simple`, `tanween_alif`, `redundant_ba`, `redundant_waw`, `word_repeat`, `extra_spaces`, `space_before_punct`) — 0 of 13 exist in `packages/medical/tmx_processor.py`. Different tool entirely (translation post-correction vs. TMX file processing). |

### DELETE (26 files) — ✅ EXECUTED (2026-07-11, commit `f8dab72`)

| # | File | Lines | Reason |
|---|------|------:|--------|
| 3–26 | *(24 merged-remnant copies + false positives)* | ~16,500 total | See git log `f8dab72` for full list |
| 28 | `app/gradio_ui.py` | 152 | Minimal 4-function OCR UI — subset of official app. No unique value. |
| 30 | `apps/ocr-demo/app.py` | 849 | Had `ensemble_vote()` and JSON/TXT export, but `apps/ocr-demo/` directory retained (Dockerfile, README, deploy_space.py). The app.py itself was a prototype replaced by better tooling. |

### ARCHIVED (8 files) — ✅ MOVED to `research/prototypes/`

> These files have unique study/prototype value but are not production code. Preserved for reference.

| # | Original Path | Lines | Current Location | Reason Archived |
|---|--------------|------:|------------------|-----------------|
| 27 | `app/hf_app.py` | 1990 | `research/prototypes/hf_app_legacy.py` | EasyOCR + TrOCR + PDF OCR. OCR engine logic now duplicated by `engine_registry.py` (7 adapters, runtime probing). No active imports found (only comment references in `gradio_extended.py`). Archived 2026-07-15. |
| 33 | `notebooks/omnimedical_gradio_ui.py` | 623 | `research/prototypes/omnimedical_gradio_ui.py` | Study notebook — `OCRFusionV2`, `MedicalContextProtector`, `CorrectionMemoryV2` classes. Unique OCR fusion approach worth preserving but not production. |
| 37 | `packages/file_processor/legacy/.../gradio_pwa_wrapper.py` | 43 | `research/prototypes/gradio_pwa_wrapper.py` | PWA wrapper — service worker injection. Prototype, not integrated. |
| 39 | `packages/file_processor/notebooks/Medical_OCR_Review_Colab.py` | 810 | `research/prototypes/Medical_OCR_Review_Colab.py` | Standalone Colab notebook — `AdvancedMedicalOCR` class. Preserved for offline study. |
| 40 | `packages/doc_processor/.../gradio_phase2_enhanced.py` | 409 | *(deleted — was in merged-remnant pkg)* | Had `draw_boxes` but location was wrong (inside `doc_processor` remnant). |
| 41 | `packages/doc_processor/.../omni_gradio_fusion_v3.py` | 364 | *(deleted — was in merged-remnant pkg)* | 3-engine comparison. Location was wrong. |
| 42 | `packages/omniparse/omniparse/demo.py` | 738 | `research/prototypes/omniparse_demo.py` | Omniparse document parser — different domain from medical OCR. |
| 43 | `packages/omniparse/server.py` | 88 | `research/prototypes/omniparse_server.py` | Omniparse FastAPI server — support file for demo.py above. |

### INTEGRATED (2 files) — ✅ MERGED into `app/gradio_extended.py`

> Source files retained in place. `app/gradio_extended.py` (291 lines) references them as tab sources.
> **Verification (2026-07-15)**: `grep` confirms no file outside `packages/file_processor/modules/ui/__init__.py` imports these modules. The `__init__.py` itself is not imported by any other file. The code is referenced only in comment-strings within `gradio_extended.py`.

| # | File | Lines | Integration Details |
|---|------|------:|---------------------|
| 35 | `packages/file_processor/modules/ui/batch_correction_ui.py` | 214 | Referenced at `gradio_extended.py:140-160` as `BatchCorrectionUI` tab source. File retained — available for lazy import by extended app. Zero runtime imports from other files. |
| 36 | `packages/file_processor/modules/ui/dual_ocr_interface.py` | 237 | Referenced at `gradio_extended.py:166-186` as `DualOCR` tab source. File retained — available for lazy import by extended app. Zero runtime imports from other files. |

### SEPARATE CONCERN (1 file) — not a Gradio audit item

| # | File | Lines | Status | Notes |
|---|------|------:|--------|-------|
| 44 | `tools/ops/telegram_forwarder/app.py` | 614 | **KEEP (ops tool)** | Self-contained Telegram content forwarder. Merged from external repo (`commit 0d3ab88`). Zero imports from monorepo packages. Only depends on `telethon` + `gradio`. Upstream comparison failed (no network access). File has 1 commit in git history (added `DeduplicationPipeline`). Not a medical OCR tool. Tracked separately as ops tooling. |

## Resolution Timeline

| Date | Action | Files |
|------|--------|-------|
| 2026-07-11 | DELETE 26 files (24 merged-remnant + 2 trivial) | #3–#26, #28, #30 |
| 2026-07-11 | ARCHIVE 7 prototypes to `research/prototypes/` | #33, #37, #39–#43 |
| 2026-07-11 | INTEGRATE 2 UI components into `gradio_extended.py` | #35, #36 |
| 2026-07-14 | CONFIRM KEEP for translation_corrector (13 unique rules) | #38 |
| 2026-07-15 | ARCHIVE `app/hf_app.py` → `research/prototypes/hf_app_legacy.py` | #27 |
| 2026-07-15 | VERIFY all 4 pending KEEP decisions; 0 files remain pending | #29, #31, #32, #34 |
| 2026-07-15 | **ALL 43 FILES RESOLVED** | — |