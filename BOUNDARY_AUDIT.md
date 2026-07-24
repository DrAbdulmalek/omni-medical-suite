# Boundary Audit — omni-medical-suite × intelli-file-manager

> Date: 2026-07-24
> Auditor: Architectural Review Bot
> Scope: Identify every place where the two repos are coupled, and the
> remediation status of each.

## Summary of findings

| # | Type | Location | Severity | Status |
|---|------|----------|----------|--------|
| 1 | D — release/CI coupling | `scripts/backup.sh` bundles `intelli-file-manager` | HIGH | **FIXED** in this PR |
| 2 | A — docs coupling | `docs/CHANGELOG.md` mentions IntelliFile | LOW | Acceptable (historical reference) |
| 3 | A — docs coupling | `docs/ADR/005-repo-portfolio-strategy.md` lists `IntelliFile-app` as archived | LOW | Acceptable (ADR documents legacy) |
| 4 | A — docs coupling | `docs/audits/BROKEN_REFERENCES.md` mentions IntelliFile | LOW | Acceptable (audit trail) |
| 5 | A — docs coupling | `docs/اقتراحات/اقتراحات_تطوير_المشاريع.md` mentions IntelliFile | LOW | Acceptable (proposal doc) |
| 6 | A — docs coupling | `docs/LOCAL_GRADIO_GUIDE.md` mentions IntelliFile | LOW | Acceptable (doc reference) |
| 7 | A — docs coupling | `VERIFICATION_LOG.md` mentions IntelliFile | LOW | Acceptable (log) |
| 8 | A — docs coupling | `OPEN_ISSUES.md` mentions IntelliFile | LOW | Acceptable (issues list) |
| 9 | C — code coupling | `tools/repo_admin/git-sync/config/repos.txt` lists `IntelliFile-app` | LOW | Acceptable (legacy archived repo, in denylist) |
| 10 | C — code coupling | `tools/repo_admin/git-sync/config/governance.yaml` denies `IntelliFile-app` | LOW | Acceptable (correctly denied) |
| 11 | C — code coupling | `tools/repo_admin/git-sync/master_orchestrator.py` lists `IntelliFile-app` | LOW | Acceptable (legacy reference) |
| 12 | A — docs coupling | `tools/repo_admin/git-sync/GOVERNANCE.md` lists `IntelliFile-app` as archived | LOW | Acceptable |
| 13 | C — code duplication | `packages/omnifile/__init__.py`, `packages/file_processor/__init__.py`, `packages/handwriting/__init__.py` are duplicates (same MD5) | MED | Out of scope — internal cleanup, not cross-repo |
| 14 | C — code duplication | `apps/handwriting-demo/variants/handwriting-ocr/__init__.py` duplicates the above | MED | Out of scope — internal cleanup |

## Inverse direction (intelli-file-manager → omni-medical-suite)

| # | Type | Location | Severity | Status |
|---|------|----------|----------|--------|
| 15 | B — code coupling | `src/core/classifier.py` has `classify_medical()` and `classify_file_medical()` methods with Arabic medical keyword dict | HIGH | To be fixed in PR `intellifile-scope-reset` |
| 16 | A — docs coupling | `AI_WORKLOG.md` mentions omni-medical-suite (audit trail) | LOW | Acceptable |
| 17 | A — docs coupling | `PRODUCT_IDENTITY.md` mentions omni-medical-suite as sibling project | LOW | Acceptable (correctly framed as separate) |
| 18 | A — docs coupling | `SECURITY_NOTES.md` mentions omni-medical-suite | LOW | Acceptable |
| 19 | A — docs coupling | `REPO_POLICY.md` mentions omni-medical-suite | LOW | Acceptable |
| 20 | A — docs coupling | `docs/ROADMAP.md` mentions omni-medical-suite boundary | LOW | Acceptable |
| 21 | A — docs coupling | `CONTRIBUTING.md` mentions "DICOM" in commit message example | LOW | To be fixed in PR `intellifile-scope-reset` (replaced with general example) |

## What this PR fixes

- Finding #1: `scripts/backup.sh` no longer bundles `intelli-file-manager` or any
  sibling repo. Each repo must back up itself.

## What this PR does NOT fix (deferred)

- Findings #2-12, #16-20: Documentation references to the sibling project are
  acceptable when they correctly frame the boundary (e.g., "IntelliFile-app is
  archived", "intelli-file-manager is a separate project"). These are historical
  / context references, not active coupling.
- Finding #13, #14: Internal package duplication is an omni-medical-suite internal
  concern, not a cross-repo boundary issue. Tracked in OPEN_ISSUES.md.
- Finding #15: intelli-file-manager's `classify_medical()` is a HIGH severity
  boundary violation on the *other* repo. Fixed in that repo's
  `intellifile-scope-reset` PR.
- Finding #21: Minor wording fix in intelli-file-manager's CONTRIBUTING.md.
  Fixed in same PR as #15.

## Verification

After this PR merges:
- `git grep -n "intelli-file-manager" scripts/` returns no matches
- `git grep -n "intelli_file" scripts/` returns no matches
- `git grep -n "IntelliFile" scripts/` returns no matches
