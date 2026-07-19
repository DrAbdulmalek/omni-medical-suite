# STATE_OF_TRUTH.md

**Last updated:** 2026-07-19 — v1.1.1 (HF Space drift control + Termux unification)

> **v1.1.1 round completed (2026-07-19).** Merge commit on `main`:
> `e7ff3e5cc95596ee9ad505839daf3d4c6fa8d178` ("Merge branch
> 'fix/hf-space-drift-and-termux-unify' into main"). Annotated tag
> `v1.1.1` points at this merge commit. Post-merge verification
> (run locally, before push): `python3 scripts/check_hf_space_drift.py`
> → all 4 knobs match; `import app.gradio_full_hitl` → OFFICIAL APP OK;
> `import mobile.termux.termux_app` → `SCANNER_FIXER_AVAILABLE=True`,
> `HAS_LEARNING=True`. Remote branch
> `fix/hf-space-drift-and-termux-unify` is queued for deletion after
> push. **Open security item:** the PAT used in earlier rounds is
> still exposed — user must revoke it manually at
> <https://github.com/settings/tokens> before any further remote
> operation; this sandbox session has no stored credentials and the
> push/tag/remote-branch-delete for v1.1.1 are pending credential
> restoration.

This document is the **single authoritative answer** to "what is the
current state of the omni-medical-suite runtime?". It is updated every
time a P0/P1/P2 patch lands. If anything in this file disagrees with the
code, the code wins — fix this file.

---

## 0. Release status

| Tag | Date | Status | Tests |
|-----|------|--------|-------|
| **v1.1.1** | 2026-07-19 | ✅ Merge complete locally (`e7ff3e5`); tag created; **remote push pending credential restoration** | Post-merge drift gate green; official app + Termux imports OK |
| **v1.1.0** (stable) | 2026-07-19 | ✅ Released — GitHub Release with AppImage + SHA256 | 174 pass (163 unit + 11 AppImage smoke) |
| v1.1.0-rc1 | 2026-07-19 | ✅ Merged into v1.1.0 | 161 pass + 11 conditional |
| v1.0.0 | 2026-07-05 | ✅ Stable (legacy) | Pre-hardening baseline |

**Main HEAD:** points at v1.1.0 stable commit (after final doc + tag push).
**Backup branches:** `backup/before-p0-1-p0-2-work`, `backup/before-p1-work`,
`backup/before-p2-work`, `backup/before-v1.1.0-stable` (last pre-stable snapshot).

---

## 1. What runs in production

| Surface | Source of truth | Notes |
|---------|-----------------|-------|
| HuggingFace Space (live) | `hf-space/app.py` + `hf-space/Dockerfile` | Synced by `.github/workflows/deploy-to-hf.yml` on every push to `main` that touches `hf-space/**` or `Dockerfile.gradio`. |
| Local Gradio HITL app | `app/gradio_full_hitl.py` | Thin orchestration layer over `app/services/*`. |
| Local advanced review/QA | `app/advanced_review_app.py` | Tabbed UI; includes the observability "📊 السجلات" tab added in observability patch. |
| Docker (Gradio) | `Dockerfile.gradio` | Multi-stage build; copies `hf-space/app.py` and `hf-space/{src,packages,config}`. |
| Docker (FastAPI) | `Dockerfile.api` | Not in scope for this patch set. |

**Known drift (intentional, documented):** `hf-space/app.py` (306 LOC,
frozen snapshot for HF Spaces CPU tier) duplicates the OCR / NER /
translation / HF-dataset logic that lives in `app/services/*` (refactored
canonical version, ~466 LOC + service modules). The two implementations
have **structural divergence only** — same public API surface
(`full_process`, `save_to_hf`, `translate_text`, `calculate_metrics`),
same behavioral contract.

| Aspect | `hf-space/app.py` (snapshot) | `app/gradio_full_hitl.py` (canonical) |
|--------|------------------------------|--------------------------------------|
| Imports | All logic inline (cv2, numpy, gradio) | Delegates to `app/services/{ocr,review,translation,hf_dataset}_service.py` |
| Lazy loading | Manual `try/except` per import | PEP 562 `__getattr__` on service modules |
| HF dataset | Direct `datasets.load_dataset()` per save | Staging queue → batched flush at 25 rows |
| Device | Hardcoded `device="cpu"` | `use_gpu=False` (configurable) |
| Sync | NOT auto-overwritten by `sync-hf-space.sh` | Source of truth for `app/services/*` |

`sync-hf-space.sh --verify` confirms 5 directories in sync: `src/ocr`,
`packages/{vision,nlp,core}`, `config`. HF-specific files (`app.py`,
`Dockerfile`, `requirements.txt`) are intentionally NOT overwritten —
they are deploy-snapshot files tuned for the HF Spaces CPU environment.

---

## 2. Service layer (`app/services/`)

| Module | Heavy deps | Lazy? | Public API |
|--------|-----------|-------|------------|
| `ocr_service.py` | PaddleOCR, ImagePreprocessor, Tesseract, HybridSpellChecker | **Yes (since P0)** — `get_paddle_ocr()`, `get_image_preprocessor()`, `has_tesseract()`, `get_spell_checker()` | `_preprocess_image`, `_run_paddle_ocr`, `_run_tesseract`, `_auto_correct_ocr`, `OCR_CORRECTIONS` |
| `review_service.py` | Jais proofreader, JaisNER (when `ENABLE_LLM=true`) | **Yes (since P0)** — `get_proofreader()`, `get_ner()` | `_extract_ner`, `jais_proofread_only`, `MEDICAL_TERMS`, `ENABLE_LLM` |
| `translation_service.py` | MarianMT (transformers), torch | **Yes (since P0)** — `load_translator()`, `get_translation_corrector()` | `translate_text`, `correct_translation`, `TRANSLATION_MODELS`, `DEVICE` |
| `hf_dataset_service.py` | `datasets`, `pandas`, `huggingface_hub` | Conditional import (gated by `HAS_HF`); staging file works without them | `save_to_hf`, `flush_queue`, `count_pending`, `update_medical_dictionary`, `retrain_now` |
| `app/scanner_tab.py` | `scanner_fixer`, OpenCV | Optional (graceful fallback to `process_single_image` legacy path) | `apply_manual_crop`, `apply_advanced_edges`, `process_with_options`, `save_processed_image`, `build_zip_from_dir`, `pick_random_from_gallery` |

**Import-time contract (since P0):**
Importing any service module is O(1) and must not trigger network I/O,
model loading, or subprocess execution. All heavy construction is
deferred to the first call of the corresponding getter. Failures are
cached so a missing dependency is not retried on every call.

`reset_lazy_cache()` is provided on each service for tests.

---

## 3. Persistence model (HF dataset corrections)

**Pre-P0 (broken):** `save_to_hf()` loaded the entire HF dataset,
appended one row, and pushed the whole thing back. O(N) per save in
network and memory; a single upload failure loses the correction.

**Post-P0 (current):**
```
user calls save_to_hf()
    │
    ▼
row appended to <OMNI_HF_QUEUE_DIR>/pending.jsonl   ← atomic append, never fails
    │
    ▼
if pending_count >= OMNI_HF_FLUSH_THRESHOLD (default 25)
    │
    ▼
flush_queue()                                        ← single batched push
    │                                                ← on failure: rows stay staged
    ▼
HF Dataset updated, staged rows archived to <OMNI_HF_QUEUE_DIR>/uploaded/<ts>.jsonl
```

**Operational commands:**
```bash
# Inspect queued rows
OMNI_HF_QUEUE_DIR=~/.omni/hf_dataset_queue \
  python -c "from app.services.hf_dataset_service import count_pending; print(count_pending())"

# Manually flush (e.g. after network outage)
python -c "from app.services.hf_dataset_service import flush_queue; print(flush_queue())"

# Override threshold (e.g. flush on every save for debugging)
OMNI_HF_FLUSH_THRESHOLD=1 python app/gradio_full_hitl.py
```

Dedup is enforced at flush time: rows whose `content_hash` already
exists in the live HF dataset are skipped and archived without
re-upload.

---

## 4. Structured decision logging

**Module:** `app/core/decision_log.py` (new in P0)

**Logger:** `app.decision_log` (separate from root logger; configure a
JSON-lines file handler in production to ship decisions to your log
aggregator).

**Schema:**
```json
{
  "ts": "2026-07-19T00:30:00+00:00",
  "decision": "engine_selection",
  "outcome": ["EasyOCR"],
  "reasons": ["Arabic/mixed language (ar)"],
  "inputs": {"profile": "balanced", "language": "ar", "image_quality": 0.8},
  "skipped": ["PaddleOCR", "Nougat"],
  "duration_ms": 0.42,
  "session_id": "abc123"
}
```

**Currently instrumented sites:**
- `EngineRouter.select()` — emits one `engine_selection` decision per call
  (with the full input vector + skipped alternatives + timing).

**Sites to instrument in P1:**
- `ArabicRTLFixer.fix_text()` — emit `rtl_reversal` decision when a
  reversal is applied.
- `WeightedMedicalDeduplicator` — emit `dedup_decision` when duplicates
  are merged.
- `QdrantMedicalSearch` — emit `backend_selection` when falling back from
  Qdrant to local fuzzy.

**Session id:** set via `OMNI_SESSION_ID` env var or
`app.core.decision_log.set_session_id()` at request middleware time.

---

## 5. Test configuration

**Single source of truth:** `pyproject.toml` → `[tool.pytest.ini_options]`
(consolidated in P0; `pytest.ini` was deleted).

**Markers:** `slow`, `benchmark`, `integration`, `ocr`, `nlp`, `gpu`,
`requires_api_key`.

**Python path:** `["."`, `"src"`, `"packages"]` — matches the runtime
layout.

**Excluded from recursion:** `hf-space/`, `packages/omniparse/`,
`packages/omni-ocr/`, `legacy/`, `node_modules/`, `.venv/`, `build/`,
`dist/`, etc.

**Async:** `asyncio_mode = "auto"`.

**Focused core test suite (must remain green):**
- `tests/test_arabic_rtl.py`
- `tests/test_qdrant_search.py`
- `tests/test_rtl_fix_pipeline.py`
- `tests/test_field_extractor_core.py`
- `tests/test_weighted_dedup.py`
- `tests/test_engine_router.py`
- `tests/test_engine_router_advanced.py`

Run them with:
```bash
python -m pytest tests/test_arabic_rtl.py tests/test_qdrant_search.py \
  tests/test_rtl_fix_pipeline.py tests/test_field_extractor_core.py \
  tests/test_weighted_dedup.py tests/test_engine_router.py \
  tests/test_engine_router_advanced.py
```

**New tests added in P0:**
- `tests/test_decision_log.py` (12 tests)
- `tests/test_lazy_ocr_service.py` (14 tests)
- `tests/test_translation_service.py` (14 tests)
- `tests/test_hf_dataset_staging.py` (15 tests)

Total: **55 new tests, all passing.** Plus the 7 focused core suites
above (63 passed, 1 skipped on a no-OCR-engine environment).

---

## 6. What is NOT yet done (P1/P2 roadmap)

### Done in P0-1 / P0-2 (this patch set)
1. ✅ **Deploy source-of-truth unification.** `scripts/sync-hf-space.sh`
   now has `--verify` mode; `docs/DEPLOYMENT.md` has a "Source of
   Truth" section. `hf-space/` is documented as an explicit deploy
   snapshot (option (b) from the original P1 list).
2. ✅ **Scanner fixer Gradio tab enhancement.**
   `app/advanced_review_app.py` Tab 1 now offers interactive manual
   crop (4 number inputs: x/y/w/h), advanced edge detection options
   (Canny + Adaptive Threshold + Morphology + Hough Lines), and a
   manual save button backed by `app/scanner_tab.py`.
3. ✅ **Lazy loading, translation extraction, HF staging, decision log,
   pytest unification** — done in commit `6a23c52` (P0 hardening patch).

### P1 — should-do before final RC
1. **Field extractor hardening** (`src/ocr/field_extractor.py`):
   multi-line value support, broader bilingual labels, optional
   confidence scoring, safe `template_signature` (current
   `text.replace(value, " ")` corrupts output when a value is a
   substring of another).
2. **Benchmark reporter** (`omni_medical_suite/preprocessing/compare_raw_vs_printed.py`):
   add `to_csv()`, `to_json()`, `aggregate_metrics()` to
   `OCRComparisonPipeline`.
3. **RTL/dedup/backend decision logging** — instrument the sites listed
   in section 4 (currently only `app.core.decision_log` itself is
   wired; callsites are not yet emitting decisions).
4. **Deploy parity CI check.** Add a CI job that runs
   `./scripts/sync-hf-space.sh --verify` on every PR touching
   `hf-space/**`, `src/ocr/**`, `packages/**`, or `config/**`.

### P2 — post-RC polish
5. **Git LFS audit.** Verify `.gitattributes` covers all binary artifacts
   currently tracked. Run `git lfs ls-files` on a fresh clone and
   diff against `find . -type f -size +1M`.
6. **CI hardening.** Add a `focused-core-tests` job (the 7 tests above)
   that runs on every PR. Add an `optional-extras-matrix` job that
   tests `pip install -e ".[ocr]"`, `.[nlp]`, `.[search]` etc. Add a
   `deploy-smoke-check` job that hits the HF Space URL after deploy.

---

## 7. Migration notes (v1.0.0 → v1.1.0-rc)

See `MIGRATION_NOTES_v1.1.0-rc.md` for the full diff. Summary:

- **No breaking API changes.** All pre-P0 module-level names
  (`paddle_ocr`, `spell_checker`, `HAS_TESSERACT`, `proofreader`, `ner`,
  `HAS_LLM`, `paddle_ocr`, `image_preprocessor`, `HAS_PREPROCESSOR`,
  `DEVICE`, `TRANSLATION_MODELS`, `translate_text`) continue to resolve
  via PEP 562 module `__getattr__`. Existing call sites keep working.
- **Behavior change:** `app/services/ocr_service.py` no longer
  initializes any engine at import time. Code that depended on
  `paddle_ocr is not None` immediately after `import` will now see
  `None` until the first OCR call. This is the intended fix.
- **`save_to_hf()` return string format changed slightly.** The success
  message now reports staged count + (if applicable) flush result,
  rather than just the new HF total. Gradio bindings display the string
  verbatim, so no UI changes needed.
- **`pytest.ini` deleted.** All config moved to `pyproject.toml`. IDE
  plugins that pointed at `pytest.ini` need to be repointed (most do
  this automatically).
- **`HF_TOKEN` env var still respected.** No change to auth.

### Operational caveats
- The staging directory defaults to `~/.omni/hf_dataset_queue/`. On
  shared deployments, set `OMNI_HF_QUEUE_DIR` to a persistent location
  (e.g. a mounted volume) so queued rows survive container restarts.
- The auto-flush threshold defaults to 25. For low-traffic deployments
  set `OMNI_HF_FLUSH_THRESHOLD=1` to flush on every save (higher
  network cost, lower latency). For high-traffic deployments set it to
  100+ to amortize push cost.
- `flush_queue()` is safe to call concurrently — it holds a lock for
  the duration of the read+push+archive+clear sequence. Concurrent
  `save_to_hf()` calls during a flush will block briefly.
