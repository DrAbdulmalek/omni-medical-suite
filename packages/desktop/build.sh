#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# build.sh — Build medical-doc-processor as a single ELF executable
# ══════════════════════════════════════════════════════════════════
#
# Target: Linux (Manjaro/KDE Plasma) — ELF 64-bit executable
#
# Requirements:
#   - Python 3.10+
#   - PyInstaller (pip install pyinstaller)
#   - All dependencies from requirements.txt installed
#   - scanner_fixer package installed (pip install -e ../scanner_fixer)
#
# Usage:
#   cd packages/desktop
#   bash build.sh
#
# Output:
#   dist/medical-doc-processor  (single ELF executable, ~150-300MB)
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════════════"
echo "  Building medical-doc-processor (Linux ELF)      "
echo "═══════════════════════════════════════════════════"

# ── 1. Check dependencies ─────────────────────────────────────────
echo ""
echo "📦 Checking dependencies..."

if ! python3 -c "import PySide6" 2>/dev/null; then
    echo "❌ PySide6 not found. Install: pip install PySide6"
    exit 1
fi

if ! python3 -c "import cv2" 2>/dev/null; then
    echo "❌ OpenCV not found. Install: pip install opencv-python-headless"
    exit 1
fi

if ! python3 -c "import scanner_fixer" 2>/dev/null; then
    echo "❌ scanner_fixer not found. Install: pip install -e ../scanner_fixer"
    exit 1
fi

if ! command -v pyinstaller &>/dev/null && ! python3 -m PyInstaller --version &>/dev/null; then
    echo "❌ PyInstaller not found. Install: pip install pyinstaller"
    exit 1
fi

echo "✅ All dependencies available"

# ── 2. Clean previous builds ───────────────────────────────────────
echo ""
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/

# ── 3. Build ───────────────────────────────────────────────────────
echo ""
echo "🔨 Building executable (this may take a few minutes)..."
pyinstaller build_executable.spec --clean --noconfirm

# ── 4. Verify ──────────────────────────────────────────────────────
echo ""
if [ -f "dist/medical-doc-processor" ]; then
    SIZE=$(du -h dist/medical-doc-processor | cut -f1)
    TYPE=$(file dist/medical-doc-processor | head -1)
    echo "✅ Build successful!"
    echo ""
    echo "   File:     dist/medical-doc-processor"
    echo "   Size:     $SIZE"
    echo "   Type:     $TYPE"
    echo ""
    echo "   Run with: ./dist/medical-doc-processor"
    echo ""
    echo "⚠️  Note: On first run, it may take a few seconds to extract"
    echo "   temporary files. This is normal for --onefile executables."
else
    echo "❌ Build failed! Check the output above for errors."
    exit 1
fi
