# Release Notes — OmniMedical Suite v1.1.0

**Release Date:** 2026-07-20  
**Tag:** `v1.1.0`  
**Branch:** `main`  
**Status:** Stable

---

## Summary

OmniMedical Suite v1.1.0 is a major hardening and infrastructure release that delivers: a fully rewritten PWA installer with systemd integration and health checks, AppImage freshness tracking with CI, a comprehensive RC quality gate workflow, a production-grade release pipeline with AppImage + Docker + GitHub Releases, and Git LFS migration tooling. This release consolidates the P0 (core hardening), P1 (mobile installer + AppImage), and P2 (RC gate + release workflow + LFS) workstreams into a single stable release ready for production deployment.

---

## Highlights

### PWA Installer Rewrite (P0/P1)

The `install_mobile_pwa.sh` and `uninstall_mobile_pwa.sh` scripts have been completely rewritten from simple desktop-shortcut creators into full-featured system installers. The new installer performs comprehensive system dependency checks (pacman/apt), creates a Python virtual environment at `~/.omni-mobile-venv`, installs all required dependencies (flask, opencv-python-headless, pydantic, Pillow, numpy), generates a systemd user service with properly separated `Environment=` lines, enables and starts the service with a manual-launch fallback when systemd is unavailable (containers, WSL), runs a health check with up to 15 retries against the `/health` endpoint, and creates a desktop shortcut for easy access. The uninstaller cleanly removes all systemd artifacts, the virtual environment, and desktop entries while preserving user data by default. The `--purge-data` flag is available for complete removal but requires double confirmation ("yes/N" followed by "YES" in capitals) to prevent accidental data loss.

### AppImage Freshness Tracking (P1)

A new `check_appimage_freshness.py` script compares the git commit recorded at AppImage build time (stored in `packages/desktop/.last_build_commit`) against the latest commits to tracked source files. When a tracked file has changed since the last build, the script exits with code 1 (stale) and lists the affected files. This is integrated into CI as a warning-only check via `.github/workflows/appimage-freshness.yml`, ensuring developers are alerted when AppImage rebuilds are needed without blocking the pipeline. The `build_appimage.sh` script now automatically writes the build commit hash after every successful build, creating a seamless freshness-tracking loop.

### RC Quality Gate (P2)

A new `rc-gate.yml` workflow provides a comprehensive quality gate with 8 parallel jobs: lint (ruff), type check (mypy, non-blocking), critical tests, mobile server smoke test, AppImage freshness, security scan (bandit), LFS coverage audit, and a gate summary job. The 4 required jobs (lint, test-critical, mobile-smoke, security) must all pass before the gate is considered green. This workflow runs on pushes to `main` and on manual dispatch, providing a clear go/no-go signal before tagging release candidates.

### Release Workflow (P2)

The `release.yml` workflow has been completely rewritten to support a multi-stage release pipeline: build AppImage on Ubuntu 22.04 → create GitHub Release with auto-generated changelog → build and push Docker images to GHCR. The workflow detects pre-release tags (`-rc*`, `-beta*`, `-alpha*`) and marks them accordingly. It generates SHA256 checksums for all AppImage artifacts and attaches them to the release. Manual releases are supported via `workflow_dispatch` with configurable version and pre-release flags.

### Git LFS Migration Tooling (P2)

The `.gitattributes` file covers 10 categories of binary and large-text assets: data files (CSV, JSONL, Parquet), images (raster and vector), PDFs, Jupyter notebooks, ML model weights, media files, archives, binary executables, large JSON files (tokenizers), and office documents. A new `scripts/migrate-to-lfs.sh` provides a one-time history-rewriting migration script with `--dry-run` for preview and `--above=SIZE` for selective migration. The CI workflow includes an LFS coverage audit step to ensure no large files slip through untracked.

---

## Detailed Changes

### New Files (P2)

