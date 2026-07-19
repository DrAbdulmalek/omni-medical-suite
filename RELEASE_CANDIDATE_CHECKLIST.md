# Release Candidate Checklist — v1.1.0-rc

**Branch:** `feat/rc-hardening-p0`
**Latest commit:** `bcd5c73` (2026-07-19) — P1-4 complete
**Test status:** 161/161 P0+P1 tests pass (3.02s)
- P0: 95 tests (scanner_tab + decision_log + translation + hf_dataset_staging + lazy_ocr_service)
- P1: 66 tests (field_extractor + benchmark_reporter + decision_instrumentation)

**P0 status:** 7/7 complete (deploy source of truth, scanner integration, lazy loading, translation service, HF staging, decision log, pytest unification)
**P1 status:** 4/4 complete (field extractor, benchmark reporter, decision instrumentation, Git LFS audit)
**P2 status:** 6 items remaining (CI parity check, CI matrix, deploy smoke checks, AppImage regression, LFS migration, engine_router instrumentation)

---

## ✅ Done in P0 (this branch)

### P0-1 — Deploy source of truth unified
- [x] `scripts/sync-hf-space.sh` enhanced with `--verify` and `--force` modes
- [x] `docs/DEPLOYMENT.md` adds "🎯 Source of Truth" section at top
- [x] `STATE_OF_TRUTH.md` already documents runtime state matrix
- [x] Sync mapping documented: `src/ocr`, `packages/{vision,nlp,core}`, `config` → `hf-space/`
- [x] HF-specific overrides (`app.py`, `Dockerfile`, `requirements.txt`) marked as not-synced

### P0-2 — Scanner fixer Gradio integration enhanced
- [x] `app/scanner_tab.py` created — 397 LOC, pure functions, no Gradio imports at module level
- [x] Manual crop via 4 number inputs (x/y/w/h) — `apply_manual_crop()` supports dict/tuple/list formats
- [x] Advanced edge detection: Canny + Adaptive Threshold + Morphology + Hough Lines
- [x] `apply_advanced_edges()` composable composition with metadata dict
- [x] `save_processed_image()` with path-traversal sanitization
- [x] `build_zip_from_dir()` for "save all as ZIP"
- [x] Tab 1 in `advanced_review_app.py` upgraded: manual crop accordion + edge options accordion + save button
- [x] `requirements-scanner.txt` documenting optional deps
- [x] 40 unit tests in `tests/test_scanner_tab.py` (all pass)

### P0-3 — Lazy OCR factories (commit `6a23c52`)
- [x] `app/services/ocr_service.py` — `get_paddle_ocr()`, `get_image_preprocessor()`, `has_tesseract()`, `get_spell_checker()`
- [x] `app/services/review_service.py` — `get_proofreader()`, `get_ner()`
- [x] PEP 562 `__getattr__` preserves backward-compat module-level names
- [x] Thread-safe singleton + failure caching

### P0-4 — Translation service extracted (commit `6a23c52`)
- [x] `app/services/translation_service.py` created (~130 LOC extracted)
- [x] `transformers + torch` imported lazily inside `load_translator()`
- [x] `app/gradio_full_hitl.py` slimmed 585 → 466 LOC
- [x] Public API: `translate_text`, `correct_translation`, `load_translator`, `get_translation_corrector`, `reset_lazy_cache`

### P0-5 — HF dataset staging queue (commit `6a23c52`)
- [x] `save_to_hf()` now appends to local JSONL (~/.omni/hf_dataset_queue/pending.jsonl)
- [x] `flush_queue()` does dedup (via content_hash) + single batched push
- [x] `count_pending()` for monitoring
- [x] Append-only staging — no correction ever lost
- [x] Pre-P0 O(N) per save → post-P0 O(1) per save + O(N) per flush (amortized)

### P0-6 — Structured decision log (commit `6a23c52`)
- [x] `app/core/decision_log.py` — `log_decision()` emits JSON line per decision
- [x] Logger: `app.decision_log` (separate from root)
- [x] Schema: `{ts, decision, outcome, reasons, inputs, skipped, duration_ms, session_id}`
- [x] 12 unit tests in `tests/test_decision_log.py`

### P0-7 — pytest configuration unified (commit `6a23c52`)
- [x] Duplicate `pytest.ini` removed; config consolidated in `pyproject.toml`
- [x] All 4 P0 test files run cleanly: 55 new tests, 0 regressions

