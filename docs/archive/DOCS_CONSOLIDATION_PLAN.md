# Documentation Consolidation Plan

**Date:** 2026-07-11 (revised 2026-07-11 — ARCHIVE category added)
**Scope:** 24 root-level markdown files (excluding README.md, STATE_OF_TRUTH.md, PARTIAL_DUPLICATES_DECISION_QUEUE.md, VERIFICATION_LOG.md, GRADIO_APPS_DECISION.md which remain at root)

**Revision note:** Original plan classified 5 audit-trail files as DELETE. These are now ARCHIVE — they document how and when decisions were made and contain active PENDING items. See new ARCHIVE section below.

---

## Summary Table

| File | Lines | Bytes | Category | Action | Destination |
|------|------:|------:|----------|--------|-------------|
| CONTRIBUTING.md | 236 | 6,239 | KEEP AT ROOT | keep | _(root)_ |
| SECURITY.md | 639 | 19,884 | KEEP AT ROOT | keep | _(root)_ |
| MODES.md | 128 | 3,694 | MOVE TO docs/ | move | `docs/MODES.md` |
| MONITORING.md | 683 | 37,358 | MOVE TO docs/ | move | `docs/MONITORING.md` |
| PIPELINE.md | 193 | 7,952 | MOVE TO docs/ | move | `docs/PIPELINE.md` |
| RELEASE_NOTES.md | 280 | 11,332 | MOVE TO docs/ | move | `docs/RELEASE_NOTES.md` |
| ROADMAP.md | 103 | 4,477 | MOVE TO docs/ | move | `docs/ROADMAP.md` |
| DEPLOY.md | 56 | 1,224 | MERGE | merge | `docs/DEPLOYMENT.md` |
| README-Deployment.md | 73 | 1,951 | MERGE | merge | `docs/DEPLOYMENT.md` |
| DEPLOYMENT_GUIDE.md | 410 | 10,336 | MERGE | merge | `docs/DEPLOYMENT.md` |
| MAINTENANCE.md | 1,397 | 49,170 | MERGE | merge | `docs/MAINTENANCE.md` |
| MAINTENANCE_LOG.md | 102 | 2,722 | MERGE | merge | `docs/MAINTENANCE.md` |
| CHANGELOG.md | 60 | 3,568 | MERGE | merge | `docs/CHANGELOG.md` |
| CLEANUP_LOG.md | 194 | 7,425 | MERGE | merge | `docs/CHANGELOG.md` |
| MIGRATION_REPORT.md | 46 | 1,886 | MERGE | merge | `docs/CHANGELOG.md` |
| BROKEN_REFERENCES.md | 238 | 14,908 | ARCHIVE | ~~move→`docs/audits/`~~ **DONE** | `docs/audits/BROKEN_REFERENCES.md` |
| DUPLICATE_VERIFICATION_REPORT.md | 4,127 | 398,214 | ARCHIVE | ~~move→`docs/audits/`~~ **DONE** | `docs/audits/DUPLICATE_VERIFICATION_REPORT.md` |
| GRADIO_APPS_DECISION.md | 139 | 10,708 | KEEP AT ROOT | **STAYS** — 18 PENDING decisions not yet resolved | _(root)_ |
| MODEL_CARD.md | 114 | 3,365 | DELETE | delete | — |
| PORTFOLIO.md | 110 | 5,414 | DELETE | delete | — |
| PROPOSALS.md | 107 | 10,468 | DELETE | delete | — |
| PYTEST_REPORT.md | 284 | 13,595 | ARCHIVE | ~~move→`docs/audits/`~~ **DONE** | `docs/audits/PYTEST_REPORT.md` |
| TIERS.md | 199 | 5,207 | DELETE | delete | — |
| WORKFLOW_AUDIT.md | 302 | 18,129 | ARCHIVE | ~~move→`docs/audits/`~~ **DONE** | `docs/audits/WORKFLOW_AUDIT.md` |

### Category Counts

| Category | File Count |
|----------|-----------:|
| KEEP AT ROOT | 3 (incl. GRADIO_APPS_DECISION.md — active PENDING decisions) |
| MOVE TO docs/ | 5 |
| MERGE | 8 (3 groups) |
| ARCHIVE → `docs/audits/` | 4 (moved; GRADIO_APPS_DECISION.md stays at root) |
| DELETE | 4 |
| **Total processed** | **24** |

---

## Category: KEEP AT ROOT

These files follow GitHub conventions and must remain at the repository root for platform recognition.

| File | Reason |
|------|--------|
| `CONTRIBUTING.md` | GitHub standard — displayed on PR/issue pages and the repo homepage |
| `SECURITY.md` | GitHub standard — displayed on the Security tab; enables security policy |

