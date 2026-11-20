# Release Notes — v1.1.0-rc1

**Release date:** 2026-07-19
**Branch:** `feat/rc-hardening-p0`
**Tag (pending):** `v1.1.0-rc1`
**Previous release:** v1.0.0 (commit `f98e2f9`)

This is the first Release Candidate of the Omni Medical Suite hardening sprint. It consolidates **15 commits** across three phases (P0 + P1 + P2), adding **161 passing tests** (up from ~95 pre-P0), structured decision logging, an AppImage build pipeline, and a multi-platform CI matrix.

---

## 🎯 Highlights

1. **Lazy OCR factories** — PaddleOCR, Tesseract, spell-checker, proofreader, NER, and translator are now constructed on first use, not at import. Failures are cached (no retry storms).
2. **Structured decision log** — every RTL fix, dedup batch, field extraction, and HF staging decision emits a JSON line with reasons + duration.
3. **HF dataset staging queue** — `save_to_hf()` no longer blocks on network; appends to local JSONL, flushes in batches of 25 (configurable).
4. **Field extractor hardening** — multi-line value support, bilingual Arabic/English labels, per-field confidence scoring, safe template signatures.
5. **Benchmark reporter** — `to_csv()`, `to_json()`, `aggregate_metrics()` for OCR comparison pipelines.
6. **AppImage for desktop scanner** — `bash build_appimage.sh --version-from-git --smoke-test` produces a portable Linux AppImage with SHA256 checksum.
7. **CI matrix** — Python 3.10/3.11/3.12 on Ubuntu + Manjaro/Arch container + HF Space Dockerfile smoke + Colab notebook validation.
8. **Git LFS coverage** — 50+ patterns across 10 categories; `audit-lfs-coverage.sh` enforces in CI.

---

## 📦 What's new

### Phase P0 — Hardening foundations (7 items)

| Item | Summary |
|------|---------|
| P0-1 | Deploy source of truth unified (`app/gradio_full_hitl.py` canonical, `hf-space/app.py` snapshot) |
| P0-2 | Scanner fixer Gradio integration: manual crop, advanced edges, ZIP save (40 tests) |
| P0-3 | Lazy OCR factories: `get_paddle_ocr()`, `get_image_preprocessor()`, `has_tesseract()`, `get_spell_checker()`, `get_proofreader()`, `get_ner()` |
| P0-4 | Translation service extracted (~130 LOC) with lazy `transformers + torch` import |
| P0-5 | HF dataset staging queue (`save_to_hf` → JSONL → `flush_queue` batched push) |
| P0-6 | Structured decision log (`app/core/decision_log.py`) with JSON schema |
| P0-7 | pytest config unified in `pyproject.toml` (duplicate `pytest.ini` removed) |

### Phase P1 — Quality + observability (4 items)

| Item | Summary |
|------|---------|
| P1-1 | Field extractor: multi-line values, bilingual labels, confidence scores, safe `build_template_signature()` |
| P1-2 | Benchmark reporter: `to_csv()`, `to_json()`, `aggregate_metrics()` with percentiles |
| P1-3 | Instrumented RTL fixer, deduplication, and field extractor with `log_decision()` calls |
| P1-4 | `.gitattributes` expanded to 50+ patterns + `audit-lfs-coverage.sh` script |

### Phase P2 — Release polish (4 items)

| Item | Summary |
|------|---------|
| P2-1 | AppImage build script with Manjaro/Arch detection, `--version-from-git`, `--smoke-test`, SHA256 checksum, signing support |
| P2-2 | CI matrix workflow (`ci-matrix.yml`) with 5 jobs: Python × OS, Manjaro/Arch container, HF Space Dockerfile, Colab notebook JSON, summary |
| P2-3 | Final RC Checklist + these Release Notes |
| P2-4 | Git LFS migration plan (`docs/LFS_MIGRATION_PLAN.md`) — staged approach without forced history rewrite |

---

## 🧪 Test status

| Phase | Tests | Status |
|-------|-------|--------|
| P0    | 95    | ✅ Pass (3.02s) |
| P1    | 66    | ✅ Pass |
| P2    | 11 (AppImage smoke) | ⏸ Skipped without `MEDICAL_DOC_APPIMAGE` env var |
| **Total** | **172** | **161 pass + 11 conditional** |

Run locally:
```bash
pytest tests/test_scanner_tab.py tests/test_decision_log.py \
       tests/test_translation_service.py tests/test_hf_dataset_staging.py \
       tests/test_lazy_ocr_service.py \
       tests/test_field_extractor.py tests/test_field_extractor_core.py \
       tests/test_benchmark_reporter.py tests/test_decision_instrumentation.py \
       -v
```

With a built AppImage:
```bash
MEDICAL_DOC_APPIMAGE=packages/desktop/MedicalDocProcessor-*.AppImage \
    pytest packages/desktop/test_appimage_smoke_pytest.py -v
```

---

## 🚀 Deployment surfaces

### 1. HuggingFace Space (primary web UI)
- **URL:** https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
- **Sync:** `./scripts/sync-hf-space.sh --force && git commit -m "chore(hf-space): sync" && git push origin main`
- **Drift check:** `./scripts/sync-hf-space.sh --verify`
- **CI smoke:** `ci-matrix.yml → hf-space-smoke` job builds Dockerfile + verifies `import app`

### 2. Manjaro Desktop AppImage (offline GUI)
- **Build:** `cd packages/desktop && bash build_appimage.sh --version-from-git --smoke-test`
- **Output:** `MedicalDocProcessor-<version>-x86_64.AppImage` (~250-400 MB)
- **Verify:** `sha256sum -c MedicalDocProcessor-*.AppImage.sha256`
- **Docs:** [`docs/APPIIMAGE_MANJARO.md`](docs/APPIIMAGE_MANJARO.md)
- **CI smoke:** `appimage-build.yml` builds on push + tags, uploads as artifact (30-day retention)