---

## ⏳ P1 — Done in this branch (4/4 complete)

1. ✅ **P1-1: Field extractor hardening** (`src/ocr/field_extractor.py`)
   - Multi-line value support for diagnosis/medications (lookahead pattern)
   - Bilingual labels: Arabic + English shorthand (Pt Name, File No, DOB, Dr, Dx, Rx)
   - Per-field confidence scoring in [0.0, 1.0] via `_confidence_for()`
   - Safe `build_template_signature()`: `re.escape()` + placeholder + length-desc sort
   - Tests: `tests/test_field_extractor_p1.py` (29 tests, all pass)
   - Commit: `5b70816`

2. ✅ **P1-2: Benchmark reporter** (`omni_medical_suite/preprocessing/compare_raw_vs_printed.py`)
   - `to_csv(results, path, *, flatten_field_aware=True)` — CSV export with field-aware flattening
   - `to_json(results, path, *, indent=2)` — JSON export preserving Arabic Unicode
   - `aggregate_metrics(results, *, percentiles=(0.5, 0.9, 0.95))` — min/max/mean/median/stdev/percentiles
   - Convenience rollups: `improvement_mean`, `processed_better_count`, `processed_better_ratio`
   - Tests: `tests/test_benchmark_reporter_p1.py` (25 tests, all pass)
   - Commit: `e9ffdde`

3. ✅ **P1-3: RTL/dedup/field_extractor decision logging**
   - `src/ocr/rtl_utils.py` — `analyze_and_fix()` emits `decision='rtl_fix'`
   - `src/ocr/deduplication.py` — `deduplicate()` emits `decision='dedup_batch'`
   - `src/ocr/field_extractor.py` — `extract_fields()` emits `decision='field_extraction'`
   - All instrumentation wrapped in `try/except ImportError` (graceful degradation)
   - Bug fix in `app/core/decision_log.py`: `_coerce_outcome()` now handles dicts
     (previously stringified them); `_safe_jsonable()` handles nested lists/dicts
     with circular-reference protection
   - Tests: `tests/test_decision_instrumentation_p1.py` (12 tests, all pass)
   - Commit: `e8ea063`

4. ✅ **P1-4: Git LFS audit + .gitattributes cleanup**
   - Expanded `.gitattributes` from 11 → 50+ patterns across 10 categories
   - Added: `*.ipynb`, ML weights (`.h5/.pt/.safetensors/.onnx/...`), media (`.mp4/.mp3/...`),
     archives (`.zip/.tar/.7z/...`), office docs (`.docx/.xlsx/.pptx`),
     path-specific patterns for `tectonic` binary and `tokenizer.json`
   - New `scripts/audit-lfs-coverage.sh` — verifies coverage, `--strict` mode for CI
   - Audit result: **32/32 large files covered, 0 uncovered**
   - Commit: `bcd5c73`

**P1 test total: 66 new tests (29 + 25 + 12), all pass. Combined with P0's 95 tests: 161/161 pass in 3.02s.**

---

## 🎯 P2 — Post-RC polish (next sprint)

1. **Deploy parity CI check** — Add GitHub Actions job running `./scripts/sync-hf-space.sh --verify` on PRs touching `hf-space/**`, `src/ocr/**`, `packages/**`, or `config/**`
2. **CI matrix** — `pip install -e ".[ocr]"`, `.[nlp]`, `.[search]` test matrix
3. **Deploy smoke checks** — hit HF Space URL after deploy, verify 200 + key endpoint
4. **AppImage for desktop scanner** — already built, needs regression test
5. **LFS migration of existing tracked files** — `git lfs migrate import` for files now covered by new patterns (rewrites history, coordinate with collaborators)
6. **Instrument engine_router** — emit `decision='engine_selection'` in `packages/core/engine_router.py` (the only remaining uninstrumented decision site)

---

## 🚀 Run commands

### Local Gradio (advanced_review_app with new scanner tab)

```bash
# 1. Install scanner_fixer (editable)
pip install -e packages/scanner_fixer

# 2. Install scanner-specific deps
pip install -r requirements-scanner.txt

# 3. Install tesseract binary (system package)
# Debian/Ubuntu:
sudo apt install tesseract-ocr tesseract-ocr-ara
# Arch/Manjaro:
sudo pacman -S tesseract tesseract-data-ara
# macOS:
brew install tesseract tesseract-lang

# 4. Run advanced review app (Tab 1 has new scanner features)
python app/advanced_review_app.py
# → Open http://localhost:7860
# → Tab "🔬 معالج الصور" → expand "✂️ قص يدوي" + "⚙️ كشف الحواف المتقدم"
```

