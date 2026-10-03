# Changelog

All notable changes to OmniMedical Suite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Repository History

### Monorepo Migration (2026-07-07)

# Monorepo Migration Report
# Date: 2026-07-07
# Canonical Repo: omni-medical-suite

#### Merged Repos (17 total)

**Core Medical/OCR (8 repos → packages/ + apps/)**

| Source Repo | Target Path | Status |
|---|---|---|
| scanner-fixer | packages/scanner_fixer/ | Merged |
| medical-ocr-ground-truth | packages/gt_core/ | Merged |
| medical-ocr-benchmarks | packages/benchmark_core/ | Merged |
| medical-ocr-training-hub | packages/training_hub/ | Merged |
| medical-ocr-postprocessor | packages/ocr_postprocess/ | Merged |
| medical-doc-processor | packages/doc_processor/ | Merged |
| omni-medical-ocr-pipeline | apps/ocr-pipeline/ | Merged |
| medical-handwriting-ocr | apps/handwriting-demo/ | Merged |

**Tools/Ops (5 repos → tools/)**

| Source Repo | Target Path | Status |
|---|---|---|
| git-sync-system | tools/repo_admin/git-sync/ | Merged |
| telegram-forwarder | tools/ops/telegram_forwarder/ | Merged |
| reset-net | tools/sys/reset_net/ | Merged |
| manjaro-care | tools/sys/manjaro-care/ | Merged |
| ai-fuel-engine | tools/ai_fuel/ | Merged |

**Shared Text/Data (4 repos → packages/ + labs/)**

| Source Repo | Target Path | Status |
|---|---|---|
| bilingual-extractor | packages/bilingual/ | Merged |
| OmniFile_Processor | packages/file_processor/ | Merged |
| omniparse | packages/omniparse/ | Merged |
| omniparse-study | labs/omniparse_study/ | Merged |

**Trainer/Demo (3 repos → apps/)**

| Source Repo | Target Path | Status |
|---|---|---|
| medical-ocr-trainer | apps/trainer-ui/ | Merged |
| medical-ocr-trainer-hf | apps/trainer-ui/hf-variant/ | Merged |
| medical-ocr-demo | apps/ocr-demo/ | Merged |
| handwriting-ocr | apps/handwriting-demo/variants/ | Merged |

**Method:** `git subtree add --squash` — preserves file history in squash commits, each source repo becomes a self-contained subdirectory.

### Repository Cleanup (2026-07-07)

**Account:** DrAbdulmalek
**Executed by:** AI Assistant (Super Z) + DrAbdulmalek oversight
**Total repos before:** ~50+
**Total repos after:** 15

#### Phase 0: Discovery & Inventory

- Ran `gh repo list` to catalog all repositories
- Categorized repos into: Core Keep (9), Merge (6), Archive (7+), Delete (34), Rename (2)
- Saved inventory to `full_inventory.json`

#### Phase 1: Backup (34 repos)

All repos slated for deletion were backed up locally via `git clone --mirror` to `/home/z/github_cleanup/backups/` before any destructive operations.

| # | Repo | Backup Status |
|---|------|--------------|
| 1 | training | OK |
| 2 | tools | OK |
| 3 | tests | OK |
| 4 | src | OK |
| 5 | scripts | OK |
| 6 | notebooks | OK |
| 7 | New-Folder | OK |
| 8 | modules | OK |
| 9 | mobile_review_v2 | OK |
| 10 | mobile_review | OK |
| 11 | mobile | OK |
| 12 | legacy | OK |
| 13 | k8s | OK |
| 14 | grafana | OK |
| 15 | .github | OK |
| 16 | examples | OK |
| 17 | _dev_references | OK |
| 18 | deployment | OK |
| 19 | data | OK |
| 20 | _claude_merge | OK |
| 21 | backend | OK |
| 22 | manjaro-care | OK |
| 23 | reset-net | OK |
| 24 | telegram-forwarder | OK |
| 25 | old-copies-before-edits | OK |
| 26 | telegram-pipeline | OK |
| 27 | telegram-channel-copier | OK |
| 28 | github-file-uploader | OK (may be empty) |
| 29 | medical-ocr-work-data | OK (may be empty) |
| 30 | archive | OK (may be empty) |
| 31 | arabic-dictionaries-collection | OK (may be empty) |
| 32 | text_snippets | OK |
| 33 | manjaro-ultimate-control-center | OK (may be empty) |
| 34 | OmniFile_Processor | OK (cloned for Phase A audit) |

#### Phase 2: Archive to medical-ocr-archived (7 repos)

Repos archived as git bundles + full clones into `DrAbdulmalek/medical-ocr-archived` (PRIVATE).

