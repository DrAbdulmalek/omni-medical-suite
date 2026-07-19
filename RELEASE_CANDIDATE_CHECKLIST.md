# Release Candidate Checklist — v1.1.0-rc1

**Target:** promote `feat/rc-hardening-p0` → `main` and tag `v1.1.0-rc1`.

---

## P0 — Must pass (this patch set)

- [x] **P0-2 Lazy OCR loading.** Importing `app/services/ocr_service.py`
  no longer triggers PaddleOCR / ImagePreprocessor / Tesseract /
  HybridSpellChecker construction. Same for `app/services/review_service.py`
  (Jais proofreader + NER).
  - Tests: `tests/test_lazy_ocr_service.py` (14 tests, all pass).
  - Verified: `python -c "import app.services.ocr_service; print('ok')"`
    completes in <0.1s without network I/O.
- [x] **P0-3 Translation service extracted.** All translation logic
  moved to `app/services/translation_service.py`. `app/gradio_full_hitl.py`
  slimmed from 585 → 462 lines.
  - Tests: `tests/test_translation_service.py` (14 tests, all pass).
- [x] **P0-4 HF dataset staging.** `save_to_hf()` writes to local
  staging file; `flush_queue()` does batched push with dedup.
  - Tests: `tests/test_hf_dataset_staging.py` (15 tests, all pass).
  - Operational: `OMNI_HF_QUEUE_DIR` env var for custom location.
- [x] **P0-5 Structured decision logger.** `app/core/decision_log.py`
  with `log_decision()`; `EngineRouter.select()` instrumented.
  - Tests: `tests/test_decision_log.py` (12 tests, all pass).
- [x] **P0-8 Pytest config unified.** `pytest.ini` deleted; all config
  under `pyproject.toml [tool.pytest.ini_options]`.
  - Verified: `python -m pytest --co -q` discovers tests correctly.

## Focused core tests — Must remain green

Run these on **every** PR before merge:

```bash
python -m pytest \
  tests/test_arabic_rtl.py \
  tests/test_qdrant_search.py \
  tests/test_rtl_fix_pipeline.py \
  tests/test_field_extractor_core.py \
  tests/test_weighted_dedup.py \
  tests/test_engine_router.py \
  tests/test_engine_router_advanced.py \
  tests/test_decision_log.py \
  tests/test_lazy_ocr_service.py \
  tests/test_translation_service.py \
  tests/test_hf_dataset_staging.py
```

**Last run on this patch set:** 118 passed, 1 skipped (OCR-engine-required).

---

## Pre-merge manual smoke

- [ ] `python -c "from app.services.ocr_service import get_paddle_ocr; print(get_paddle_ocr() is None)"` → prints `True` on a no-paddle env, completes in <1s.
- [ ] `python -c "from app.services.review_service import get_proofreader; print(get_proofreader() is None)"` → prints `True` without `ENABLE_LLM=true`.
- [ ] `python -c "from app.services.translation_service import translate_text; print(translate_text('', 'Arabic → English'))"` → prints the empty-input Arabic message.
- [ ] `python -c "from app.services.hf_dataset_service import count_pending; print(count_pending())"` → prints `0` on a fresh env.
- [ ] `python -m pytest tests/test_engine_router.py -v` → all pass, and a `engine_selection` decision line appears on stderr.
- [ ] `python -c "import app.gradio_full_hitl"` → completes without raising.

## Deploy smoke (post-merge)

- [ ] `.github/workflows/deploy-to-hf.yml` runs green on `main`.
- [ ] HF Space URL `https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr` responds 200.
- [ ] Upload a test image; verify "Saved correction to HF" message appears.
- [ ] `~/.omni/hf_dataset_queue/pending.jsonl` exists locally with one row.
- [ ] After 25 saves (or `flush_queue()` call), the HF dataset total
      increments by the staged count.

## Known drift to address in P1 (NOT blockers for rc1)

- `hf-space/app.py` duplicates `app/services/*` logic. They have
  diverged. P1-1 will document this and add a parity CI check.
- `src/ocr/field_extractor.py` does not support multi-line values or
  bilingual labels. P1-6.
- `OCRComparisonPipeline` lacks CSV/JSON export. P1-7.

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lazy loading breaks a caller that depended on import-time init | Low | Medium | PEP 562 `__getattr__` preserves all old names; tested in `test_lazy_ocr_service.py`. |
| `flush_queue()` loses rows on partial HF upload failure | Low | High | Rows are only archived+cleared after `push_to_hub()` returns successfully. On failure, exception propagates and rows stay staged. |
| Decision logger grows large in production | Medium | Low | One line per `EngineRouter.select()` call; typical session <100 decisions/hour. Configure log rotation on `app.decision_log` logger. |
| `hf-space/app.py` drift causes silent deploy regression | High | High | P1-1 parity check is the long-term fix. For rc1, manually diff `hf-space/app.py` against `app/services/*` before tagging. |
| Staging file grows unbounded if `flush_queue()` never succeeds | Low | Medium | Operator should monitor `count_pending()` and trigger manual flush. Future: add a max-staged-rows guard. |

## Sign-off

- [ ] All P0 boxes ticked.
- [ ] Focused core tests green.
- [ ] Pre-merge manual smoke run.
- [ ] Code review by at least one other engineer.
- [ ] Tag `v1.1.0-rc1` on `main` after merge.
