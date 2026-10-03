# Workflow Audit Report

**Generated:** 2025-07-11
**Scope:** All `.yml`/`.yaml` files under `packages/` and `apps/` (excluding root `.github/workflows/`)
**Auditor:** Automated scan + manual classification

---

## Summary

| Category | Count |
|---|---|
| **Total `.yml`/`.yaml` files found** | 213 |
| **GitHub Actions workflow files** (in `*/.github/workflows/`) | 52 |
| **Workflow files — REMNANTS (should be deleted)** | 46 |
| **Workflow files — STILL VALID (paths exist)** | 6 |
| **Non-workflow YAML config files** | 161 |

> **Note:** GitHub Actions only runs workflows from the root `.github/workflows/` directory. All 52 scattered workflow files inside `packages/*/` and `apps/*/` are **dormant/dead** — GitHub will never execute them regardless of whether their paths are valid. Even the 6 "still valid" ones serve no purpose in the monorepo.

---

## Root `.github/workflows/` — Canonical Workflows

These are the **only** workflows GitHub will actually run. All 13 files exist and are the correct monorepo-level workflows:

| File | Purpose |
|---|---|
| `cd.yml` | Continuous deployment |
| `ci.yml` | Main CI pipeline |
| `credential-scan.yml` | Credential scanning |
| `deploy-to-hf.yml` | Deploy to HuggingFace Spaces |
| `docker-scanner-fixer.yml` | Scanner-fixer Docker build |
| `docker.yml` | Docker image builds |
| `keep-spaces-awake.yml` | Keep HF Spaces warm |
| `lint-test.yml` | Linting and testing |
| `nightly.yml` | Nightly builds/jobs |
| `pipeline-integration.yml` | Pipeline integration tests |
| `release.yml` | Release automation |
| `scanner-fixer-docker-full.yml` | Full scanner-fixer Docker pipeline |
| `security-scan.yml` | Security scanning |

**Status: All present and correct.** These supersede all scattered workflows.

---

## Table 1: REMNANT Workflow Files (46 files)

These are leftover workflows from pre-merge standalone repos (subtree-merged into the monorepo). GitHub ignores them entirely. Most also have **broken path references** since the repo structure changed during the merge.

### 1.1 — `packages/file_processor/.github/workflows/` (4 remnants)

Original repo: **OmniFile_Processor** (standalone before subtree merge)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Full CI/CD: unit tests, Docker builds, security scan, staging/production deploy via Helm | References `api_server_v2/` (not found), `deployment/helm/` (not found), uses K8s/EKS deploy for standalone repo |
| `docs.yml` | Deploy MkDocs documentation to GitHub Pages | Standalone docs site; monorepo uses root docs |
| `release.yml` | Create GitHub releases with changelog | References `requirements-core.txt`, `requirements-full.txt` which don't exist in this package (they're in `omnifile/` and `handwriting/`); cloned from OmniFile_Processor |
| `train.yml` | Trigger training pipeline (TroCR-LoRA, Qwen-VL, Unsloth) | References `training/scripts/` (exists) and `tools/benchmark_ocr.py` (exists) but `pip install -e ".[training]"` may not work as expected from monorepo root; designed for standalone repo dispatch |

### 1.2 — `packages/handwriting/.github/workflows/` (2 remnants)

Original repo: **OmniFile_Processor** (handwriting variant, same codebase)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Tests + lint with coverage on `modules/` | References `requirements-core.txt` (exists), `requirements-full.txt` (exists), `modules/` (exists) — paths valid but workflow is dormant; duplicate of `packages/omnifile/.github/workflows/ci.yml` |
| `release.yml` | GitHub releases for handwriting package | Identical to omnifile's release.yml; references OmniFile Processor branding (wrong for `handwriting/` package) |

### 1.3 — `packages/omnifile/.github/workflows/` (2 remnants)

Original repo: **OmniFile_Processor** (refactored into `omnifile/` package)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Tests + lint with coverage on `modules/` | Paths valid (`modules/`, `tests/`, `requirements-*.txt` all exist), but dormant — GitHub won't run it |
| `release.yml` | GitHub releases | Paths OK but dormant; release body says "OmniFile AI Processor" with standalone install instructions |

### 1.4 — `packages/doc-processor/.github/workflows/` (3 remnants)