_(5 additional files already confirmed to stay at root: README.md, STATE_OF_TRUTH.md, PARTIAL_DUPLICATES_DECISION_QUEUE.md, VERIFICATION_LOG.md, GRADIO_APPS_DECISION.md)_

---

## Category: MOVE TO docs/

These are general-purpose documentation files. They do not overlap with each other and serve as standalone references. They should be moved as-is (no content changes required beyond updating internal links if any).

| File | Lines | Purpose |
|------|------:|---------|
| `MODES.md` | 128 | Describes three deployment modes (Lite / Standard / Production) with Docker Compose configs |
| `MONITORING.md` | 683 | Full observability guide: structured logging, Prometheus, Sentry, Grafana, benchmark tracking |
| `PIPELINE.md` | 193 | Continuous improvement pipeline: GT import → benchmarks → trainer → model update loop |
| `RELEASE_NOTES.md` | 280 | v1.0.0 release notes (Arabic/English), feature summary, known issues |
| `ROADMAP.md` | 103 | Versioned roadmap with completed milestones and future plans |

**Action:** `git mv <file> docs/<file>` for each file above. Update any cross-references in README.md or other docs.

---

## Category: MERGE

### Merge Group 1: Deployment → `docs/DEPLOYMENT.md`

Three files cover deployment with significant overlap. Consolidate into a single comprehensive guide.

| Source File | Lines | Sections Contributed |
|-------------|------:|----------------------|
| `DEPLOYMENT_GUIDE.md` | 410 | **Primary base.** Full guide covering local dev, Docker, HF Spaces, production server, backup/restore, troubleshooting (Arabic + English) |
| `DEPLOY.md` | 56 | Quick HF Spaces deploy steps (prerequisites, `git push space main`, HF_TOKEN secret) |
| `README-Deployment.md` | 73 | v2.0 quick start with `docker-compose up -d`, health check, Gradio/Angular/MinIO/Redis URLs |

**Merge strategy:**
1. Start with `DEPLOYMENT_GUIDE.md` as the base (it is the most comprehensive).
2. Integrate the concise HF Spaces quick-deploy from `DEPLOY.md` into the existing HF Spaces section.
3. Integrate the v2.0 quick-start and service URL reference table from `README-Deployment.md` into a new "Quick Start" section at the top.

**Delete source files after merge:** `DEPLOY.md`, `README-Deployment.md`, `DEPLOYMENT_GUIDE.md`

---

### Merge Group 2: Maintenance → `docs/MAINTENANCE.md`

Two files that together form the complete maintenance documentation.

| Source File | Lines | Sections Contributed |
|-------------|------:|----------------------|
| `MAINTENANCE.md` | 1,397 | **Primary base.** Full runbook: schedules, error-rate/latency/OCR/accuracy runbooks, HF Space build failure, database issues, backup strategy, disaster recovery, dependency management |
| `MAINTENANCE_LOG.md` | 102 | Maintenance schedule table (daily/weekly/monthly tasks), phase-by-phase log of past maintenance runs |

