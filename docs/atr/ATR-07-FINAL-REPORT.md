# ATR-07 — FINAL REPORT (Arabic TrOCR Advanced Features) — UNIFIED

> Generated 2026-09-23 — **dual-session execution** (Z.ai "Omni Audit Bot" +
> Qwen "ATR Autonomous Agent") under the ATR-01b reconciliation protocol
> (fetch-before-push, additive commits only, adopt-and-skip on duplicate phases,
> independent cross-verification). This document is the **merged** final report
> of both sessions; per-session raw reports are preserved in git history
> (`8f2235f` Z.ai, `5b352c5`/`50c0d71` Qwen).

## === ATR FINAL STATUS ===

- **BRANCH**: `feature/atr-trocr-advanced` (from `main` @ `39640a6dbba7…`). **main untouched** — verified empty diff vs main by both sessions (`git diff main..HEAD -- Dockerfile docker-compose.yml .dockerignore packages/omni_ocr/adapter.py apps/ocr-pipeline` = empty).
- **HEAD / REMOTE-VERIFIED-SHA**: see `PROGRESS.md` + `git ls-remote origin feature/atr-trocr-advanced` (re-verified after every push; final tip = this commit).
- **ATR SUITE**: **38/38 passed in BOTH environments**:
  - Z.ai env: Python 3.12.14 / torch 2.14.0+cpu / **transformers 5.12.1**
  - Qwen env: Python 3.11.2 / torch 2.14.0+cpu / **transformers 4.57.6**
  - (4 batch + 4 tokenizer + 15 training-UI + 12 docker + 3 integration-smoke)
- **FULL SUITE (Qwen)**: **793 passed**, failure set IDENTICAL to pre-ATR baseline (164 failed / 26 errors, all pre-existing missing-optional-dep) → **zero regressions**.
- **PERSISTENCE**: **OK** — owner token (fingerprint `sha256:5821a50287a8c836…`, never printed/stored in `.git/config`) worked on every push from both sessions; every commit remote-verified; handover bundles under `download/OMNI-EXECUTION/handovers/<sha>/`.

## PER-PHASE TABLE (dual-session ledger)

| Phase | Status | Commit | Tests | Notes |
|---|---|---|---|---|
| ATR-01 Pre-Flight + PROGRESS.md | PROVEN (Z.ai) | `11da6ac` | n/a | branch from origin/main 39640a6 |
| ATR-01b Reconciliation | PROVEN (Qwen) | `558dda5` | n/a | dual-session protocol + independent ATR-02 verification (Qwen: 759-pass full suite, zero regressions) |
| ATR-02 F4 Batch PDF | PROVEN (Z.ai + Qwen) | `b49a742` | 4/4 (both) | segment_batch + merge_batches + `ahw/segment.py` reconstruction (S001-v7 lineage, documented) + RTL GT prefill |
| ATR-03 F1 AraBERT Tokenizer | PROVEN (Z.ai) / dry_run PROVEN (Qwen) | `acf86b3` | 4/4 dry_run (both) | **real-load proven (Z.ai, 5.12.1)**: resize 50265→64000, reinit embed_tokens/lm_head/embed_positions, one-step forward logits [1,1,64000] in 0.8s CPU. **Qwen real-load BLOCKED** by 1GB sandbox RAM (OOM) — dry_run only |
| ATR-04 F3 Training UI | PROVEN (Qwen + Z.ai) | `21b0ba5` | 15/15 (both) | headless core `ahw/train_trocr.py` + Flask/SocketIO server + RTL dashboard (socket.io served locally, no CDN) + `correction_server.py` |
| ATR-04b Z.ai reconciliation | PROVEN (Z.ai) | `cc9fea8` | 35/35 | transformers 5.x compat for dry_run (PreTrainedTokenizerFast); `scripts/atr_probe_models.py` committed (closes Qwen audit note); dual-evidence pin note |
| Seam unification (crop-path) | PROVEN (Z.ai) | `bc6f740` | 38/38 | single crop-path contract (bare `crop_path` + `batch` column; consumers batch-aware per ATR-06). Z.ai's producer-side prefix **reverted** after Qwen's ATR-06 integration test caught the conflict — one unified contract |
| ATR-04c Cross-version dry_run fix | PROVEN (Qwen) | `50c0d71` | 38/38 (4.57.6) | Z.ai's 5.x dry_run tokenizer produced a single token w/o [CLS]/[SEP] → **loss=0 on transformers 4.57.6**. Added `TemplateProcessing("[CLS] $A [SEP]")` — faithful to real AraBERT, version-neutral (4.x AND 5.x). **No dependency upgrade** (rule 1.3); `<5.0.0` pin removed (dual-evidence) |
| ATR-05 F2 Docker | **PARTIALLY PROVEN** (Qwen + Z.ai) | `70e5982` | 12/12 STRUCTURE_ONLY | no docker binary in either env (spec fallback honored); documented deviations: `libgl1` (bookworm), ATR-suffixed filenames protect platform files |
| ATR-06 Integration Smoke | PROVEN (Qwen + Z.ai) | `11967da` | 3/3 e2e (Qwen) + 1/1 (Z.ai) | synthetic 3-page PDF → 3 batches/60 words/sha256 → merge → corrections.xlsx → run_training (dry_run tiny model, real crops). Qwen loss 2.8465→2.6945; Z.ai (5.12.1) loss 4.396/CER 0.686 |
| ATR-07 Final Report | PROVEN (both — unified here) | `8f2235f`+`5b352c5`+`50c0d71` | n/a | this merged document |