Original repo: **medical-doc-processor** (standalone web app)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Test Python core (`packages/core/`) + web app (Bun) | References `packages/core/` which is a legacy dir structure from standalone repo; dormant |
| `release.yml` | GitHub release with Bun build | References standalone repo clone URL `DrAbdulmalek/medical-doc-processor.git`; dormant |
| `tests.yml` | Run Python tests with PyQt5 desktop support | References `requirements.txt` and `test_core.py` at package root (exist); but runs desktop GUI tests irrelevant to monorepo CI; dormant |

### 1.5 — `packages/doc_processor/.github/workflows/` (3 remnants)

Original repo: **medical-doc-processor** (duplicate with hyphenated vs underscored name — **exact same workflows** as `doc-processor/`)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Identical to `doc-processor` ci.yml | Same broken `packages/core/` path reference; this is a duplicate package directory |
| `release.yml` | Identical to `doc-processor` release.yml | Same standalone repo URL reference |
| `tests.yml` | Identical to `doc-processor` tests.yml | Same issues |

### 1.6 — `packages/benchmark_core/.github/workflows/` (7 remnants)

Original repo: **medical-ocr-benchmarks** (standalone benchmarking repo)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `benchmark.yml` | Run OCR benchmark suite with mock mode | References `src/`, `data/`, `config/` — all exist; but path filter watches `src/**` and `data/**` from package root (not monorepo root); dormant |
| `ci.yml` | Lint + unit tests | Multi-job CI with Docker compose, API tests — designed for standalone benchmark repo; dormant |
| `ground-truth-integration.yml` | Ground truth data sync with `working-directory: ground-truth` | `ground-truth/` directory does NOT exist in this package; broken |
| `nightly-benchmark.yml` | Nightly scheduled benchmarks | Dispatches to itself; dormant |
| `nightly-benchmarks.yml` | Another nightly benchmark runner | References `python -m benchmarks.runner` from package root; paths partially valid; dormant |
| `pr-benchmark.yml` | Benchmark on PRs | Watches `src/**` paths; dormant |
| `scanner-fixer-benchmark.yml` | Benchmark scanner-fixer module | References `scanner-fixer/` directory which does NOT exist; broken |

### 1.7 — `packages/gt_core/.github/workflows/` (2 remnants)

Original repo: **medical-ocr-ground-truth** (standalone ground truth repo)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Lint + test | `requirements.txt` NOT found; `tests/` NOT found; broken |
| `dispatch-benchmarks.yml` | Dispatch events to external repos (benchmarks, training-hub, omni-medical-suite) | Dispatches to `DrAbdulmalek/medical-ocr-benchmarks` and `DrAbdulmalek/medical-ocr-training-hub` — these are now packages in the same repo; dispatches are meaningless |

### 1.8 — `packages/bilingual/.github/workflows/` (1 remnant)

Original repo: **medical-ocr-bilingual** (standalone bilingual processing)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Lint + test | `requirements.txt` exists; but no `tests/` directory found; dormant |

### 1.9 — `packages/ocr_postprocess/.github/workflows/` (1 remnant)

Original repo: **medical-ocr-postprocess** (standalone postprocessing)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Lint + test | `requirements.txt` NOT found; `tests/test_core.py` exists; partially broken |

### 1.10 — `packages/ai-fuel/.github/workflows/` (1 remnant)

Original repo: **ai-fuel** (standalone AI fueling library)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Lint + test | `requirements.txt`, `setup.py`, `pyproject.toml` all exist; paths valid but dormant |

### 1.11 — `packages/omniparse/.github/workflows/` (2 remnants)

Original repo: **OmniParse** (third-party, subtree-merged as reference)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `docker-image.yml` | Build & push Docker image to Docker Hub | Pushes to `cognitivelab/omniparse` — external org; `Dockerfile` exists but this is a third-party reference repo |
| `python-publish.yml` | Publish Python SDK to PyPI | References `python-sdk/` (exists); but pushes to PyPI under OmniParse's namespace — not ours to publish |

### 1.12 — `packages/scanner_fixer/.github/workflows/` (1 remnant)

Original repo: **scanner-fixer** (standalone scanner fixer)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Lint + test + build wheel | `src/` and `tests/` exist; paths valid but dormant |

### 1.13 — `packages/training_hub/.github/workflows/` (2 remnants)

Original repo: **medical-ocr-training-hub** (standalone training data hub)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `release-pipeline.yml` | Readiness check + release validation | `requirements.txt` NOT found (falls back to `pip install requests pyyaml`); `training_data/` and `src/` exist; dispatches to external repos that are now in-monorepo; dormant |
| `sync-and-build.yml` | Sync HF Space ↔ GitHub, build training datasets | `scripts/` and `training_data/` exist; dispatches to external repos; dormant |

