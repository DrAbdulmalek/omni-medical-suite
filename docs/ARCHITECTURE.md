# Architecture — omni-medical-suite

End-to-end medical document processing suite: scan → OCR → audited correction/spell-check → terminology/TM lookup → NER → structured output. Ships as AppImage + HF Space.

## Current production OCR path

The canonical Gradio/HF production path is implemented through:

```text
input image
  → hf-space/app.py / hf-space/app_core.py
  → app/services/ocr_service.py
      → image preprocessing
      → PaddleOCR / Tesseract execution
      → _auto_correct_ocr()
          → HybridSpellChecker.apply_ocr_corrections()
          → exact-token audited OCR corrections
          → HybridSpellChecker.correct_text()
          → specialty-aware token corrections
      → structured response
```

`hf-space/app_core.py` mirrors the canonical correction implementation and is kept synchronized by `scripts/sync-hf-space.sh` and the HF Space drift gate.

## OCR components

The repository contains two OCR orchestration concepts which must not be conflated:

- `src/ocr/ensemble.py` — a multi-engine ensemble implementation with composite scoring. It is a real repository component.
- `packages/core/engine_router.py` — an engine-selection router which records `engine_selection` decisions through `app.core.decision_log.log_decision()` when its `select()` method is used.

Post-merge audit status: the canonical Gradio/HF production path above does **not** currently invoke `packages/core/engine_router.py` for engine selection. Therefore its decision logging is not, by itself, evidence that production OCR engine-selection decisions are being audited. Any future connection must be explicit, tested, and must not create a second competing OCR path.

## OCR correction safety boundary

OCR corrections, medical terminology, and translation memory are separate semantic resources:

```text
OCR corrections
    → exact-token correction only

Medical terminology
    → exact whole-input lookup / normalization metadata
    → never a blind text replacement map

Translation memory / TMX
    → exact segment lookup
    → never substring replacement
```

The 159k-scale generated glossary artifact is not a runtime OCR replacement map. It must not be reintroduced into `_auto_correct_ocr()` as a global `str.replace()` dictionary.

## Repository data dependencies

`data/arabic-medical-glossary` is a Git submodule. Any CI job that builds an artifact or Docker image requiring that data must use `actions/checkout` with `submodules: recursive` (or an equivalent explicit submodule initialization step). A normal checkout leaves the submodule unavailable.

## Decision logging

`app.core.decision_log.log_decision()` is implemented and used by `packages/core/engine_router.py`. The production OCR path must be treated separately until an explicit integration is implemented and covered by an end-to-end test.

### Issue #94 — Production engine-selection decision logging

The **existing production HF OCR selector** (in `hf-space/app_core.py:_select_ocr_result()`) remains the canonical selector. It has been instrumented to emit a structured decision log via `log_decision()` — **without changing OCR behavior**.

Key points:

- **The production selector is `_select_ocr_result()`**, not `EngineRouter`. `EngineRouter` exists in `packages/core/engine_router.py` but is **NOT used by the production HF OCR pipeline**.
- The selection rule is unchanged: PaddleOCR is selected iff it produced text with stripped length > 5 characters; otherwise Tesseract.
- The decision log records **only operational metadata** in `inputs`: `paddle_available`, `paddle_text_length`, `tesseract_available`, `tesseract_text_length`, `selection_rule`. **No OCR text, patient data, medical terms, image content, or raw OCR output** is ever logged.
- `log_decision()` has a never-raise contract (errors are swallowed), so logging failures cannot break OCR processing. This is verified by `tests/test_pr94_production_engine_decision.py::TestSelectOcrResultLoggingNeverFails`.
- A reproducible benchmark is at `scripts/benchmarks/benchmark_production_ocr_selection.py`. It measures the pure selection helper with deterministic mocked outputs — it does **not** fabricate PaddleOCR/Tesseract inference numbers.

This is intentional until a separate architecture decision changes the selector to `EngineRouter` or another component.

## Performance

No repository-wide P50/P95/P99 OCR production baseline is claimed by this document. A reproducible benchmark must be established before introducing additional NLP dependencies or making latency claims.

## Future layers

After production OCR and terminology/TM availability are verified in deployed artifacts, the next architectural layer is clinical NER. Only after that should the project evaluate larger NLP integrations (for example MedCAT, medspaCy, or EDS-NLP) and interoperability mappings such as FHIR.
