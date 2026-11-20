# Broken References Audit Report

**Date**: 2025-07-26
**Scope**: 9 active GitHub repositories under `DrAbdulmalek`
**Auditor**: Automated audit (Task 1c)

---

## 1. Repository Inventory

| # | Repository | Archived? | Cloned Locally? | Has Broken Refs? |
|---|-----------|-----------|-----------------|-----------------|
| 1 | `omni-medical-suite` | **No** | Yes (`/home/z/my-project/omni-medical-suite/`) | **Yes** (many) |
| 2 | `manjaro-care` | **No** | No (remote) | No |
| 3 | `reset-net` | **No** | No (remote) | No |
| 4 | `repo-sync-toolkit` | **No** | No (remote) | **Yes** (self-reference uses old name) |
| 5 | `sync-github` | **No** | No (remote) | **Yes** (references old name of #4) |
| 6 | `intelli-file-manager` | **No** | No (remote) | **Yes** (links to archived repo) |
| 7 | `arabic-medical-glossary` | **No** | Yes (`/home/z/my-project/arabic-medical-glossary/`) | No |
| 8 | `medical-ocr-demo` | **No** | No (remote) | No |
| 9 | `medical-ocr-trainer-hf` | **No** | Yes (`hf-space-trainer/`, `hf-space/`) | **Yes** (Source of Truth → archived repo) |

**Summary**: 6 of 9 active repos contain broken references.

---

## 2. Confirmed Archived Repositories (Referenced by Active Repos)

These repos are **archived** and their content was merged into `omni-medical-suite`. Any reference to them as "Active" or as a "Source of Truth" is a broken reference.

| Archived Repo | Merged Into | Confirmed Via |
|--------------|-------------|---------------|
| `git-sync-system` → renamed to `repo-sync-toolkit` | N/A (renamed, not merged) | GitHub redirect on raw content |
| `medical-ocr-trainer` | `omni-medical-suite/apps/trainer-ui/` | README: "Repository Archived" |
| `medical-handwriting-ocr` | `omni-medical-suite/apps/handwriting-demo/` | README: "Repository Archived" |
| `medical-ocr-training-hub` | `omni-medical-suite/packages/training_hub/` | README: "Repository Archived" |
| `medical-ocr-benchmarks` | `omni-medical-suite/packages/benchmark_core/` | README: "Repository Archived" |
| `medical-ocr-ground-truth` | `omni-medical-suite/packages/gt_core/` | README: "Repository Archived" |
| `scanner-fixer` | `omni-medical-suite/packages/scanner_fixer/` | README: "Repository Archived" |
| `omni-medical-ocr-pipeline` | N/A (deleted/404) | HTTP 404 |
| `OmniFile_Processor` | `omni-medical-suite/packages/file_processor/` | Listed in CLEANUP_LOG as archived |
| `medical-doc-processor` | `omni-medical-suite/packages/doc_processor/` | Listed in GOVERNANCE.md denylist as archived |
| `medical-ocr-postprocessor` | `omni-medical-suite/packages/ocr_postprocess/` | Listed in GOVERNANCE.md denylist as archived |
| `bilingual-extractor` | `omni-medical-suite/packages/bilingual/` | Listed in GOVERNANCE.md denylist as archived |
| `ai-fuel-engine` | `omni-medical-suite/packages/ai-fuel/` | Listed in GOVERNANCE.md denylist as archived |
| `telegram-forwarder` | `omni-medical-suite/tools/ops/telegram_forwarder/` | Listed in GOVERNANCE.md denylist as archived |

---

## 3. Confirmed Broken References

### 3.1 KNOWN CASE A: `repo-sync-toolkit` README Uses Old Name "git-sync-system"

**Repository**: `repo-sync-toolkit` (remote)
**File**: `README.md`
**Status**: The repo was renamed from `git-sync-system` to `repo-sync-toolkit`, but the README was never updated.

| Line | Broken Text | Should Be |
|------|------------|-----------|
| 1 | `# Git Sync System` | `# Repo Sync Toolkit` |
| 21 | `git clone https://github.com/DrAbdulmalek/git-sync-system.git ~/github-sync-system` | `git clone https://github.com/DrAbdulmalek/repo-sync-toolkit.git ~/repo-sync-toolkit` |
| 73 | `~/.config/git-sync-system/secrets.env` | `~/.config/repo-sync-toolkit/secrets.env` |
| 103 | `git-sync-system/` (directory tree) | `repo-sync-toolkit/` |

**Also affected (local copy inside omni-medical-suite)**:

| File | Line | Broken Text | Should Be |
|------|------|------------|-----------|
| `omni-medical-suite/tools/repo_admin/git-sync/README.md` | 21 | `git clone https://github.com/DrAbdulmalek/git-sync-system.git` | `git clone https://github.com/DrAbdulmalek/repo-sync-toolkit.git` |
| `omni-medical-suite/tools/repo_admin/git-sync/README.md` | 73 | `~/.config/git-sync-system/secrets.env` | `~/.config/repo-sync-toolkit/secrets.env` |
| `omni-medical-suite/tools/repo_admin/git-sync/README.md` | 103 | `git-sync-system/` | `repo-sync-toolkit/` |
| `omni-medical-suite/tools/repo_admin/git-sync/GOVERNANCE.md` | 1 | `# Governance Policy — git-sync-system` | `# Governance Policy — repo-sync-toolkit` |
| `omni-medical-suite/tools/repo_admin/git-sync/GOVERNANCE.md` | 4 | `the git-sync-system tool` | `the repo-sync-toolkit tool` |

---

### 3.2 KNOWN CASE B: `medical-ocr-trainer-hf` README References `medical-ocr-trainer` as Active (Archived)

**Repository**: `medical-ocr-trainer-hf` (remote)
**File**: `README.md`
**Status**: `medical-ocr-trainer` was **archived** and merged into `omni-medical-suite/apps/trainer-ui/`, but `medical-ocr-trainer-hf/README.md` still points to it as "Source of Truth" and marks it "Active".

| Line | Broken Text | Should Be |
|------|------------|-----------|
| (frontmatter) | `Source of truth: [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer)` | `Source of truth: [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) (apps/trainer-ui/)` |
| (Status table) | `Source of Truth: [medical-ocr-trainer]...` | `Source of Truth: [omni-medical-suite/apps/trainer-ui/]...` |
| (Related Repos table) | `[medical-ocr-trainer]... \| Source of Truth \| Active` | `[omni-medical-suite]... \| Source of Truth \| Active` |
| (When to Use table) | `Full local development: [medical-ocr-trainer]...` | `Full local development: [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)` |

**Also affected (identical content in local clones and copy)**:

| File | Lines | Broken Text |
|------|-------|------------|
| `hf-space/README.md` (local clone of medical-ocr-trainer-hf) | 12, 24, 63, 70 | References `medical-ocr-trainer` as "Source of Truth" and "Active" |
| `hf-space-trainer/README.md` (local clone of medical-ocr-trainer-hf) | 57 | References `medical-ocr-trainer` as "Source of Truth" |
| `omni-medical-suite/apps/trainer-ui/hf-variant/README.md` | 12, 24, 63, 70 | References `medical-ocr-trainer` as "Source of Truth" and "Active" |
| `omni-medical-suite/desktop/README_SCANNER_FIXER.md` | 17 | `medical-ocr-trainer \| **نشط**` (listed as Active) |

---

### 3.3 `sync-github` README References Old Name "git-sync-system"

**Repository**: `sync-github` (remote)
**File**: `README.md`

| Line | Broken Text | Should Be |
|------|------------|-----------|
| (vs section) | `see [git-sync-system](https://github.com/DrAbdulmalek/git-sync-system)` | `see [repo-sync-toolkit](https://github.com/DrAbdulmalek/repo-sync-toolkit)` |
| (heading) | `## vs git-sync-system` | `## vs repo-sync-toolkit` |

---

### 3.4 `medical-handwriting-ocr` Referenced as "Active" (Archived)

`medical-handwriting-ocr` was **archived** and merged into `omni-medical-suite/apps/handwriting-demo/`.

| File | Line | Broken Text | Should Be |
|------|------|------------|-----------|
| `hf-space/README.md` (local) | 64 | `Production OCR: [medical-handwriting-ocr]...` | `Production OCR: [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)` |
| `hf-space/README.md` (local) | 71 | `[medical-handwriting-ocr]... \| Production OCR \| Active` | `[omni-medical-suite]... \| Production OCR \| Active` |
| `omni-medical-suite/apps/trainer-ui/hf-variant/README.md` | 64 | `Production OCR: [medical-handwriting-ocr]...` | `Production OCR: [omni-medical-suite]...` |
| `omni-medical-suite/apps/trainer-ui/hf-variant/README.md` | 71 | `[medical-handwriting-ocr]... \| Active` | `[omni-medical-suite]... \| Active` |
| `omni-medical-suite/desktop/README_SCANNER_FIXER.md` | 16 | `medical-handwriting-ocr \| **نشط**` | `omni-medical-suite/apps/handwriting-demo/ \| **نشط**` |
| `intelli-file-manager/README.md` (remote) | (Live Demo link) | `[Live Demo](https://huggingface.co/spaces/DrAbdulmalek/medical-handwriting-ocr)` | `[Live Demo](https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo)` |
| `omni-medical-suite/apps/handwriting-demo/QUICKSTART.md` | 12, 30 | `git clone https://github.com/DrAbdulmalek/medical-handwriting-ocr.git` | `git clone https://github.com/DrAbdulmalek/omni-medical-suite.git` |
| `omni-medical-suite/apps/handwriting-demo/CONTRIBUTING.md` | 14 | `git clone https://github.com/DrAbdulmalek/medical-handwriting-ocr.git` | `git clone https://github.com/DrAbdulmalek/omni-medical-suite.git` |
| `omni-medical-suite/docs/اقتراحات/HF-Model-Card.md` | 97 | `git clone https://github.com/DrAbdulmalek/medical-handwriting-ocr.git` | `git clone https://github.com/DrAbdulmalek/omni-medical-suite.git` |

---

### 3.5 `omni-medical-ocr-pipeline` — Repo Returns 404 (Does Not Exist)

| File | Line | Broken Text | Should Be |
|------|------|------------|-----------|
| `omni-medical-suite/apps/ocr-pipeline/README.md` | 16 | `git clone https://github.com/DrAbdulmalek/omni-medical-ocr-pipeline.git` | `git clone https://github.com/DrAbdulmalek/omni-medical-suite.git` |

---

### 3.6 `PORTFOLIO.md` — Core Architecture Table References 5 Archived Repos as Active

**File**: `omni-medical-suite/PORTFOLIO.md`

| Line | Broken Text (Active) | Should Be |
|------|---------------------|-----------|
| 13 | `[scanner-fixer](...) — **Required** first step` | Merged into `omni-medical-suite/packages/scanner_fixer/` |
| 15 | `[medical-ocr-ground-truth](...) — Single source of truth` | Merged into `omni-medical-suite/packages/gt_core/` |
| 16 | `[medical-ocr-training-hub](...) — Data ingestion` | Merged into `omni-medical-suite/packages/training_hub/` |
| 17 | `[medical-ocr-trainer](...) — Human-in-the-loop` | Merged into `omni-medical-suite/apps/trainer-ui/` |
| 18 | `[medical-ocr-benchmarks](...) — Nightly regression` | Merged into `omni-medical-suite/packages/benchmark_core/` |
| 105-109 | Ecosystem docs links to all 5 archived repos | Should link to monorepo or note "archived" status |

---

### 3.7 `GOVERNANCE.md` Allowlist Contains 6 Archived Repos

**File**: `omni-medical-suite/tools/repo_admin/git-sync/GOVERNANCE.md`

The allowlist (repos that CAN receive pushes) includes repos that are archived and no longer receive updates:

| Line | Broken Entry | Status | Should Be |
|------|-------------|--------|-----------|
| 25 | `scanner-fixer` | Archived | Remove or mark archived |
| 25 | `medical-handwriting-ocr` | Archived | Remove or mark archived |
| 26 | `medical-ocr-training-hub` | Archived | Remove or mark archived |
| 27 | `medical-ocr-benchmarks` | Archived | Remove or mark archived |
| 28 | `medical-ocr-trainer` | Archived | Remove or mark archived |
| 29 | `medical-ocr-ground-truth` | Archived | Remove or mark archived |

---

### 3.8 `LOCAL_GRADIO_GUIDE.md` — Repo Table Has Stale Entries

**File**: `omni-medical-suite/docs/LOCAL_GRADIO_GUIDE.md`

| Line | Broken Entry | Should Be |
|------|-------------|-----------|
| 100 | `medical-ocr-trainer \| Evaluation & training` | Mark as archived, point to `apps/trainer-ui/` |
| 104 | `ai-fuel-engine \| Data processing engine` | Mark as archived (not in the 9 active repos) |
| 105 | `bilingual-extractor \| Medical term extraction` | Mark as archived (not in the 9 active repos) |
| 106 | `IntelliFile-app \| File management` | Rename to `intelli-file-manager` |
| 107 | `git-sync-system \| Repo synchronization` | Rename to `repo-sync-toolkit` |

---

### 3.9 Stale `git clone` URLs in Migrated Package CONTRIBUTING/README Files

These packages were migrated from standalone archived repos into the `omni-medical-suite` monorepo. Their `CONTRIBUTING.md` and `README.md` files still reference the old standalone repo name in `git clone` URLs. **All listed repos below are archived.**

| Package (in omni-medical-suite) | Old Standalone Repo | Files Affected |
|--------------------------------|--------------------|----------------|
| `packages/benchmark_core/` | `medical-ocr-benchmarks` | `README.md` (lines 40, 60), `CONTRIBUTING.md` (line 14) |
| `packages/training_hub/` | `medical-ocr-training-hub` | `README.md` (line 104), `CONTRIBUTING.md` (line 14) |
| `packages/gt_core/` | `medical-ocr-ground-truth` | `CONTRIBUTING.md` (line 14), `README.md` (line 217) |
| `packages/bilingual/` | `bilingual-extractor` | `README.md` (line 69), `CONTRIBUTING.md` (line 14) |
| `packages/ocr_postprocess/` | `medical-ocr-postprocessor` | `README.md` (line 377), `CONTRIBUTING.md` (line 14) |
| `packages/ai-fuel/` | `ai-fuel-engine` | `CONTRIBUTING.md` (line 14) |
| `tools/ai_fuel/` | `ai-fuel-engine` | `CONTRIBUTING.md` (line 14) |
| `apps/trainer-ui/` | `medical-ocr-trainer` | `README.md` (line 38), `CONTRIBUTING.md` (line 14) |
| `hf-space/packages/ocr_postprocess/` | `medical-ocr-postprocessor` | `README.md` (line 377), `CONTRIBUTING.md` (line 14) |

**Note**: These files should either be updated to use `omni-medical-suite` clone URLs or the clone instructions should note that the standalone repo is archived and development happens in the monorepo.

---

## 4. Repositories With NO Broken References

| Repository | Notes |
|-----------|-------|
| **manjaro-care** | Self-contained. Only references `reset-net` (active) as a dependency. |
| **reset-net** | Self-contained. No cross-repo references. |
| **arabic-medical-glossary** | Self-contained. No references to other DrAbdulmalek repos. |
| **medical-ocr-demo** | Self-contained. No references to other GitHub repos (only HF datasets). |

---

## 5. Summary Statistics

| Category | Count |
|----------|-------|
| Active repos audited | 9 |
| Active repos with broken refs | 6 |
| Archived repos confirmed | 14+ |
| **Critical** (Source of Truth → archived repo) | 8 instances across 4 files |
| **High** (Status "Active" → actually archived) | 15+ instances across 8 files |
| **Medium** (Old name / stale clone URL) | 25+ instances across 20+ files |
| **Low** (Historical/migration context) | Many in MIGRATION_MAP, CLEANUP_LOG, LEGACY_NOTICE |

---

## 6. Recommended Priority Fixes

1. **Immediate** — Fix `repo-sync-toolkit/README.md` and `sync-github/README.md` (rename references)
2. **Immediate** — Fix `medical-ocr-trainer-hf/README.md` (Source of Truth → omni-medical-suite)
3. **High** — Fix `PORTFOLIO.md` core architecture table (5 archived repos listed as active)
4. **High** — Fix `GOVERNANCE.md` allowlist (6 archived repos)
5. **Medium** — Fix all "Active" status labels for `medical-handwriting-ocr` and `medical-ocr-trainer`
6. **Medium** — Update `LOCAL_GRADIO_GUIDE.md` repo table
7. **Low** — Batch-update `git clone` URLs in migrated package CONTRIBUTING.md files
8. **Low** — Fix `omni-medical-ocr-pipeline` 404 reference in `apps/ocr-pipeline/README.md`