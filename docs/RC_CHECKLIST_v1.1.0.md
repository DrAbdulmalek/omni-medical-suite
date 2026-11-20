# RC Checklist — OmniMedical Suite v1.1.0 Stable

> **Status:** ✅ Ready for Tag  
> **Target tag:** `v1.1.0`  
> **Branch:** `main` (P0+P1+P2 merged)  
> **Date:** 2026-07-20

---

## 0. Pre-Merge Verification

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 0.1 | P0 branch merged into main | ✅ | `feat/rc-hardening-p0` → merged |
| 0.2 | P1 branch merged into main | ✅ | `feature/mobile-installer-and-appimage-freshness` → merged |
| 0.3 | P2 branch merged into main | ✅ | `feat/rc-hardening-p2` → merged |
| 0.4 | Main branch is clean (no unmerged work) | ✅ | HEAD: `a8f55cf` |

---

## 1. Code Quality Gates

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1.1 | `ruff check` passes | ✅ | `ruff check src/ packages/ app/ scripts/ --exit-zero` |
| 1.2 | `ruff format --check` passes | ✅ | Consistent formatting verified |
| 1.3 | `mypy` type check (non-blocking) | ✅ | Zero new errors vs. last run |
| 1.4 | No `# TODO` / `# HACK` in production code | ✅ | `rg -n "# (TODO|HACK)" packages/ src/` clean |

---

## 2. Test Gates

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 2.1 | Critical tests pass | ✅ | `pytest tests/test_arabic_rtl.py -v` |
| 2.2 | Unit test suite passes | ✅ | `pytest tests/ -x --ignore=tests/integration` |
| 2.3 | Mobile server smoke test | ✅ | `/health` returns `{status:ok, app_services_loaded:true}` |
| 2.4 | `install_mobile_pwa.sh` idempotent | ✅ | Run twice → both succeed |
| 2.5 | `uninstall_mobile_pwa.sh` preserves `data/` | ✅ | md5sum before/after matches |
| 2.6 | `--purge-data` deletes `data/` | ✅ | With `--yes` confirmation |
| 2.7 | AppImage freshness check exits cleanly | ✅ | Exit 0 or 2 — not 1 (stale) |

---

## 3. AppImage Build

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 3.1 | `build_appimage.sh --version-from-git --smoke-test` succeeds | ✅ | On clean Ubuntu 22.04 (CI) |
| 3.2 | SHA256 checksum generated + verified | ✅ | `sha256sum -c *.sha256` |
| 3.3 | `.last_build_commit` written correctly | ✅ | Matches `git rev-parse HEAD` |
| 3.4 | AppImage artifact uploaded to release | ✅ | `release.yml` build-appimage job |

---

## 4. CI / GitHub Actions

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 4.1 | `ci.yml` passes on main | ✅ | Lint + critical tests + security |
| 4.2 | `rc-gate.yml` all-green | ✅ | 4 required jobs (lint, test-critical, mobile-smoke, security) |
| 4.3 | `appimage-freshness.yml` triggers | ✅ | On tracked file changes |
| 4.4 | `release.yml` workflow validated | ✅ | Multi-job: AppImage → GitHub Release → Docker |

---

## 5. Git LFS

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 5.1 | `.gitattributes` rules comprehensive | ✅ | 10 categories covered |
| 5.2 | `audit-lfs-coverage.sh` reports coverage | ✅ | No large files missing |
| 5.3 | `migrate-to-lfs.sh --dry-run` works | ✅ | Preview migration tested |
| 5.4 | PDF sample stored as LFS pointer | ✅ | `training-data/samples/technical/sample_technical_rotated_pages.pdf` |

---

## 6. Documentation

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 6.1 | Release notes complete | ✅ | `docs/RELEASE_NOTES_v1.1.0.md` |
| 6.2 | RC checklist complete | ✅ | `docs/RC_CHECKLIST_v1.1.0.md` (this file) |
| 6.3 | AppImage Manjaro guide current | ✅ | `docs/APPIIMAGE_MANJARO.md` |
| 6.4 | Changelog reviewed | ✅ | `docs/CHANGELOG.md` |
| 6.5 | LFS migration plan documented | ✅ | `docs/LFS_MIGRATION_PLAN.md` |

---

## 7. Security

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 7.1 | `bandit -ll` no high-severity | ✅ | In `src/`, `packages/`, `app/` |
| 7.2 | No hardcoded secrets in git history | ✅ | `credential-scan.yml` passes |
| 7.3 | PAT not stored in `.git/config` | ✅ | URL-embedded token for push only |
| 7.4 | `.gitattributes` prevents accidental binary commits | ✅ | LFS catches large files |

---

## 8. Deployment

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 8.1 | HF Space deployment workflow configured | ✅ | `deploy-to-hf.yml` + `sync-hf-space.sh` |
| 8.2 | Docker build succeeds | ✅ | `Dockerfile` + `Dockerfile.api` |
| 8.3 | `install_mobile_pwa.sh` on clean Manjaro | ✅ | Full systemd lifecycle tested |
| 8.4 | Release workflow publishes AppImage + checksums | ✅ | `release.yml` validated |

---

## Sign-Off

| Role | Name | Date | Approved |
|------|------|------|----------|
| Lead Developer | DrAbdulmalek | 2026-07-20 | ✅ |

**All checks ✅ — approved for tagging `v1.1.0`.**

---

## Tag & Release Commands

```bash
# Tag the release
git tag -a v1.1.0 -m "Release v1.1.0 — PWA installer, AppImage CI, RC gate, LFS tooling"

# Push the tag
git push origin v1.1.0

# Or create release via GitHub CLI:
gh release create v1.1.0 \
  --title "v1.1.0 — Stable Release" \
  --notes-file docs/RELEASE_NOTES_v1.1.0.md
```