| File | Description |
|------|-------------|
| `.github/workflows/rc-gate.yml` | RC quality gate — 8 jobs, 4 required |
| `docs/RC_CHECKLIST_v1.1.0.md` | 35-item checklist across 8 categories |
| `docs/RELEASE_NOTES_v1.1.0.md` | This file — release notes for v1.1.0 stable |
| `scripts/migrate-to-lfs.sh` | One-time LFS migration script with dry-run |

### Modified Files (P2)

| File | Change |
|------|--------|
| `.github/workflows/ci.yml` | Extended triggers to `feat/**` and `fix/**` |
| `.github/workflows/release.yml` | Complete rewrite: AppImage + Docker + pre-release |

### Merged from P1

| File | Change |
|------|--------|
| `scripts/install_mobile_pwa.sh` | Full installer (systemd + venv + health check) |
| `scripts/uninstall_mobile_pwa.sh` | Complete uninstaller (preserves data/ by default) |
| `scripts/check_appimage_freshness.py` | Staleness detector for AppImage builds |
| `.github/workflows/appimage-freshness.yml` | Warning-only freshness CI check |
| `packages/desktop/build_appimage.sh` | Writes `.last_build_commit` after build |

### Merged from P0

| File | Change |
|------|--------|
| `.gitattributes` | Comprehensive LFS tracking (10 categories) |
| `scripts/audit-lfs-coverage.sh` | LFS coverage audit for CI |
| Various observability modules | `log_decision()` instrumentation |
| Benchmark exports | CSV/JSON export + aggregate metrics |

---

## Breaking Changes

None. All changes are backward-compatible.

---

## Upgrade Instructions

### From v1.1.1 → v1.1.0

```bash
git pull origin main
git checkout v1.1.0

# Reinstall PWA (if previously installed)
bash scripts/uninstall_mobile_pwa.sh
bash scripts/install_mobile_pwa.sh

# Verify health
curl http://localhost:5000/health

# Check AppImage freshness
python3 scripts/check_appimage_freshness.py

# Run RC gate locally (optional)
# gh workflow run rc-gate.yml
```

### Git LFS (first-time setup)

```bash
# After pulling v1.1.0
git lfs install
git lfs fetch --all
git lfs checkout

# Preview LFS migration (does not modify history):
bash scripts/migrate-to-lfs.sh --dry-run

# Full migration (rewrites history — coordinate first):
bash scripts/migrate-to-lfs.sh
```

### AppImage (Linux x86_64)

```bash
# Download from GitHub Release
wget https://github.com/DrAbdulmalek/omni-medical-suite/releases/download/v1.1.0/MedicalDocProcessor-1.1.0-x86_64.AppImage
wget https://github.com/DrAbdulmalek/omni-medical-suite/releases/download/v1.1.0/MedicalDocProcessor-1.1.0-x86_64.AppImage.sha256

# Verify checksum
sha256sum -c MedicalDocProcessor-1.1.0-x86_64.AppImage.sha256

# Run
chmod +x MedicalDocProcessor-1.1.0-x86_64.AppImage
./MedicalDocProcessor-1.1.0-x86_64.AppImage
```

---

## Known Issues

1. **systemd --user in containers**: Falls back to manual process launch; full systemd lifecycle must be verified on native Manjaro/Arch with DBUS and XDG_RUNTIME_DIR properly configured.
2. **AppImage on Wayland**: May need `QT_QPA_PLATFORM=wayland;xcb` for fallback on KDE Plasma 6. Set `OMNI_APPIMAGE_OFFSCREEN=1` for headless/CI environments.
3. **LFS migration**: `git lfs migrate import` rewrites history — coordinate with all contributors before running on shared repositories.
4. **rc-gate.yml mobile-smoke job**: May fail in CI if the mobile server module path is not correctly configured for the test environment. The `PYTHONPATH` must include the repository root.

---

## Contributors

- DrAbdulmalek (lead developer, architecture, CI/CD)