## FILES_CREATED

**Z.ai (Omni Audit Bot):** `PROGRESS.md`, `ahw/__init__.py`, `ahw/segment.py` (reconstructed),
`segment_batch.py`, `merge_batches.py`, `ahw/arabic_trocr.py`, `scripts/atr_probe_models.py`,
`tests/test_atr_batch.py`, `tests/test_atr_arabic_tokenizer.py`.

**Qwen (ATR Autonomous Agent):** `ahw/train_trocr.py`, `train_server.py`, `correction_server.py`,
`templates/train_dashboard.html`, `Dockerfile.atr`, `Dockerfile.atr.dockerignore`,
`docker-compose.atr.yml`, `requirements-atr.txt`, `scripts/atr_smoke.py`,
`tests/test_atr_training_ui.py`, `tests/test_atr_docker.py`, `tests/test_atr_integration_smoke.py`,
`docs/atr/ATR-01-PREFLIGHT-AUDIT.md`, `docs/atr/ATR-01b-RECONCILIATION.md`,
`docs/atr/reference-draft-from-session-logs.txt`, `docs/atr/ATR-07-FINAL-REPORT.md`.

## FILES_MODIFIED

- Both: `PROGRESS.md` (per-phase memory), `ahw/arabic_trocr.py` (Z.ai 5.x rebuild + Qwen ATR-04c post-processor), `requirements-atr.txt` (dual-evidence pin), `merge_batches.py` (net-zero after contract unification).
- **No existing platform file touched** (engines / contract / router / OCRResult / root Docker artifacts) — verified empty diff vs main by both sessions.

Total vs main: **24 files, ~+4150 lines, all additive.**

## DEPENDENCIES_ADDED (registry: name · version · license · reason)

Isolated in `requirements-atr.txt` + dev venvs. **`requirements.txt`/`pyproject.toml` UNCHANGED** (rule 1.6). No `pip install --upgrade` of any existing dependency (rule 1.3) — the ATR-04c fix is code-side, not version-side.