### 3. Google Colab (cloud notebook)
- **Notebooks:** `notebooks/generate_training_data_colab.ipynb`, `notebooks/ocr_ensemble_colab.ipynb`, `notebooks/omnimedical_v2_colab.ipynb`
- **Validation:** `python scripts/validate_notebooks.py` (3/3 valid)
- **CI smoke:** `ci-matrix.yml → colab-smoke` job

### 4. Mobile / PWA (via HF Space)
- No separate deployment — mobile apps point to the HF Space URL.
- **URL:** `https://DrAbdulmalek-omni-medical-ocr.hf.space`

---

## 📋 Migration notes (v1.0.0 → v1.1.0-rc1)

### Breaking changes
**None.** All P0/P1/P2 changes are backward-compatible:
- Module-level attributes (`paddle_ocr`, `HAS_TESSERACT`, etc.) preserved via PEP 562 `__getattr__`
- `save_to_hf()` signature unchanged; `flush_queue()` and `count_pending()` are additive
- `process_single_image()` adds 5 optional parameters with defaults

### Behavioral changes (no API change)

1. **HF dataset writes are batched.** `save_to_hf()` appends to local JSONL; pushes when `OMNI_HF_FLUSH_THRESHOLD` (default 25) rows accumulate. Set `OMNI_HF_FLUSH_THRESHOLD=1` for legacy per-save behavior.

2. **OCR engines load on first use.** First call to `get_paddle_ocr()` etc. is slower (model loading); subsequent calls cached. Failed constructions are cached too (no retry).

3. **Decision log emits to stderr by default.** Attach a JSON-lines file handler to `app.decision_log` logger to ship decisions to your log aggregator:
   ```python
   import logging
   fh = logging.FileHandler("/var/log/omni/decisions.jsonl")
   fh.setFormatter(logging.Formatter("%(message)s"))
   logging.getLogger("app.decision_log").addHandler(fh)
   ```

### New environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OMNI_HF_QUEUE_DIR` | `~/.omni/hf_dataset_queue` | Directory for staging JSONL files |
| `OMNI_HF_FLUSH_THRESHOLD` | `25` | Number of staged rows that trigger a batched push |
| `OMNI_APPIMAGE_OFFSCREEN` | (unset) | Set to `1` to force `QT_QPA_PLATFORM=offscreen` in AppImage |
| `APPIMAGETOOL_SIGN_KEY` | (unset) | GPG key ID for AppImage signing (optional) |
| `MEDICAL_DOC_APPIMAGE` | (unset) | Path to built AppImage (enables pytest smoke tests) |

---

## 📥 Download

### Pre-built AppImage (when CI publishes)
1. Go to **Actions tab → latest `appimage-build.yml` run**
2. Download artifact: `MedicalDocProcessor-<version>-x86_64.AppImage`
3. Verify checksum: `sha256sum -c MedicalDocProcessor-*.AppImage.sha256`

### Build from source
```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
git checkout feat/rc-hardening-p0  # or tag v1.1.0-rc1 once cut
cd packages/desktop
bash build_appimage.sh --version-from-git --smoke-test
```

---

## ⚠️ Known issues

1. **hf-space drift** (pre-existing, not a P2 regression) — `hf-space/packages/core/engine_router.py` has minor drift; `hf-space/packages/nlp/translation_corrector/` was deleted in monorepo but snapshot still has it. **Fix:** `./scripts/sync-hf-space.sh --force && git commit && git push`.

2. **AppImage smoke test in CI** — `appimage-build.yml` smoke step extracts the AppImage and verifies the AppDir layout, but does not launch the GUI (no display in CI). For full GUI smoke, run locally with `--smoke-test` flag.

3. **Engine router not instrumented** — `packages/core/engine_router.py` does not yet emit `decision='engine_selection'`. Tracked as Post-RC item.

4. **LFS migration deferred** — Existing large files in history are NOT migrated to LFS (would require `git lfs migrate import` which rewrites history). New files matching `.gitattributes` patterns are automatically tracked by LFS. See `docs/LFS_MIGRATION_PLAN.md` for the staged migration approach.

---

## 🗺️ Roadmap (post-rc1)

| Priority | Item | Target |
|----------|------|--------|
| P3-1 | Instrument `engine_router.py` with `log_decision()` | v1.1.0-rc2 |
| P3-2 | HF Space live URL smoke (HTTP 200 + endpoint check) | v1.1.0-rc2 |
| P3-3 | Performance regression baseline (P95 latency) | v1.1.0 |
| P3-4 | LFS migration of legacy tracked blobs (coordinated) | v1.2.0 |
| P3-5 | Arabic medical NER fine-tuning | v1.2.0 |

---

## 🙏 Acknowledgments

- **P0 hardening patch** originally authored by Grok, reviewed and applied by Claude/Z.ai
- **P1 + P2** executed by Z.ai (this session)
- **Test infrastructure** benefited from the unified `pyproject.toml` pytest config

---

## 📚 References

- [Release Candidate Checklist](RELEASE_CANDIDATE_CHECKLIST.md)
- [AppImage Manjaro Build Guide](docs/APPIIMAGE_MANJARO.md)
- [LFS Migration Plan](docs/LFS_MIGRATION_PLAN.md)
- [Deployment Source of Truth](docs/DEPLOYMENT.md)
- [State of Truth matrix](STATE_OF_TRUTH.md)
