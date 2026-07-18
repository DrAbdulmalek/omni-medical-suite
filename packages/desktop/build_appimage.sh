#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# build_appimage.sh — Build medical-doc-processor as an AppImage
# ══════════════════════════════════════════════════════════════════
#
# Target: Linux (Manjaro/KDE Plasma) — AppImage (portable, no install)
#
# Requirements:
#   - Python 3.10+
#   - AppImageTool (wget from GitHub or: yay -S appimagetool)
#   - All dependencies from requirements.txt installed
#   - scanner_fixer package installed (pip install -e ../scanner_fixer)
#
# Usage:
#   cd packages/desktop
#   bash build_appimage.sh
#
# Output:
#   MedicalDocProcessor-x86_64.AppImage
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="MedicalDocProcessor"
APPDIR="${SCRIPT_DIR}/AppDir"
VERSION="${1:-1.0.0}"

echo "═══════════════════════════════════════════════════"
echo "  Building ${APP_NAME} AppImage v${VERSION}        "
echo "═══════════════════════════════════════════════════"

# ── 1. Check dependencies ─────────────────────────────────────────
echo ""
echo "📦 Checking dependencies..."

for cmd in python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "❌ $cmd not found."
        exit 1
    fi
done

python3 -c "import PySide6" 2>/dev/null || { echo "❌ PySide6 not found. Install: pip install PySide6"; exit 1; }
python3 -c "import cv2" 2>/dev/null || { echo "❌ OpenCV not found. Install: pip install opencv-python-headless"; exit 1; }
python3 -c "import scanner_fixer" 2>/dev/null || { echo "❌ scanner_fixer not found. Install: pip install -e ../scanner_fixer"; exit 1; }

echo "✅ All dependencies available"

# ── 2. Build PyInstaller onefile first ─────────────────────────────
echo ""
echo "🔨 Building PyInstaller onefile..."
cd "$SCRIPT_DIR"
bash build.sh

# ── 3. Create AppDir structure ────────────────────────────────────
echo ""
echo "📁 Creating AppDir structure..."
rm -rf "$APPDIR"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${APPDIR}/usr/share/metainfo"

# Copy the PyInstaller executable
cp dist/medical-doc-processor "${APPDIR}/usr/bin/"

# ── 4. Create AppStream metadata ──────────────────────────────────
cat > "${APPDIR}/usr/share/metainfo/${APP_NAME}.metainfo.xml" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>com.omnimedical.docprocessor</id>
  <name>Medical Document Processor</name>
  <summary>معالج الوثائق الطبية التفاعلي — Interactive medical document processor</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <description>
    <p>Pre-OCR image normalization and medical document processing suite.
    Features deskew, auto-crop, normalization, dedup detection, and OCR.</p>
  </description>
  <launchable type="desktop-id">com.omnimedical.docprocessor.desktop</launchable>
  <releases>
    <release version="1.0.0" date="2025-01-01"/>
  </releases>
</component>
EOF

# ── 5. Create .desktop file ───────────────────────────────────────
cat > "${APPDIR}/usr/share/applications/com.omnimedical.docprocessor.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Medical Document Processor
Name[ar]=معالج الوثائق الطبية
Comment=Interactive medical document processing and OCR
Comment[ar]=معالجة تفاعلية للوثائق الطبية والتعرف البصري
Exec=medical-doc-processor
Icon=com.omnimedical.docprocessor
Terminal=false
Categories=Office;Graphics;Scanning;MedicalSoftware;
Keywords=OCR;medical;scanner;document;Arabic;
StartupWMClass=medical-doc-processor
EOF

# ── 6. Create a simple icon (SVG → PNG) ──────────────────────────
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (30, 64, 175, 255))
draw = ImageDraw.Draw(img)
# Simple medical cross icon
draw.rectangle([98, 40, 158, 216], fill='white')
draw.rectangle([40, 98, 216, 158], fill='white')
img.save('${APPDIR}/usr/share/icons/hicolor/256x256/apps/com.omnimedical.docprocessor.png')
" 2>/dev/null || {
    # Fallback: create a 1x1 placeholder
    cp /usr/share/icons/hicolor/256x256/apps/*.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/com.omnimedical.docprocessor.png" 2>/dev/null || true
}

# ── 7. Create AppRun ─────────────────────────────────────────────
cat > "${APPDIR}/AppRun" << 'APP_RUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
# Set Qt platform for Wayland/X11
export QT_QPA_PLATFORMTHEME=kvantum
exec "${HERE}/usr/bin/medical-doc-processor" "$@"
APP_RUN
chmod +x "${APPDIR}/AppRun"

# ── 8. Download appimagetool if needed ────────────────────────────
echo ""
echo "🔧 Looking for appimagetool..."
if ! command -v appimagetool &>/dev/null; then
    echo "📥 Downloading appimagetool..."
    ARCH=$(uname -m)
    APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    wget -q -O /tmp/appimagetool "${APPIMAGETOOL_URL}" || curl -sL -o /tmp/appimagetool "${APPIMAGETOOL_URL}"
    chmod +x /tmp/appimagetool
    APPIMAGETOOL_CMD="/tmp/appimagetool"
else
    APPIMAGETOOL_CMD="appimagetool"
fi

# ── 9. Build AppImage ─────────────────────────────────────────────
echo ""
echo "📦 Building AppImage..."
OUTPUT_NAME="${APP_NAME}-${VERSION}-$(uname -m).AppImage"

cd "$SCRIPT_DIR"
"$APPIMAGETOOL_CMD" "$APPDIR" "$OUTPUT_NAME" 2>&1 || {
    echo ""
    echo "⚠️  appimagetool failed. You can still use the PyInstaller executable:"
    echo "   ./dist/medical-doc-processor"
    echo ""
    echo "Alternatively, to create an AppImage manually:"
    echo "   1. Install appimagetool: yay -S appimagetool"
    echo "   2. Run: appimagetool AppDir/ ${OUTPUT_NAME}"
    exit 1
}

# ── 10. Done! ─────────────────────────────────────────────────────
echo ""
echo "✅ AppImage built successfully!"
echo ""
echo "   File:     ${OUTPUT_NAME}"
echo "   Size:     $(du -h "${OUTPUT_NAME}" | cut -f1)"
echo ""
echo "   Run with: chmod +x ${OUTPUT_NAME} && ./${OUTPUT_NAME}"
echo ""
echo "   Install system-wide (optional):"
echo "   sudo mv ${OUTPUT_NAME} /usr/local/bin/medical-doc-processor.AppImage"
