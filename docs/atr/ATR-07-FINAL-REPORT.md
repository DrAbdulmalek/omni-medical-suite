# ATR-07 — التقرير النهائي الشامل (Arabic TrOCR Advanced Features)

> Generated 2026-09-23 — dual-session execution (Z.ai + Qwen/ATR-Agent) under the
> ATR-01b reconciliation protocol (fetch-before-push, additive commits only,
> adopt-and-skip on duplicate phases, independent cross-verification).

## === ATR FINAL STATUS ===

- **BRANCH**: `feature/atr-trocr-advanced` (main `39640a6dbba7` untouched — verified empty diff vs main by both sessions)
- **HEAD**: `bc6f7403b16b6589318159dd23f1fb236151426c`
- **REMOTE-VERIFIED-SHA**: `bc6f7403b16b6589318159dd23f1fb236151426c` (`git ls-remote origin` == local HEAD, after every push)
- **ATR SUITE**: **38/38 passed** (4 batch + 4 tokenizer + 15 training UI + 12 docker + 1 integration smoke + 2 contract/conflict guards) — Z.ai env: Python 3.12.14 / torch 2.14.0+cpu / transformers 5.12.1
- **PERSISTENCE**: **OK** — token from `/home/z/my-project/.secrets/gh_token` (fingerprint sha256:5821a50287a8c836…, never printed) worked on every push; every commit remote-verified; handover bundles under `download/OMNI-EXECUTION/handovers/<sha>/` outside the repo.

## PER-PHASE TABLE

| Phase | Status | Commit | Tests (Z.ai env) | Notes |
|---|---|---|---|---|
| ATR-01 Pre-Flight + PROGRESS.md | PROVEN (Z.ai) | `11da6ac` | n/a | branch from origin/main 39640a6; dirty=59 mode-bits only → core.fileMode=false |
| ATR-01b Reconciliation | PROVEN (Qwen) | `558dda5` | n/a | dual-session protocol + independent ATR-02 verification (Qwen: 759-pass full suite, zero regressions) |
| ATR-02 F4 Batch PDF | PROVEN (Z.ai + Qwen) | `b49a742` | 4/4 | segment_batch + merge_batches + ahw/segment.py reconstruction (S001-v7 lineage, documented) + RTL GT prefill |
| ATR-03 F1 AraBERT Tokenizer | PROVEN (Z.ai) | `acf86b3` | 4/4 dry_run | real-load proven: resize 50265→64000, reinit embed_tokens/lm_head(tied)/embed_positions, one-step forward 0.8s CPU |
| ATR-04 F3 Training UI | PROVEN (Qwen + Z.ai) | `21b0ba5` | 15/15 | headless core ahw/train_trocr.py + Flask/SocketIO server + RTL dashboard (socket.io served locally, no CDN) + correction_server |
| ATR-05 F2 Docker | **PARTIALLY PROVEN** (Qwen + Z.ai) | `70e5982` | 12/12 STRUCTURE_ONLY | no docker binary in either env (spec fallback honored); documented deviations: libgl1 (bookworm), ATR-suffixed filenames to protect platform files |
| ATR-06 Integration Smoke | PROVEN (Qwen + Z.ai) | `11967da` | 1/1 e2e | synthetic 3-page PDF → 3 batches/60 words/sha256 → merge → corrections.xlsx → run_training (dry_run tiny model, real crops) |
| ATR-04b Z.ai reconciliation | PROVEN (Z.ai) | `cc9fea8` | 35/35 | transformers 5.x compat for dry_run (PreTrainedTokenizerFast); probe script committed (closes audit note); dual-evidence pin note in requirements-atr.txt |
| Seam unification | PROVEN (Z.ai) | `bc6f740` | 38/38 | single crop-path contract (bare crop_path + batch column; consumers batch-aware per ATR-06) — Z.ai's producer-side prefix reverted after integration test caught the conflict |
| ATR-07 Final Report | PROVEN (Z.ai) | (this commit) | n/a | this document |

## FILES_CREATED (Z.ai)

`PROGRESS.md`, `ahw/__init__.py`, `ahw/segment.py` (reconstructed), `segment_batch.py`,
`merge_batches.py`, `tests/test_atr_batch.py`, `ahw/arabic_trocr.py`,
`tests/test_atr_arabic_tokenizer.py`, `scripts/atr_probe_models.py`,
`docs/atr/ATR-07-FINAL-REPORT.md`.

## FILES_CREATED (Qwen — adopted)

