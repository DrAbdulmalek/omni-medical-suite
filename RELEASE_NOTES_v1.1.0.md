# Release Notes — v1.1.0 (stable)

**Release date:** 2026-07-19
**Tag:** `v1.1.0` (annotated, points to main HEAD post-doc-update)
**Previous release:** v1.1.0-rc1 (2026-07-19, same day)
**Predecessor:** v1.0.0 (commit `f98e2f9`, 2026-07-05)

This is the **first stable release** of the Omni Medical Suite hardening
sprint. It promotes v1.1.0-rc1 to stable after verifying all 174 tests
pass (163 unit + 11 AppImage smoke) and the AppImage CI build is fully
green.

---

## 🎯 Highlights

1. **Lazy OCR factories** — PaddleOCR, Tesseract, spell-checker, proofreader, NER, and translator are now constructed on first use, not at import. Failures are cached (no retry storms).
2. **Structured decision log** — every RTL fix, dedup batch, field extraction, and HF staging decision emits a JSON line with reasons + duration.
3. **HF dataset staging queue** — `save_to_hf()` no longer blocks on network; appends to local JSONL, flushes in batches of 25 (configurable).
4. **Field extractor hardening** — multi-line value support, bilingual Arabic/English labels, per-field confidence scoring, safe template signatures.
5. **Benchmark reporter** — `to_csv()`, `to_json()`, `aggregate_metrics()` for OCR comparison pipelines.
6. **AppImage for desktop scanner** — pre-built 177 MB binary published as a Release asset; `bash build_appimage.sh --version-from-git --smoke-test` for from-source builds.
7. **CI matrix** — Python 3.10/3.11/3.12 on Ubuntu + Manjaro/Arch container + HF Space Dockerfile smoke + Colab notebook validation + LFS audit.
8. **Git LFS coverage** — 50+ patterns across 10 categories; `audit-lfs-coverage.sh` enforces in CI.

### What changed between rc1 and stable

| Item | rc1 | stable |
|------|-----|--------|
| AppImage build in CI | ❌ Failed at appimagetool step (3 issues) | ✅ Fully green (run 29681501968) |
| `.desktop` file placement | Only in `usr/share/applications/` | Also at AppDir root (appimagetool requirement) |
| `ARCH` env var | Not set → "multiple architectures found" | Forced to `x86_64` |
| Icon naming at AppDir root | `MedicalDocProcessor.png` | `com.omnimedical.docprocessor.png` (matches `Icon=` field) |
| AppImage artifact | Not built | ✅ 177 MB ELF binary, downloadable as Release asset |
| README direct-download | Not present | ✅ `wget` + `sha256sum -c` + `chmod +x` quick-start |
| Test count | 161 unit + 11 conditional smoke | **174 pass** (163 unit + 11 smoke, all green) |
| Backup branch | `backup/before-p2-work` | Added `backup/before-v1.1.0-stable` |

4 post-rc1 commits on `main`:
- `bf34b84` fix(appimage): place .desktop + icon at AppDir root for appimagetool
- `9225884` fix(appimage): force ARCH env var for appimagetool
- `a121b8c` fix(appimage): name root icon com.omnimedical.docprocessor.png
- `25a6198` docs(readme): add direct download link for v1.1.0-rc1 AppImage

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
| P2-2 | CI matrix workflow (`ci-matrix.yml`) with 6 jobs: Python × OS, Manjaro/Arch container, HF Space Dockerfile, Colab notebook JSON, LFS audit, summary |
| P2-3 | Final RC Checklist + Release Notes |
| P2-4 | Git LFS migration plan (`docs/LFS_MIGRATION_PLAN.md`) — staged approach without forced history rewrite |

### Stable promotion (4 commits post-rc1)

| Commit | Summary |
|--------|---------|
| `bf34b84` | Place `.desktop` + icon at AppDir root (appimagetool requirement) |
| `9225884` | Force `ARCH=x86_64` env var (PyInstaller bundles multi-arch libs) |
| `a121b8c` | Name root icon `com.omnimedical.docprocessor.png` (matches `Icon=` field) |
| `25a6198` | Add direct download link to README |

