# Known Issues — OmniMedical Suite

> Authoritative list of open + resolved issues affecting releases.
> Last updated: 2026-07-26

---

## Resolved

### 1. AppImage numpy/OpenBLAS crash (CRITICAL) — fixed in v1.2.0

**Affected releases:** v1.1.0, v1.1.1

**Symptom:**
The v1.1.0 and v1.1.1 AppImages crash on launch with:

```
ImportError: libscipy_openblas64_-32a4b2a6.so: ELF load command address/offset not page-aligned
```

**Root cause:**
`packages/scanner_fixer/pyproject.toml` declared `numpy>=1.23` with no upper bound. During the AppImage build (editable install of `scanner_fixer` + PyInstaller bundle), pip resolved to numpy 2.x. numpy 2.x bundles `libscipy_openblas64_` with ELF segment alignment that PyInstaller's onefile extraction corrupts on Linux kernels 5.18+ (Manjaro, Arch, Ubuntu 24.04+). The library then fails to `dlopen()` at runtime.

**Why v1.1.0/v1.1.1 were broken:**
- `packages/desktop/requirements.txt` was pinned to `numpy>=1.24.0,<2.0.0` (correct), but...
- `packages/scanner_fixer/pyproject.toml` had `numpy>=1.23` (no upper bound), and `pip install -e packages/scanner_fixer` runs *after* `pip install -r packages/desktop/requirements.txt` in `release.yml`. pip's resolver upgraded numpy to 2.x to satisfy scanner_fixer's looser constraint, overriding the desktop pin.
- The runtime hook `hook_numpy_openblas.py` mitigates loading issues but cannot fix corrupted ELF alignment.

**Fix (this PR — `fix/appimage-numpy-pin`):**
Pinned `numpy>=1.24.0,<2.0.0` in four places:
1. `packages/scanner_fixer/pyproject.toml` — the original source of the regression
2. `hf-space/packages/scanner_fixer/pyproject.toml` — mirror copy used by HF Space builds
3. `requirements-scanner.txt` — root-level scanner requirements (legacy)
4. `pyproject.toml` (root) — `[project].dependencies` for `pip install -e .`

Plus pre-existing mitigations (kept unchanged):
- `packages/desktop/requirements.txt` already pinned (`numpy>=1.24.0,<2.0.0`)
- `packages/desktop/build_executable.spec` — `strip=False`, `upx=False`, runtime hook wired in
- `packages/desktop/hook_numpy_openblas.py` — pre-loads OpenBLAS, sets `OPENBLAS_NUM_THREADS`
- `.github/workflows/release.yml` — explicit `pip install "numpy>=1.24.0,<2.0.0"` before scanner_fixer install
- `scripts/rebuild-appimage.sh` — one-command rebuild with numpy downgrade

**Verification:**
`pip install --dry-run -e packages/scanner_fixer` now resolves to `numpy-1.26.4` (was 2.x).

**Upgrade path:**
Users on v1.1.0/v1.1.1 should upgrade to v1.2.0 once tagged. As a workaround on v1.1.0/v1.1.1, run `scripts/rebuild-appimage.sh` locally.

---

## Open

### 2. systemd --user in containers

Falls back to manual process launch; full systemd lifecycle must be verified on native Manjaro/Arch with DBUS and XDG_RUNTIME_DIR properly configured.

### 3. AppImage on Wayland

May need `QT_QPA_PLATFORM=wayland;xcb` for fallback on KDE Plasma 6. Set `OMNI_APPIMAGE_OFFSCREEN=1` for headless/CI environments.

### 4. Git LFS migration rewrites history

`git lfs migrate import` rewrites history — coordinate with all contributors before running on shared repositories.

### 5. rc-gate.yml mobile-smoke job

May fail in CI if the mobile server module path is not correctly configured for the test environment. `PYTHONPATH` must include the repository root.

### 6. ~50 legacy requirements*.txt files

Gradually being migrated to `pyproject.toml` extras. See `docs/DEPENDENCY_STRATEGY.md`.

---

## Reporting new issues

Open a GitHub issue at <https://github.com/DrAbdulmalek/omni-medical-suite/issues> with:
- Affected version (tag or commit)
- OS + kernel version (`uname -a`)
- Reproduction steps
- Error output (full traceback for crashes)