| Name | Version | License | Reason |
|---|---|---|---|
| torch | 2.14.0+cpu (CPU index) | BSD-3-Clause | TrOCR model + Trainer (F1/F3) |
| transformers | **4.57.6 (Qwen) / 5.12.1 (Z.ai)** — `>=4.46.0`, no cap | Apache-2.0 | VisionEncoderDecoder/TrOCRProcessor/Trainer. **Dual-evidence:** both proven 38/38 after ATR-04c. **4.48.3 AVOID** (Trainer `num_items_in_batch` rejected by ViTModel.forward). Repo pyproject allows `>=4.40.0` uncapped |
| accelerate | >=0.30.0 | Apache-2.0 | HF Trainer requirement |
| flask | >=3.0.0 | BSD-3-Clause | ATR-F3 servers |
| flask-socketio | 5.6.1 | MIT | realtime training events |
| simple-websocket | >=1.0.0 | MIT | websocket transport (threading mode) |
| PyMuPDF | 1.28.2 | **AGPL-3.0** (or commercial) | PDF→image render (F4). Already in `requirements/ml.txt` — not new to platform |
| opencv-python-headless | 4.x | Apache-2.0 | image ops/segmentation. Already in ml.txt |
| Pillow / numpy / scipy | latest compat | HPND / BSD-3 / BSD-3 | crop handling, arrays, image ops |
| pandas / openpyxl | 2.x / 3.x | BSD-3 / MIT | metadata/corrections. Already present |
| jiwer | 4.0.0 | Apache-2.0 | local CER (replaces external `evaluate` — no network). Already in ml.txt |
| arabic-reshaper / python-bidi | latest | MIT | Arabic shaping + RTL |
| pyyaml | 6.x | MIT | docker-compose YAML validation test |
| protobuf / sentencepiece | latest | BSD-3 / Apache-2.0 | tokenizer loading robustness (Z.ai env) |
| pytest / pytest-asyncio / pytest-timeout | 9.1.1 / 1.4.0 / 2.4.0 | MIT | dev/testing |

## MODELS_DOWNLOADED

| Model | Size | License | Status |
|---|---|---|---|
| microsoft/trocr-base-handwritten | 2.67 GB (2,668,254,555 B) | MIT | **Z.ai: DOWNLOADED + real-load proven** (logits [1,1,64000], 0.8s CPU). **Qwen: partial ~363MB then OOM** (1GB RAM cap) — cleaned up; dry_run only |
| aubmindlab/bert-base-arabertv02 | tokenizer only (~few MB) | Apache-2.0 | 64k vocab; LM head re-initialized (weights not needed) |

- **Z.ai total ≈ 2.7 GB ≤ 4 GB cap** (within budget).
- **Qwen total = 0 GB complete** (blocked by sandbox RAM, not budget/network/disk — 6GB disk free).
- dry_run fallback (implemented + tested OFFLINE via `HF_HUB_OFFLINE=1`) covered all Qwen verification.

## SMOKE TEST RESULT (end-to-end, real numbers)

Synthetic 3-page PDF (dummy Latin words `alpha..epsilon`, **zero PHI**) → `segment_pdf`
(pages-per-batch=1 → **3 batches, 60 words**, per-batch crops/preview/metadata.csv/.xlsx/manifest.json,
central `batch_state.json`, final manifest with **pdf sha256=12ef302be1a1…**) → `merge_all`
(metadata_all.csv/.xlsx, **batch column** = [batch_001,002,003]) → fake corrections.xlsx (60 rows) →
`run_training` (dry_run tiny model, real crops resolved batch-aware):

- **Qwen (4.57.6):** train=40 val=20, **loss 2.8465 → 2.6945** (eval_loss 2.6187), 1 epoch ~0.7s, pipeline 6.4–6.8s. **0 downloads / 0 network / 0 PHI.** Loss DECREASING = real gradient flow through TrOCR+AraBERT (dry_run) on real batch crops.
- **Z.ai (5.12.1):** Trainer 5 steps, loss 4.396, CER 0.686, 6.2s. Real-load (2.67GB): one decoder step logits [1,1,64000] in 0.8s CPU.

**Integration seam caught & fixed (why ATR-06 exists):** `segment_batch` writes `crop_path`
relative to each `batch_NNN/` + separate `batch` column, while consumers resolved from the
sample dir → every crop "missing". Fixed batch-aware in `train_trocr` + `correction_server`
(Qwen ATR-06), then contract unified repo-wide (Z.ai bc6f740). The integration test failed
first, passed after — proof ATR-06 did its job.

## EVIDENCE LABELS

- **PROVEN:** ATR-01, ATR-01b, ATR-02, ATR-03 (dry_run both; real-load Z.ai), ATR-04, ATR-04b, ATR-04c, ATR-06, seam unification, ATR-07.
- **PARTIALLY_PROVEN:** ATR-05 / F2 Docker (files + 12 static tests only — no docker runtime in either env). ATR-03 real-weight **in Qwen env** (RAM-blocked; proven in Z.ai env).
- **UNPROVEN:** full-mode multi-epoch training on real owner data with real weights + CER on a corrected OWNER_REVIEWED corpus (awaits owner data + GPU/RAM env; the pipeline for it is exactly ATR-02→F3, proven end-to-end on synthetic).
- **BLOCKED:** Qwen independent real-load (F1) — hard 1GB sandbox RAM cap → OOM during model materialization (not a code defect; dry_run works).
- **NOT EXECUTED:** docker image build; GPU training; PR creation (owner-authorized action).