---

## 🧪 Test status

| Phase | Tests | Status |
|-------|-------|--------|
| P0    | 95    | ✅ Pass |
| P1    | 66    | ✅ Pass |
| P2 (AppImage smoke) | 11 | ✅ Pass (with `MEDICAL_DOC_APPIMAGE` env var) |
| P0-extra | 28 | ✅ Pass |
| **Total** | **174** | **All pass** |

Local verification (run before tagging v1.1.0):

```bash
# Unit tests (163 pass in 1.92s)
pytest tests/test_decision_log.py tests/test_decision_instrumentation_p1.py \
       tests/test_field_extractor_p1.py tests/test_field_extractor_core.py \
       tests/test_benchmark_reporter_p1.py tests/test_hf_dataset_staging.py \
       tests/test_lazy_ocr_service.py tests/test_translation_service.py \
       tests/test_scanner_tab.py -v

# AppImage smoke (11 pass in 1.28s)
MEDICAL_DOC_APPIMAGE=MedicalDocProcessor-v1.1.0-x86_64.AppImage \
    pytest packages/desktop/test_appimage_smoke_pytest.py -v
```

---

## 🚀 Deployment surfaces

### 1. HuggingFace Space (primary web UI)
- **URL:** https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
- **Sync:** `./scripts/sync-hf-space.sh --force && git commit -m "chore(hf-space): sync" && git push origin main`
- **Drift check:** `./scripts/sync-hf-space.sh --verify` ✅ clean
- **CI smoke:** `ci-matrix.yml → hf-space-smoke` job builds Dockerfile + verifies `import app`
- **Drift policy:** `hf-space/app.py` is an intentional deploy snapshot (frozen, inline logic for HF CPU tier); `app/gradio_full_hitl.py` is the canonical source with service-layer delegation. See `STATE_OF_TRUTH.md` for the full drift table.

### 2. Manjaro Desktop AppImage (offline GUI)
- **Direct download (177 MB):** https://github.com/DrAbdulmalek/omni-medical-suite/releases/download/v1.1.0/MedicalDocProcessor-v1.1.0-x86_64.AppImage
- **SHA256:** https://github.com/DrAbdulmalek/omni-medical-suite/releases/download/v1.1.0/MedicalDocProcessor-v1.1.0-x86_64.AppImage.sha256
- **Verify:** `sha256sum -c MedicalDocProcessor-v1.1.0-x86_64.AppImage.sha256`
- **Run:** `chmod +x MedicalDocProcessor-*.AppImage && ./MedicalDocProcessor-*.AppImage`
- **Docs:** [`docs/APPIIMAGE_MANJARO.md`](docs/APPIIMAGE_MANJARO.md)
- **CI smoke:** `appimage-build.yml` builds on push + tags, uploads as artifact (30-day retention); v1.1.0 release asset uploaded manually via GitHub API.

### 3. Google Colab (cloud notebook)
- **Notebooks:** `notebooks/generate_training_data_colab.ipynb`, `notebooks/ocr_ensemble_colab.ipynb`, `notebooks/omnimedical_v2_colab.ipynb`
- **Validation:** `python scripts/validate_notebooks.py` (3/3 valid)
- **CI smoke:** `ci-matrix.yml → colab-smoke` job
- **Quick start (stable):**
  ```python
  !git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
  %cd omni-medical-suite
  !git checkout v1.1.0  # stable release
  !pip install -e packages/scanner_fixer
  !pip install -r requirements-scanner.txt
  !apt-get install -y tesseract-ocr tesseract-ocr-ara
  import sys; sys.path.insert(0, '.')
  from app.advanced_review_app import build_app, demo
  build_app().launch(share=True, debug=True)
  ```

### 4. Mobile / PWA (via HF Space)
- No separate deployment — mobile apps point to the HF Space URL.
- **URL:** `https://DrAbdulmalek-omni-medical-ocr.hf.space`

---