**Merge strategy:**
1. Start with `MAINTENANCE.md` as the base.
2. Append the schedule table and phase log from `MAINTENANCE_LOG.md` as an "Appendix: Maintenance Log" section at the end.
3. Ensure no duplication of the schedule (the runbook's Section 1 covers schedules conceptually; keep the concrete table from the log).

**Delete source files after merge:** `MAINTENANCE.md`, `MAINTENANCE_LOG.md`

---

### Merge Group 3: History & Changelog → `docs/CHANGELOG.md`

Three files that capture project history from different angles.

| Source File | Lines | Sections Contributed |
|-------------|------:|----------------------|
| `CHANGELOG.md` | 60 | **Primary base.** Keep-a-Changelog format entries for v2.2.0 and earlier (fixes, features, breaking changes) |
| `CLEANUP_LOG.md` | 194 | Repository cleanup audit trail: Phase 0 discovery, Phase 1 backup, Phase 2 deletion, Phase 3 archive, Phase 4 rename, final inventory |
| `MIGRATION_REPORT.md` | 46 | Monorepo migration report: 17 merged repos with source→target path mappings |

**Merge strategy:**
1. Start with `CHANGELOG.md` as the base (standard changelog format).
2. Add a new top-level section "## Repository History" before the versioned entries.
3. Under "Repository History", add two subsections:
   - "### Monorepo Migration (2026-07-07)" — content from `MIGRATION_REPORT.md`
   - "### Repository Cleanup (2026-07-07)" — content from `CLEANUP_LOG.md`
4. This preserves the chronological narrative: migration happened first, then cleanup, then versioned changelog entries follow.

**Delete source files after merge:** `CHANGELOG.md`, `CLEANUP_LOG.md`, `MIGRATION_REPORT.md`

---

## Category: ARCHIVE → `docs/audits/`

Audit-trail files that document how and when decisions were made. These are NOT stale documentation — they contain the reasoning behind cleanup actions and, in some cases, active pending decisions. They are moved (not deleted) to `docs/audits/` to keep the root clean while preserving the audit trail.

**> ⚠️ Standing rule: Any file documenting decisions not yet resolved (containing PENDING items or awaiting human review) is an active work file, not stale documentation. It must not be included in any DELETE plan regardless of its age or location.**

| File | Lines | Justification | Status |
|------|------:|---------------|--------|
| `BROKEN_REFERENCES.md` | 238 | Audit of broken cross-repo references (2025-07-26). Documents which references were found broken and what was fixed. | ✅ Moved to `docs/audits/` |
| `DUPLICATE_VERIFICATION_REPORT.md` | 4,127 | Automated verification of 344 duplicate groups (2026-07-10). Source data for PARTIAL_DUPLICATES_DECISION_QUEUE.md analysis. | ✅ Moved to `docs/audits/` |
| `PYTEST_REPORT.md` | 284 | Pytest run results (305 passed / 97 failed / 45 skipped). Historical test baseline. | ✅ Moved to `docs/audits/` |
| `WORKFLOW_AUDIT.md` | 302 | Audit of 213 YAML files identifying 46 remnant GitHub Actions workflows. Documents cleanup decisions. | ✅ Moved to `docs/audits/` |

### Exception: `GRADIO_APPS_DECISION.md` stays at root

This file contains **18 active PENDING decisions** that have not been resolved yet (each file has a unique feature described). It is an **active work document** being used in the current cleanup session.

**It must NOT be moved to `docs/audits/` until all 18 PENDING decisions are resolved.** Once resolved, it can be archived alongside the other audit files.

---

## Category: DELETE

Stale outputs and files whose useful content has been absorbed into living documents. These have no audit-trail value and no pending decisions.

| File | Lines | Justification |
|------|------:|---------------|
| `MODEL_CARD.md` | 114 | HuggingFace model card YAML frontmatter for "Ensemble Baseline Model v1.0". Belongs in the model repository or `model/` directory, not the source repo root |
| `PORTFOLIO.md` | 110 | Architectural portfolio showing pre-monorepo repo structure with strikethrough-deleted repos. Superseded by STATE_OF_TRUTH.md and docs/ARCHITECTURE.md |
| `PROPOSALS.md` | 107 | Feature proposals (Arabic). Content overlaps with and is subsumed by ROADMAP.md which already tracks planned features |
| `TIERS.md` | 199 | Tier comparison (Lite/Standard/Full) with feature matrix. Content fully duplicated by MODES.md which already covers the same three deployment tiers with the same feature breakdown |

**Action:** `git rm <file>` for each file above. No content needs to be preserved elsewhere.

---

## Execution Checklist

- [ ] Create `docs/` directory if not exists
- [ ] MOVE: `git mv MODES.md docs/MODES.md`
- [ ] MOVE: `git mv MONITORING.md docs/MONITORING.md`
- [ ] MOVE: `git mv PIPELINE.md docs/PIPELINE.md`
- [ ] MOVE: `git mv RELEASE_NOTES.md docs/RELEASE_NOTES.md`
- [ ] MOVE: `git mv ROADMAP.md docs/ROADMAP.md`
- [ ] MERGE Group 1: Create `docs/DEPLOYMENT.md` from DEPLOYMENT_GUIDE.md + DEPLOY.md + README-Deployment.md
- [ ] MERGE Group 2: Create `docs/MAINTENANCE.md` from MAINTENANCE.md + MAINTENANCE_LOG.md
- [ ] MERGE Group 3: Create `docs/CHANGELOG.md` from CHANGELOG.md + CLEANUP_LOG.md + MIGRATION_REPORT.md
- [ ] ARCHIVE: ~~`git mv` 4 audit files to `docs/audits/`~~ **DONE**
- [ ] DELETE: `git rm` all 4 files listed in DELETE category
- [ ] Update `README.md` links to point to `docs/` for moved files
- [ ] Verify no broken internal references with a link check pass
- [ ] Commit with message: `docs: consolidate 24 root markdown files per DOCS_CONSOLIDATION_PLAN.md`

---

## Final Root Directory State

After execution, the root will contain only these `.md` files:

```
README.md
STATE_OF_TRUTH.md
PARTIAL_DUPLICATES_DECISION_QUEUE.md
VERIFICATION_LOG.md
GRADIO_APPS_DECISION.md     ← stays until 18 PENDING decisions resolved
CONTRIBUTING.md
SECURITY.md
DOCS_CONSOLIDATION_PLAN.md   ← this file (can be deleted after execution)
```

All other documentation lives under `docs/`.