### 1.14 — `packages/file_processor/_dev_references/*/` (6 remnants)

These are workflows from **external reference repos** stored in `_dev_references/` for study purposes. They were never part of any merge — they're reference material.

| File | Original Repo | What It Did | Why It's Invalid |
|---|---|---|---|
| `_dev_references/9router/.github/workflows/docker-publish.yml` | 9router | Docker image build/push to GHCR | Reference only; not part of this project |
| `_dev_references/OSINT-Recon-Agent/.github/workflows/lint.yml` | OSINT-Recon-Agent | Markdown/YAML/Python/Shell linting | Reference only; references `skills/` dirs that don't exist at this path |
| `_dev_references/agent-skills/.github/workflows/test-plugin-install.yml` | agent-skills | Test Claude Code plugin installation | Reference only; references `claude` CLI not available in CI |
| `_dev_references/agentmemory/.github/workflows/ci.yml` | agentmemory | Node.js CI (build + test) | Reference only; npm project not ours |
| `_dev_references/agentmemory/.github/workflows/publish.yml` | agentmemory | Publish to npm registry | Reference only; pushes to `@agentmemory/*` namespace |
| `_dev_references/financial-services/.github/workflows/secret-scan.yml` | financial-services | Gitleaks secret scanning | Reference only; scans for Anthropic internal refs |

### 1.15 — `packages/file_processor/omni-medical-suite/.github/workflows/` (1 remnant)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `keep-space-awake.yml` | Pings two HF Spaces every 12 hours | Nested copy of root `keep-spaces-awake.yml`; GitHub will never find it here (not in root `.github/workflows/`) |

### 1.16 — `apps/handwriting-demo/.github/workflows/` (6 remnants)