## 📋 Migration notes (v1.0.0 → v1.1.0 stable)

### Breaking changes
**None.** All P0/P1/P2/stable changes are backward-compatible:
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

### Pre-built AppImage (v1.1.0 stable)
1. Download `MedicalDocProcessor-v1.1.0-x86_64.AppImage` (177 MB) from the GitHub Release:
   https://github.com/DrAbdulmalek/omni-medical-suite/releases/download/v1.1.0/MedicalDocProcessor-v1.1.0-x86_64.AppImage
2. Download the checksum:
   https://github.com/DrAbdulmalek/omni-medical-suite/releases/download/v1.1.0/MedicalDocProcessor-v1.1.0-x86_64.AppImage.sha256
3. Verify: `sha256sum -c MedicalDocProcessor-v1.1.0-x86_64.AppImage.sha256`
4. Run: `chmod +x MedicalDocProcessor-v1.1.0-x86_64.AppImage && ./MedicalDocProcessor-v1.1.0-x86_64.AppImage`

### Build from source
```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
git checkout v1.1.0   # stable release
cd packages/desktop
bash build_appimage.sh --version-from-git --smoke-test
```

---

## ⚠️ Known issues

1. **HF Space drift (intentional, documented).** `hf-space/app.py` (306 LOC, frozen snapshot for HF Spaces CPU tier) duplicates logic that lives in `app/services/*` (canonical, refactored). The two implementations have structural divergence only — same public API, same behavioral contract. See `STATE_OF_TRUTH.md` §1 for the full drift table. **Not a regression — by design.**

2. **AppImage smoke test in CI** — `appimage-build.yml` smoke step extracts the AppImage and verifies the AppDir layout, but does not launch the GUI (no display in CI). For full GUI smoke, run locally with `--smoke-test` flag.

3. **Engine router not instrumented** — `packages/core/engine_router.py` does not yet emit `decision='engine_selection'`. Tracked as Post-stable P3-1 item (target: v1.1.1).

4. **LFS migration deferred** — Existing large files in history are NOT migrated to LFS (would require `git lfs migrate import` which rewrites history). New files matching `.gitattributes` patterns are automatically tracked by LFS. See `docs/LFS_MIGRATION_PLAN.md` for the staged migration approach (Phase C/D targeted for v1.2.0).

5. **AppImage size** — 177 MB is larger than ideal due to bundled PySide6 + opencv-python-headless + Pillow. Future work: tree-shake unused Qt modules, consider `-nodata` for opencv.

---

## 🗺️ Roadmap (post-v1.1.0)

| Priority | Item | Target |
|----------|------|--------|
| P3-1 | Instrument `engine_router.py` with `log_decision()` | v1.1.1 |
| P3-2 | HF Space live URL smoke (HTTP 200 + endpoint check) | v1.1.1 |
| P3-3 | Performance regression baseline (P95 latency) | v1.2.0 |
| P3-4 | LFS migration of legacy tracked blobs (coordinated) | v1.2.0 |
| P3-5 | Arabic medical NER fine-tuning | v1.2.0 |

---

## 🙏 Acknowledgments

- **P0 hardening patch** originally authored by Grok, reviewed and applied by Claude/Z.ai
- **P1 + P2** executed by Z.ai
- **rc1 → stable promotion** executed by Z.ai (4 AppImage build fixes + final verification)
- **Test infrastructure** benefited from the unified `pyproject.toml` pytest config

---

## 📚 References

- [Release Candidate Checklist](RELEASE_CANDIDATE_CHECKLIST.md)
- [AppImage Manjaro Build Guide](docs/APPIIMAGE_MANJARO.md)
- [LFS Migration Plan](docs/LFS_MIGRATION_PLAN.md)
- [Deployment Source of Truth](docs/DEPLOYMENT.md)
- [State of Truth matrix](STATE_OF_TRUTH.md)
- [Roadmap](docs/ROADMAP.md)
- [Previous RC: v1.1.0-rc1 Release Notes](RELEASE_NOTES_v1.1.0-rc1.md)