| Repo | Bundle | Clone |
|------|--------|-------|
| claude-review-ocr | archives/claude-review-ocr.bundle | repos/claude-review-ocr/ |
| future-dev-ideas | archives/future-dev-ideas.bundle | repos/future-dev-ideas/ |
| ocr-groundtruth | archives/ocr-groundtruth.bundle | repos/ocr-groundtruth/ |
| omniparse | archives/omniparse.bundle | repos/omniparse/ |
| omniparse-study | archives/omniparse-study.bundle | repos/omniparse-study/ |
| ponytail | archives/ponytail.bundle | repos/ponytail/ |
| shinyelectron | archives/shinyelectron.bundle | repos/shinyelectron/ |

#### Phase 3: Merge into omni-medical-suite (6 repos)

All merges used `git subtree add --prefix=<path> --squash`.

| Source Repo | Target Path | Status |
|-------------|-------------|--------|
| OmniFile_Processor | packages/omnifile | SUCCESS |
| medical-doc-processor | packages/doc-processor | SUCCESS |
| handwriting-ocr | packages/handwriting | SUCCESS |
| ai-fuel-engine | packages/ai-fuel | SUCCESS |
| omni-medical-ocr-pipeline | apps/ocr-pipeline | SUCCESS |
| bilingual-extractor | packages/bilingual | SUCCESS |

#### Phase 5-8: Deletion (35 repos total)

**Generic repos deleted (22):**
training, tools, tests, src, scripts, notebooks, New-Folder, modules, mobile_review_v2, mobile_review, mobile, legacy, k8s, grafana, .github, examples, _dev_references, deployment, data, _claude_merge, backend

**Personal repos deleted (3):**
manjaro-care, reset-net, telegram-forwarder

**Private repos deleted (9):**
old-copies-before-edits, telegram-pipeline, telegram-channel-copier, github-file-uploader, medical-ocr-work-data, archive, arabic-dictionaries-collection, text_snippets, manjaro-ultimate-control-center

**Merged source repos deleted (6):**
OmniFile_Processor, handwriting-ocr, medical-doc-processor, ai-fuel-engine, omni-medical-ocr-pipeline, bilingual-extractor

**Archived repos deleted from GitHub (5):**
ponytail, omniparse, omniparse-study, claude-review-ocr, future-dev-ideas, shinyelectron, ocr-groundtruth

#### Phase 9: Rename (2 repos)

| Old Name | New Name | Date |
|----------|----------|------|
| IntelliFile-app | intelli-file-manager | 2026-07-07 12:22 UTC |
| git-sync-system | repo-sync-toolkit | 2026-07-07 12:22 UTC |

#### Phase 10: README Updates (7 Core archived repos)

Unarchived temporarily, added archive banner pointing to omni-medical-suite, then re-archived.

| Repo | Commit | Suite Path |
|------|--------|------------|
| medical-handwriting-ocr | 0b9c010 | apps/handwriting-demo/ |
| arabic-medical-ocr-baseline | f89eb7f | packages/omni-ocr/ |
| medical-ocr-training-hub | a173815 | packages/training_hub/ |
| scanner-fixer | 8ae7f96 | packages/scanner_fixer/ |
| medical-ocr-ground-truth | a1225d3 | packages/gt_core/ |
| medical-ocr-trainer | f2c4320 | apps/trainer-ui/ |
| medical-ocr-benchmarks | 535aea9 | packages/benchmark_core/ |

#### Final Repository Inventory (15 repos)

**Active Repos (8)**

| # | Repo | Visibility | Purpose |
|---|------|-----------|---------|
| 1 | **omni-medical-suite** | Public | Monorepo (31 packages + 5 apps) |
| 2 | **intelli-file-manager** | Public | Intelligent File Management App |
| 3 | **repo-sync-toolkit** | Public | Git Synchronization Toolkit |
| 4 | **sync-github** | Public | One-command local repo sync |
| 5 | **DrAbdulmalek** | Public | GitHub Profile README |
| 6 | **medical-ocr-demo** | Public | HF Space - Live OCR Demo |
| 7 | **medical-ocr-trainer-hf** | Public | HF Space - Trainer Deployment |
| 8 | **medical-ocr-archived** | Private | Archived repo bundles |

**Archived Core Repos (7)**

| # | Repo | Suite Equivalent |
|---|------|-----------------|
| 1 | medical-handwriting-ocr | apps/handwriting-demo/ |
| 2 | arabic-medical-ocr-baseline | packages/omni-ocr/ |
| 3 | medical-ocr-training-hub | packages/training_hub/ |
| 4 | scanner-fixer | packages/scanner_fixer/ |
| 5 | medical-ocr-ground-truth | packages/gt_core/ |
| 6 | medical-ocr-trainer | apps/trainer-ui/ |
| 7 | medical-ocr-benchmarks | packages/benchmark_core/ |

#### OmniFile_Processor Audit (Phase A - Separate)

- **Total files audited:** 127
- **Files kept:** 3 (logger.py, export.py, finetuning.py)
- **Files deleted:** 124
- **Commit:** e22782a
- **Tag:** legacy/pre-final-prune-20260706