### HuggingFace Space deployment

```bash
# 1. Sync monorepo → hf-space/
./scripts/sync-hf-space.sh

# 2. Verify drift (should be clean)
./scripts/sync-hf-space.sh --verify

# 3. Commit + push to main (triggers deploy-to-hf.yml workflow)
git add hf-space/
git commit -m "chore(hf-space): sync from monorepo"
git push origin main

# 4. Watch deployment
# https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
```

### Google Colab

```python
# In a Colab cell:
!git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
%cd omni-medical-suite
!pip install -e packages/scanner_fixer
!pip install -r requirements-scanner.txt
!apt-get install -y tesseract-ocr tesseract-ocr-ara

# Run Gradio (use share=True for public URL)
import sys; sys.path.insert(0, '.')
from app.advanced_review_app import build_app, demo
build_app().launch(share=True, debug=True)
```

### Mobile (Telegram/PWA)

```bash
# Mobile uses the HF Space backend — no separate deployment
# Just point your mobile app/PWA to:
# https://DrAbdulmalek-omni-medical-ocr.hf.space
```

---

## 📋 Migration notes (v1.0.0 → v1.1.0-rc)

### Breaking changes
**None.** All P0 changes are backward-compatible:

- `app/services/ocr_service.py` keeps `paddle_ocr`, `HAS_TESSERACT`, `spell_checker`, `proofreader`, `ner`, `HAS_LLM` as module-level attributes via PEP 562 `__getattr__`. Existing call sites work unchanged.
- `app/gradio_full_hitl.py` still imports `translate_text` from its old location (re-exported from `translation_service`).
- `app/services/hf_dataset_service.py` keeps `save_to_hf()` signature unchanged; new functions `flush_queue()` and `count_pending()` are additive.
- `app/advanced_review_app.py` `process_single_image()` adds 5 new optional parameters with defaults — existing call sites work unchanged.

### Behavioral changes (no API change)

1. **HF dataset writes are now batched.** A `save_to_hf()` call appends to a local JSONL and only pushes when `OMNI_HF_FLUSH_THRESHOLD` (default 25) rows accumulate. To flush manually:
   ```python
   from app.services.hf_dataset_service import flush_queue
   flush_queue()
   ```
   Or set `OMNI_HF_FLUSH_THRESHOLD=1` for legacy per-save behavior (useful for debugging).

2. **OCR engines are constructed on first use, not at import.** First call to `get_paddle_ocr()` etc. will take longer (model loading); subsequent calls are cached. Failures are cached too — a missing dependency is not retried.

3. **Decision log emits to stderr by default.** In production, attach a JSON-lines file handler to the `app.decision_log` logger to ship decisions to your log aggregator.

### New environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OMNI_HF_QUEUE_DIR` | `~/.omni/hf_dataset_queue` | Directory for staging JSONL files |
| `OMNI_HF_FLUSH_THRESHOLD` | `25` | Number of staged rows that trigger a batched push |

### Pre-existing drift in `hf-space/` (NOT a P0 regression)

The verification step in `scripts/sync-hf-space.sh --verify` revealed:
- `hf-space/packages/nlp/translation_corrector/` was deleted in the monorepo but the snapshot still has it
- `hf-space/packages/core/mobile/` was added in the monorepo but missing from the snapshot
- `hf-space/packages/core/engine_router.py` has minor drift

**Fix:** Run `./scripts/sync-hf-space.sh` (default mode) and commit the result. This will bring the snapshot in sync.

### Rollback procedure

If v1.1.0-rc introduces a regression, roll back by checking out the previous main:

```bash
git checkout main
git reset --hard origin/main  # f98e2f9 (pre-P0)
```

Or revert individual P0 commits:

```bash
git revert 4321b31  # P0-2: scanner tab
git revert e2e1d1b  # P0-1: deploy source of truth
git revert 6a23c52  # P0: lazy loading + translation + HF staging + decision log
```

The backup branch `backup/before-p0-1-p0-2-work` points at `6a23c52` (post-P0 patch, pre-P0-1/P0-2) if you want to roll back only the latest two commits.
