# AppImage — Manjaro Build Guide

This document walks through building the **Medical Document Processor** AppImage on **Manjaro Linux (KDE Plasma)**. The same steps work on Arch Linux, with minor adaptations for Ubuntu/Fedora noted at the end.

> **TL;DR** — `cd packages/desktop && bash build_appimage.sh --version-from-git --smoke-test`

---

## 1. Prerequisites (Manjaro)

### 1.1 System packages (pacman)

```bash
sudo pacman -Syu --needed \
    python python-pip \
    tesseract tesseract-data-eng tesseract-data-ara \
    poppler \
    qt6-base qt6-imageformats \
    cairo pango gdk-pixbuf2 \
    libfuse2
```

Notes:
- `libfuse2` is required by AppImage runtime (otherwise AppImages won't mount).
- `tesseract-data-ara` provides Arabic OCR.
- `poppler` provides `pdf2image` rendering for PDF inputs.

### 1.2 appimagetool

Two options:

**Option A — AUR (recommended):**
```bash
yay -S appimagetool
```

**Option B — Auto-download (build script handles this):**
The `build_appimage.sh` script auto-downloads `appimagetool-x86_64.AppImage` from GitHub releases if `appimagetool` is not on `$PATH`. The downloaded binary lands at `/tmp/appimagetool`.

### 1.3 Python dependencies

```bash
# System-wide (or use a venv)
python -m venv ~/venvs/omni
source ~/venvs/omni/bin/activate

# Install scanner_fixer (editable) + desktop deps
cd packages/scanner_fixer && pip install -e . && cd ../..
cd packages/desktop && pip install -r requirements.txt
pip install pyinstaller
```

Verify:
```bash
python -c "import PySide6, cv2, scanner_fixer; print('OK')"
```

---

## 2. Build the AppImage

```bash
cd packages/desktop

# Option 1: explicit version
bash build_appimage.sh 1.1.0-rc1

# Option 2: derive version from git tags
bash build_appimage.sh --version-from-git

# Option 3: full pipeline with smoke test
bash build_appimage.sh --version-from-git --smoke-test
```

### 2.1 What the script does

| Step | Action |
|------|--------|
| 1 | Detect distro (Manjaro/Arch/Debian/Fedora) |
| 2 | Verify PySide6, cv2, scanner_fixer, PyInstaller |
| 3 | Run `build.sh` → `dist/medical-doc-processor` (PyInstaller onefile ELF) |
| 4 | Stage `AppDir/` with binary, .desktop, icon, metainfo.xml |
| 5 | Generate AppRun launcher (Qt platform abstraction) |
| 6 | Acquire `appimagetool` (system or auto-download) |
| 7 | Pack `AppDir/` → `MedicalDocProcessor-<ver>-x86_64.AppImage` |
| 8 | Generate `<name>.AppImage.sha256` checksum |
| 9 | (Optional) Smoke-test the AppImage with `OMNI_APPIMAGE_OFFSCREEN=1` |

### 2.2 Output artifacts

```
packages/desktop/
├── MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage       (~250-400 MB)
├── MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage.sha256
├── dist/
│   └── medical-doc-processor                            (PyInstaller ELF, intermediate)
└── AppDir/                                              (staged tree, intermediate)
```

---

## 3. Running on Manjaro / KDE Plasma 6

### 3.1 Direct execution

```bash
chmod +x MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage
./MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage
```

### 3.2 Wayland notes (KDE Plasma 6)

KDE Plasma 6 on Manjaro defaults to Wayland. The AppRun launcher auto-detects `WAYLAND_DISPLAY` and sets `QT_QPA_PLATFORM=wayland`. If you hit rendering glitches, force X11:

```bash
QT_QPA_PLATFORM=xcb ./MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage
```

### 3.3 Headless / CI mode

For automated testing without a display:

```bash
OMNI_APPIMAGE_OFFSCREEN=1 ./MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage --version
```

### 3.4 System-wide install

```bash
sudo mv MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage /usr/local/bin/medical-doc-processor.AppImage
sudo mv MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage.sha256 /usr/local/bin/
sudo chmod +x /usr/local/bin/medical-doc-processor.AppImage

# Verify checksum
sha256sum -c /usr/local/bin/medical-doc-processor.AppImage.sha256

# Optional: create a desktop entry (so it shows in KDE menu)
sudo tee /usr/share/applications/medical-doc-processor.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Medical Document Processor
Exec=/usr/local/bin/medical-doc-processor.AppImage
Icon=medical-doc-processor
Terminal=false
Categories=Office;Graphics;Scanning;MedicalSoftware;
EOF
```

---

## 4. Verify integrity

```bash
# Confirm checksum matches
sha256sum -c MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage.sha256

# Inspect AppDir contents
./MedicalDocProcessor-1.1.0-rc1-x86_64.AppImage --appimage-extract
ls squashfs-root/
```

---

## 5. Troubleshooting

### 5.1 `appimagetool: error while loading shared libraries: libfuse2.so`

Manjaro fix:
```bash
sudo pacman -S libfuse2
```

### 5.2 `Qt: could not connect to display`

You're running without X/Wayland. Either log into KDE Plasma or use:
```bash
OMNI_APPIMAGE_OFFSCREEN=1 ./MedicalDocProcessor-*.AppImage
```

### 5.3 PyInstaller: `ModuleNotFoundError: No module named 'scanner_fixer.*'`

Reinstall scanner_fixer editable:
```bash
cd packages/scanner_fixer && pip install -e .
```

### 5.4 Arabic OCR not working

Install Arabic tesseract data:
```bash
sudo pacman -S tesseract-data-ara
```

Verify:
```bash
tesseract --list-langs | grep ara
```

### 5.5 AppImage too large (>500 MB)

The PyInstaller onefile bundles Python + Qt + OpenCV. To shrink:
1. Use `--onefile` (already default) instead of `--onedir`.
2. Strip debug symbols: `strip dist/medical-doc-processor`.
3. Consider UPX compression (adds startup cost): `upx --best dist/medical-doc-processor`.

---

## 6. Other distros

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
    tesseract-ocr tesseract-ocr-ara poppler-utils \
    libfuse2 qt6-base-dev

# appimagetool: download from GitHub releases
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool
```

Then run `bash build_appimage.sh` as above.

### Fedora

```bash
sudo dnf install -y python3 python3-pip \
    tesseract tesseract-langpack-ara poppler-utils \
    fuse fuse-libs qt6-qtbase

# appimagetool via direct download (same as Ubuntu)
```

---

## 7. CI verification

The GitHub Actions workflow at `.github/workflows/appimage-build.yml` builds the AppImage on every push to `feat/rc-hardening-p0` and on tags matching `v*`. It runs the smoke test in offscreen mode and uploads the AppImage + checksum as an artifact.

Download artifacts from: **Actions tab → latest run → appimage-artifacts**

---

## 8. Release checklist (for maintainers)

- [ ] Bump version in `RELEASE_CANDIDATE_CHECKLIST.md`
- [ ] Tag the release: `git tag -a v1.1.0-rc1 -m "v1.1.0-rc1"`
- [ ] Push tag: `git push origin v1.1.0-rc1`
- [ ] Wait for `appimage-build.yml` to complete
- [ ] Download the AppImage artifact
- [ ] Run smoke test on Manjaro: `bash build_appimage.sh --smoke-test`
- [ ] Create GitHub Release with AppImage + checksum attached
- [ ] Update `RELEASE_NOTES_v1.1.0-rc1.md` with download links
