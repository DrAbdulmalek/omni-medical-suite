# RC Checklist — OmniMedical Suite v1.1.2

> **Status:** 🔶 Pre-RC  
> **Target tag:** `v1.1.2-rc1`  
> **Branch:** `feat/rc-hardening-p2` → merge to `main` → tag  
> **Date:** 2026-07-20

---

## 1. Code Quality Gates

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1.1 | `ruff check` passes | ☐ | `ruff check src/ packages/ app/ scripts/` |
| 1.2 | `ruff format --check` passes | ☐ | Consistent formatting |
| 1.3 | `mypy` type check (non-blocking) | ☐ | Zero new errors vs. last run |
| 1.4 | No `# TODO` / `# HACK` in production code | ☐ | `rg -n "# (TODO|HACK)" packages/ src/` |

## 2. Test Gates

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 2.1 | Critical tests pass | ☐ | `pytest tests/test_arabic_rtl.py -v` |
| 2.2 | Unit test suite passes | ☐ | `pytest tests/ -x --ignore=tests/integration` |
| 2.3 | Mobile server smoke test | ☐ | `/health` returns `{status:ok, app_services_loaded:true}` |
| 2.4 | `install_mobile_pwa.sh` idempotent | ☐ | Run twice → both succeed |
| 2.5 | `uninstall_mobile_pwa.sh` preserves `data/` | ☐ | md5sum before/after matches |
| 2.6 | `--purge-data` deletes `data/` | ☐ | With `--yes` confirmation |
| 2.7 | AppImage freshness check exits cleanly | ☐ | Exit 0 or 2 — not 1 (stale) |

## 3. AppImage Build

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 3.1 | `build_appimage.sh --version-from-git --smoke-test` succeeds | ☐ | On clean Ubuntu 22.04 |
| 3.2 | SHA256 checksum generated + verified | ☐ | `sha256sum -c *.sha256` |
| 3.3 | `.last_build_commit` written correctly | ☐ | Matches `git rev-parse HEAD` |

## 4. CI / GitHub Actions

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 4.1 | `ci.yml` passes on feature branch | ☐ | Lint + critical tests |
| 4.2 | `rc-gate.yml` all-green | ☐ | 4 required jobs |
| 4.3 | `appimage-freshness.yml` triggers | ☐ | On tracked file changes |
| 4.4 | `release.yml` dry-run | ☐ | `workflow_dispatch` with test version |

## 5. Git LFS

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 5.1 | `.gitattributes` rules comprehensive | ☐ | 10 categories covered |
| 5.2 | `audit-lfs-coverage.sh` reports coverage | ☐ | No large files missing |
| 5.3 | `migrate-to-lfs.sh --dry-run` works | ☐ | Preview migration |
| 5.4 | Fresh clone with LFS works | ☐ | `git lfs fetch --all` |

## 6. Documentation

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 6.1 | Release notes complete | ☐ | `docs/RELEASE_NOTES_v1.1.2.md` |
| 6.2 | Changelog updated | ☐ | `docs/CHANGELOG.md` |
| 6.3 | AppImage Manjaro guide current | ☐ | `docs/APPIIMAGE_MANJARO.md` |

## 7. Security

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 7.1 | `bandit -ll` no high-severity | ☐ | In `src/`, `packages/`, `app/` |
| 7.2 | No hardcoded secrets in git history | ☐ | `credential-scan.yml` passes |
| 7.3 | PAT not stored in `.git/config` | ☐ | After push operations |

## 8. Deployment

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 8.1 | HF Space deployment succeeds | ☐ | `deploy-to-hf.yml` |
| 8.2 | Docker build succeeds | ☐ | `Dockerfile` + `Dockerfile.api` |
| 8.3 | `install_mobile_pwa.sh` on clean Manjaro | ☐ | Full systemd lifecycle |

---

## Sign-Off

| Role | Name | Date | Approved |
|------|------|------|----------|
| Lead Developer | DrAbdulmalek | ____/____/____ | ☐ |

**All checks must be ✅ before tagging `v1.1.2-rc1`.**