`ahw/train_trocr.py`, `train_server.py`, `correction_server.py`,
`templates/train_dashboard.html`, `tests/test_atr_training_ui.py`,
`Dockerfile.atr`, `Dockerfile.atr.dockerignore`, `docker-compose.atr.yml`,
`requirements-atr.txt`, `tests/test_atr_docker.py`, `scripts/atr_smoke.py`,
`tests/test_atr_integration_smoke.py`, `docs/atr/ATR-01b-RECONCILIATION.md`,
`docs/atr/ATR-01-PREFLIGHT-AUDIT.md`.

## FILES_MODIFIED (Z.ai)

`PROGRESS.md` (per phase), `requirements-atr.txt` (dual-evidence pin comment),
`merge_batches.py` (net zero vs ATR-06 after contract unification).
No existing platform file touched (engines/contract/router/OCRResult untouched — verified by both sessions).

## DEPENDENCIES_ADDED (Z.ai venv — registry: name, version, license, reason)

| Name | Version | License | Reason |
|---|---|---|---|
| torch | 2.14.0+cpu (pytorch CPU index) | BSD-3 | TrOCR model + Trainer (F1/F3) |
| transformers | 4.48.3 → **5.12.1** | Apache-2.0 | VisionEncoderDecoder/TrOCRProcessor/Trainer; 4.48.3 proven broken for Trainer+TrOCR (`num_items_in_batch` rejected by ViTModel.forward), 5.12.1 proven working — matches repo's documented 5.10–5.13 bound |
| flask | 3.1.3 | BSD-3 | ATR-F3/F2 servers |
| flask-socketio | 5.6.1 | MIT | realtime training events |
| accelerate | 1.15.0 | Apache-2.0 | Trainer requirement |
| protobuf | (latest) | BSD-3 | transformers tokenizer loading |
| sentencepiece | (latest) | Apache-2.0 | AraBERT tokenizer robustness |
| pyyaml | 6.0.3 | MIT | docker-compose validation test |
| jiwer | (latest) | MIT | CER in Qwen's training core (their declared dep, needed to verify their code) |

(Qwen's `requirements-atr.txt` declares the Docker-facing superset; note inside
documents the 4.48-broken/5.12-working evidence conflict for CI arbitration.)

## MODELS_DOWNLOADED

| Model | Size | License | Used for |
|---|---|---|---|
| microsoft/trocr-base-handwritten | 2.67 GB (2,668,254,555 B) | MIT | encoder weights + ViTImageProcessor (full_load_real proven) |
| aubmindlab/bert-base-arabertv02 | tokenizer only (~few MB) | Apache-2.0 | 64k vocab; LM head re-initialized (weights not needed) |

Total ≈ 2.7 GB ≤ 4 GB cap. If downloads fail → dry_run fallback (implemented + tested offline).

## SMOKE TEST RESULT (end-to-end)

Synthetic 3-page PDF (dummy Latin words, zero PHI) → `segment_pdf`
(pages-per-batch=1 → 3 batches, 60 words, per-batch crops/preview/metadata.csv/
metadata.xlsx/manifest.json, central batch_state.json, final manifest with
pdf sha256) → `merge_all` (metadata_all.csv/.xlsx, batch column) → fake
corrections.xlsx → `run_training` (dry_run tiny model, 1 epoch, 10 synthetic
samples; real crops resolved) → CER measured. Standalone Z.ai run on
transformers 5.12.1: Trainer 5 steps, loss 4.396, CER 0.686, 6.2 s wall.
Real-load (2.67 GB weights): one decoder step logits [1,1,64000] in 0.8 s CPU.

## PROVEN / PARTIALLY_PROVEN / UNPROVEN / NOT EXECUTED

- PROVEN: ATR-01, ATR-01b, ATR-02, ATR-03, ATR-04, ATR-04b, ATR-06, seam unification, ATR-07.
- PARTIALLY_PROVEN: ATR-05 (files + static tests only — no docker runtime in either env).
- UNPROVEN: full-mode training on real owner data (awaits corrected OWNER_REVIEWED corpus — the pipeline for it is exactly ATR-02→F3).
- NOT EXECUTED: docker image build, GPU training, PR creation (owner-authorized action).

## HOW TO RUN

```bash
python -m venv .venv-atr --system-site-packages && . .venv-atr/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-atr.txt
python segment_batch.py --pdf <scan.pdf> --sample S002 --pages-per-batch 5 --dpi 300 --out output/S002 --gt-dir <gt_dir> && python merge_batches.py --out output/S002
python correction_server.py --csv output/S002/metadata_all.csv --port 5000 & python train_server.py --port 5001   # POST /api/start {"mode":"smoke"} ثم {"mode":"full","corrections":"output/S002/corrections.xlsx"}
```

## PROGRESS.md

Latest canonical content lives at repo root `PROGRESS.md` (updated by every phase,
pushed after every commit — including the parallel-session log and the adopted
commit SHAs above).