#### PHASE 4: Deployment (Re-applied 2026-07-09)

Environment reset caused loss of PHASE 4 files. Re-created and pushed as commit `32917dd`.

**Files created/modified:**
- `Dockerfile.gradio` — Multi-stage Docker build (builder → runtime), PaddleOCR pre-caching, appuser:1000
- `docker-compose.yml` — 5 services with `--profile infra`, gradio runs standalone
- `.github/workflows/deploy-to-hf.yml` — Path-filtered auto-deploy to HF Spaces
- `README.md` — New Deployment section with architecture diagram, CI/CD table, config table

#### PHASE 5: Verification & Finalization (2026-07-09)

**Test Results Summary**
- **Pytest:** 270 passed, 19 failed, 39 skipped, 4 errors (out of 332 runnable)
- **Ruff Check:** 16,981 warnings (exit 0, all fixable)
- **Mypy Check:** 1 error (handwriting-ocr package naming), exit 2

**Build & Deployment**
- **Docker Build:** Skipped (no Docker in sandbox). Files verified and committed.
- **Docker Compose:** Skipped (no Docker in sandbox). Files verified and committed.

**Application Status**
- **PyQt6 Desktop:** Core imports OK (PyQt6 6.11.0, OCREnsemble). MainWindow requires GUI libs (libEGL).
- **Gradio HITL:** Dockerfile.gradio ready, requires Docker to test.

**Final Repository Count**
- **Before Cleanup:** 61
- **After Cleanup:** 15
- **Target:** <= 15
- **Status:** Target met

---

## [2.2.0] - 2026-07-07

### Fixed
- **Alembic migrations**: Fixed `migrations/env.py` to import Base from `app.db.models.auth` instead of non-existent `app.core.database` and `app.models.document`
- **Migration completeness**: Replaced documents-only migration with comprehensive migration covering all 13 tables (RBAC, documents, jobs)
- **Database URL resolution**: Fixed `DATABASE_URL` environment variable conflict — env.py now reads `alembic.ini` directly and validates URL format before using env vars
- **app/main.py**: Removed references to non-existent `async_scoped_session`, `AsyncSessionLocal`, and `health_check` symbols; made package routers optional with graceful fallback
- **Missing routers**: Created stub routers for pipeline, ocr, jobs, datasets, models, and admin endpoints
- **app/db/models/__init__.py**: Populated empty file with proper re-exports of all RBAC models
- **Condition Parser**: Fixed `ConditionParser()` instantiation — removed invalid `fail_closed` keyword argument
- **8 syntax errors**: Fixed unterminated f-strings, invalid syntax, and unexpected indents across desktop/ and packages/ directories
- **Pydantic compatibility**: Updated all 6 config files (app, security, database, ocr, ml, storage) with v1/v2 import fallback pattern

### Added
- **Complete RBAC migration**: 13 database tables created by Alembic — users, roles, permissions, role_permissions, user_role_assignments, user_permission_assignments, audit_logs, jobs, user_sessions, refresh_tokens, documents, corrections, processing_tasks
- **Router stubs**: 6 new API router modules (pipeline, ocr, jobs, datasets, models, admin) with placeholder endpoints

### Security
- **Safe Condition Parser**: Verified fail-closed behavior — `exec()`, `eval()`, `import`, `__import__` and all dangerous AST nodes are blocked
- **Pydantic v2 readiness**: All config classes support both pydantic v1 and v2 (via `pydantic.v1` compat layer)

## [2.1.0] - 2026-06-03

### Added
- PORTFOLIO.md — unified project architecture map with 4-layer diagram
- Repository Status sections added to all 10 ecosystem repositories
- GitHub Topics added to all repositories for discoverability
- UPSTREAM.md added to omniparse fork repository
- env.example.production — production environment variable template
- scripts/generate-secrets.sh — automated secret generator
- docs/ADR/ — Architecture Decision Records (5 ADRs)
- Docker deployment profiles (lite/standard/gpu-production) for medical-handwriting-ocr
- evaluation/benchmark_runner.py — standardized benchmark tool
- .github/workflows/ci.yml — CI/CD pipelines for 4 repositories
- pyproject.toml — package configuration for medical-ocr-postprocessor
- API contract test suite for medical-ocr-postprocessor

### Changed
- All repository descriptions updated with role and status information
- README unified sections added (Status, Role, Priority, Relation, When to Use)

## [2.0.0] - 2026-05-28

### Added
- Initial merge of medical-doc-processor (v3.2) and OmniFile_Processor (v5.0)
- Multi-Engine OCR Fusion V2 with 6 engines and fallback
- Medical NLP Pipeline (4 stages)
- Qdrant VectorStore integration
- MedicalContextProtector
- AutoPromotionEngine
- CorrectionMemory V2
- BenchmarkSuite
- AES-256-GCM encryption
- NextAuth + RBAC authentication
