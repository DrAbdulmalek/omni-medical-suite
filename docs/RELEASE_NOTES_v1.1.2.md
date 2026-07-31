# Release Notes — OmniMedical Suite v1.1.2

**Release Date:** 2026-07-20  
**Tag:** `v1.1.2-rc1`  
**Branch:** `feat/rc-hardening-p2` → `main`

---

## Summary

v1.1.2 is a hardening and infrastructure release that delivers: a fully rewritten PWA installer with systemd integration, AppImage freshness tracking with CI, comprehensive Git LFS migration tooling, and an RC quality gate workflow. This release ensures that the mobile PWA runs as a proper system service on Linux/Manjaro, that AppImage builds are never stale, and that large binary assets can be efficiently stored via Git LFS.

---

## Highlights

### PWA Installer Rewrite (P0/P1 — Merged)

The `install_mobile_pwa.sh` and `uninstall_mobile_pwa.sh` scripts have been completely rewritten from simple desktop-shortcut creators into full-featured system installers. The new installer creates a Python virtual environment, installs all dependencies (flask, opencv-python-headless, pydantic, Pillow, numpy), generates a systemd user service with proper `Environment=` lines on separate rows, and verifies the server is healthy before completing. The uninstaller cleanly removes all artifacts while preserving user data by default, with `--purge-data` for complete removal after double confirmation.

### AppImage Freshness Tracking (P1 — Merged)

A new `check_appimage_freshness.py` script compares the git commit recorded at AppImage build time (in `packages/desktop/.last_build_commit`) against the latest commits to tracked source files. Integrated into CI as a warning-only check via `.github/workflows/appimage-freshness.yml`.

### RC Quality Gate (P2-1)

A new `rc-gate.yml` workflow provides a comprehensive quality gate with 8 jobs: lint (ruff), type check (mypy, non-blocking), critical tests, mobile server smoke, AppImage freshness, security (bandit), LFS audit, and gate summary. All required jobs must pass before a release candidate can be tagged.

### Release Workflow (P2-1)

The `release.yml` workflow has been completely rewritten to support: multi-job AppImage build → GitHub Release → Docker push, SHA256 checksum attachment, pre-release tag detection (`-rc*`, `-beta*`, `-alpha*`), and `workflow_dispatch` for manual releases.

### Git LFS Migration Tooling (P2-3)

The `.gitattributes` file already covers 10 categories of binary/large-text assets (from P1-4 audit). A new `scripts/migrate-to-lfs.sh` provides a one-time history-rewriting migration script with `--dry-run` and `--above=SIZE` flags. The CI workflow includes an LFS coverage audit step.

---

## Detailed Changes

### New Files

| File | Description |
|------|-------------|
| `.github/workflows/rc-gate.yml` | RC quality gate — 8 jobs, 4 required |
| `docs/RC_CHECKLIST_v1.1.2.md` | 32-item checklist across 8 categories |
| `docs/RELEASE_NOTES_v1.1.2.md` | This file — release notes |
| `scripts/migrate-to-lfs.sh` | One-time LFS migration script with dry-run |

### Modified Files

| File | Change |
|------|--------|
| `.github/workflows/ci.yml` | Extended triggers to `feat/**` and `fix/**` |
| `.github/workflows/release.yml` | Complete rewrite: AppImage + Docker + pre-release |

### Merged from P0+P1

| File | Change |
|------|--------|
| `scripts/install_mobile_pwa.sh` | Full installer (systemd + venv + health check) |
| `scripts/uninstall_mobile_pwa.sh` | Complete uninstaller (preserves data/ by default) |
| `scripts/check_appimage_freshness.py` | Staleness detector for AppImage builds |
| `.github/workflows/appimage-freshness.yml` | Warning-only freshness CI check |
| `packages/desktop/build_appimage.sh` | Writes `.last_build_commit` after build |

---

## Breaking Changes

None. All changes are backward-compatible.

---

## Upgrade Instructions

### From v1.1.1 → v1.1.2

```bash
git pull origin main

# Reinstall PWA (if previously installed)
bash scripts/uninstall_mobile_pwa.sh
bash scripts/install_mobile_pwa.sh

# Verify
curl http://localhost:5000/health

# Check AppImage freshness
python3 scripts/check_appimage_freshness.py
```

### Git LFS (first-time setup)

```bash
# After pulling v1.1.2
git lfs install
git lfs fetch --all
git lfs checkout

# For future migration (history rewrite):
bash scripts/migrate-to-lfs.sh --dry-run
bash scripts/migrate-to-lfs.sh
```

---

## Known Issues

1. **systemd --user in containers**: Falls back to manual launch; full systemd lifecycle must be verified on native Manjaro.
2. **AppImage on Wayland**: May need `QT_QPA_PLATFORM=wayland;xcb` for fallback on KDE Plasma 6.
3. **LFS migration**: `git lfs migrate import` rewrites history — coordinate with all contributors before running.