Original repo: **handwriting-demo** (standalone demo app)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci-cd-omniparse.yml` | Full CI/CD with PostgreSQL, Redis, MinIO services; Docker builds; deploy | References `backend/` (NOT found), `training/Dockerfile.training` (exists at `training/`), `docker/docker-compose.one-click.yml` (exists); `backend/` path broken |
| `ci-cd.yml` | Multi-env CI/CD with staging/production deploy | References `backend/` (NOT found), `frontend/` (exists); `backend/` path broken |
| `ci.yml` | Simple CI: test + Docker build | References `backend/requirements.txt` (NOT found), `backend/Dockerfile` (NOT found); broken |
| `cloud-build.yml` | Mobile build (Android APK/AAB) + Firebase distribution | References `mobile/` (NOT found), `mobile/android/` (NOT found); broken |
| `deploy.yml` | Simple Docker build/push | References `./backend/Dockerfile` (NOT found); broken |
| `mobile-build.yml` | Mobile build variant | References `mobile/` (NOT found), `mobile/android/` (NOT found); broken |

### 1.17 — `apps/handwriting-demo/variants/handwriting-ocr/.github/workflows/` (2 remnants)

Original repo: **OmniFile_Processor** handwriting-ocr variant (submodule/variant)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Tests + integration tests | References `requirements-core.txt`, `requirements-full.txt`, `tests/` — all exist; but this is a variant subdirectory, dormant |
| `release.yml` | GitHub release | Identical to file_processor/handwriting/omnifile release.yml; references OmniFile Processor branding; dormant |

### 1.18 — `apps/trainer-ui/.github/workflows/` (2 remnants)

Original repo: **trainer-ui** (standalone trainer)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Lint + test + build | `tests/` exists (1 file); paths mostly valid; dormant |
| `data-governance.yml` | Data governance checks | No specific path references; dormant |

### 1.19 — `apps/trainer-ui/hf-variant/.github/workflows/` (1 remnant)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `ci.yml` | Basic Python test CI | Generic CI with fallbacks; dormant |

### 1.20 — `apps/ocr-demo/.github/workflows/` (1 remnant)

Original repo: **medical-ocr-demo** (standalone HF Spaces demo)

| File | What It Did | Why It's Invalid |
|---|---|
| `deploy.yml` | Deploy to HuggingFace Spaces | Pushes entire repo to HF Space; designed for standalone repo where root IS the app. In monorepo, would push the entire monorepo. Branch filter uses `[main]` correctly but GitHub won't run it from this path |

### 1.21 — `apps/ocr-pipeline/.github/workflows/` (1 remnant)

| File | What It Did | Why It's Invalid |
|---|---|---|
| `deploy.yml` | Deploy to HF Spaces | Uses `HuggingFace/hf-spaces-deploy@v1`; dormant |

---

## Table 2: "Still Valid" Workflow Files (6 files)

These have path references that technically exist in the monorepo, but **GitHub will never execute them** because they're not in the root `.github/workflows/` directory. Listed for completeness.

| File | What It Does | Confirmed Valid Paths |
|---|---|---|
| `packages/omnifile/.github/workflows/ci.yml` | Test + lint `modules/`, `tests/` | `modules/` ✓, `tests/` ✓, `requirements-core.txt` ✓, `requirements-full.txt` ✓, `requirements-dev.txt` ✓ |
| `packages/omnifile/.github/workflows/release.yml` | GitHub releases | No relative path deps (uses `git log`) |
| `packages/handwriting/.github/workflows/ci.yml` | Test + lint `modules/`, `tests/` | `modules/` ✓, `tests/` ✓, `requirements-*.txt` ✓ |
| `packages/scanner_fixer/.github/workflows/ci.yml` | Test `src/`, build wheel | `src/` ✓, `tests/` ✓ |
| `packages/ai-fuel/.github/workflows/ci.yml` | Generic lint + test | `requirements.txt` ✓, `setup.py` ✓, `pyproject.toml` ✓ |
| `packages/file_processor/.github/workflows/train.yml` | Training pipeline with model evaluation | `training/configs/` ✓, `training/scripts/` ✓, `tools/` ✓, `data/` ✓ |

---

## Table 3: Non-Workflow YAML Files (161 files)

These are configuration files, not GitHub Actions workflows. They are not analyzed in depth.

| Category | Approximate Count | Examples |
|---|---|---|
| Docker Compose files | ~15 | `docker-compose.yml`, `docker-compose.full.yml`, `docker-compose.monitoring.yml` |
| Prometheus/Grafana configs | ~5 | `prometheus.yml`, `prometheus-rules.yml`, `alertmanager.yml`, `datasources.yml`, `dashboards.yml` |
| GitHub Issue templates | ~14 | `bug_report.yml`, `feature_request.yml`, `config.yml` (in ISSUE_TEMPLATE dirs) |
| Dependabot configs | ~9 | `dependabot.yml` files |
| Pre-commit configs | ~6 | `.pre-commit-config.yaml` |
| Kubernetes manifests | ~3 | `api-deployment.yaml`, `gpu-training-job.yaml`, `namespace.yaml` |
| Training/model configs | ~6 | `trocr_lora_arabic.yaml`, `paddleocr_custom.yaml`, `postprocessor.yaml`, `trocr_finetune.yaml` |
| Application configs | ~5 | `config.yaml`, `baselines.yaml`, `thresholds.yaml`, `codecov.yml` |
| Lock files | ~3 | `pnpm-lock.yaml` |
| Agent/skill YAML configs | ~35+ | `agent.yaml`, `plugin.yaml`, `skill.yaml` (in `_dev_references/`) |
| MkDocs config | ~1 | `mkdocs.yml` |
| Other (docker profiles, etc.) | ~59 | Various docker-compose profiles, provisioning configs, etc. |

---

## Recommendations

### Immediate Action (High Priority)

1. **Delete all 52 scattered workflow files** — They serve zero purpose. GitHub only runs workflows from the root `.github/workflows/`. Keeping them creates confusion about which CI actually runs.

2. **Delete `packages/doc_processor/` entirely** — It's a duplicate of `packages/doc-processor/` (same workflows, same structure).

3. **Delete `packages/file_processor/omni-medical-suite/`** — A nested copy of the monorepo itself inside a package. This is recursive nonsense.

### Medium Priority

4. **Audit `packages/file_processor/_dev_references/`** — This directory contains ~7 cloned external repos (agentmemory, financial-services, OSINT-Recon-Agent, etc.) with their own `.github/workflows/`. These are reference/study material and should either be:
   - Moved to a separate `docs/references/` location
   - Or deleted entirely (they're available at their original GitHub URLs)

5. **Delete all `*/.github/` directories under packages/apps** except for any ISSUE_TEMPLATE files you want to keep (though GitHub won't use those either from non-root locations for the monorepo).

### Low Priority

6. **Consider consolidating `packages/doc-processor/` and `packages/doc_processor/`** — Having both a hyphenated and underscored version is confusing.

7. **Review `packages/handwriting/` vs `packages/omnifile/` vs `packages/file_processor/`** — All three contain nearly identical code (`modules/` directories with the same structure). These may be three copies of the same OmniFile_Processor from different merge stages.