## PERSISTENCE = OK

Every commit pushed + `git ls-remote`-verified from both sessions. Token used via runtime env-var
only — never printed, never written to `.git/config` (verified `grep -c ghp_ .git/config` = 0).
Handoff bundles per commit in `download/OMNI-EXECUTION/handovers/<sha>/`.

> ⚠️ **OWNER ACTION REQUIRED:** the push token is exposed in the uploaded session logs.
> **Revoke/rotate it immediately** at <https://github.com/settings/tokens> (as the repo's own
> `worklog.md` also mandates for previously-exposed PATs).

## HOW TO RUN

```bash
# 0) dev env (venv — pip-without-venv forbidden)
python -m venv .venv-atr && . .venv-atr/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-atr.txt

# 1) batch PDF segmentation (ATR-F4)
python segment_batch.py --pdf SCAN.pdf --sample S001 --pages-per-batch 5 --dpi 300 --out output/S001
# 2) merge batches (ATR-F4)
python merge_batches.py --out output/S001
# 3) correction UI (HITL) -> http://127.0.0.1:5000  (save corrections.xlsx)
python correction_server.py --sample S001 --data-root output --port 5000
# 4) training UI (ATR-F3) -> http://127.0.0.1:5001  (mode=smoke needs no weights)
python train_server.py --host 127.0.0.1 --port 5001
# 5) integration smoke proof (ATR-06 — no weights/network/PHI)
python scripts/atr_smoke.py
# Docker (ATR-F2): docker compose -f docker-compose.atr.yml up --build
```

## GOVERNANCE NOTES & DOCUMENTED DEVIATIONS

1. **Env differs from prompt:** Qwen ran at `/home/user/omni-medical-suite` (not `/home/z/…`), Python 3.11.2 (not 3.12), venv `/home/user/.venv`. (`ATR-01-PREFLIGHT-AUDIT.md` §1)
2. **Dual-session convergence:** Z.ai did ATR-01/02/03, went dormant ~30min; Qwen adopted (no force-push, no rewrite — `switch --detach`+`branch -f` instead of forbidden `reset --hard`) and built ATR-04→07; Z.ai then resumed (ATR-04b/seam/ATR-07) and cross-verified Qwen's ATR-04/05/06 on 5.12.1; Qwen re-based additively and added ATR-04c. Both converged on 38/38. (`ATR-01b-RECONCILIATION.md`)
3. **ATR-04c cross-version fix:** dry_run tokenizer now wraps `[CLS]…[SEP]` (faithful to real AraBERT) → works on transformers 4.x AND 5.x. No dependency upgraded (rule 1.3); resolved via code, not version bump.
4. **`libgl1` not `libgl1-mesa-glx`:** the spec'd name is gone in Debian bookworm (python:3.10-slim base); documented in `Dockerfile.atr`.
5. **ATR-suffixed Docker files (`.atr`):** root `Dockerfile`/`docker-compose.yml`/`.dockerignore` belong to the existing platform and are NOT replaced (rule: don't break existing). Sidecar `Dockerfile.atr.dockerignore` (BuildKit) keeps root `.dockerignore` untouched.
6. **jiwer instead of `evaluate`:** local CER, no external metric download (rule: no external network).
7. **Uploaded PDF (18 pages, suspected PHI):** NOT processed, NOT copied into repo, NOT sent anywhere. All tests use generated synthetic data.
8. **`transformers>=5.10,<5.13` claim:** Z.ai's note cited a repo worklog TASK-02D bound; the **committed** `pyproject.toml` shows only `transformers>=4.40.0` (uncapped) — so the pin is left uncapped with dual-version evidence, and CI should gate both 4.57.x and 5.1x.

## PROGRESS.md

Latest canonical content lives at repo root `PROGRESS.md` (updated every phase, pushed after
every commit — includes the dual-session log and adopted commit SHAs).
