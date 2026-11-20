#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# rebuild-appimage.sh — Rebuild AppImage with numpy<2 fix
# ══════════════════════════════════════════════════════════════════════
# Fixes the "libscipy_openblas64_ ELF load command address/offset
# not page-aligned" crash by downgrading numpy to 1.26.x before
# building the PyInstaller bundle.
#
# This is the CRITICAL fix for the v1.1.0 AppImage crash.
#
# Usage on Manjaro/Ubuntu:
#   cd ~/GitHub/omni-medical-suite/packages/desktop
#   bash ../../scripts/rebuild-appimage.sh
#
# Or from repo root:
#   bash scripts/rebuild-appimage.sh
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP_DIR="$REPO_ROOT/packages/desktop"

echo "═══════════════════════════════════════════════════"
echo "  Rebuild AppImage with numpy<2 fix"
echo "═══════════════════════════════════════════════════"

# ── 1. Check current numpy version ───────────────────────────────────
echo ""
echo "📦 Current numpy version:"
python3 -c "import numpy; print(f'   numpy {numpy.__version__}')" 2>/dev/null || echo "   numpy not installed"

# ── 2. Downgrade numpy ──────────────────────────────────────────────
echo ""
echo "⬇️  Installing numpy<2 (fixes ELF alignment crash)..."
pip install --upgrade 'numpy>=1.24.0,<2.0.0' 2>&1 | tail -3

# Verify
NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "0.0.0")
NUMPY_MAJOR=$(echo "$NUMPY_VERSION" | cut -d. -f1)
if [ "$NUMPY_MAJOR" -ge 2 ]; then
    echo "❌ numpy still at $NUMPY_VERSION — downgrade failed"
    echo "   Try: pip install --force-reinstall 'numpy==1.26.4'"
    exit 1
fi
echo "✅ numpy $NUMPY_VERSION installed"

# ── 3. Reinstall opencv to match numpy version ──────────────────────
echo ""
echo "📦 Reinstalling opencv-python-headless (compatible with numpy $NUMPY_VERSION)..."
pip install --force-reinstall opencv-python-headless 2>&1 | tail -3

# ── 4. Build ─────────────────────────────────────────────────────────
echo ""
echo "🔨 Building AppImage..."
cd "$DESKTOP_DIR"

# Clean previous builds
rm -rf build/ dist/ AppDir/

# Build PyInstaller executable first
bash build.sh

# Then build AppImage
bash build_appimage.sh --version-from-git --smoke-test

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ AppImage rebuilt with numpy<2 fix!"
echo ""
echo "  Test it:"
echo "    cd $DESKTOP_DIR"
echo "    chmod +x MedicalDocProcessor-*.AppImage"
echo "    ./MedicalDocProcessor-*.AppImage"
echo ""
echo "  If it still crashes, run:"
echo "    OMNI_APPIMAGE_OFFSCREEN=1 ./MedicalDocProcessor-*.AppImage"
echo "═══════════════════════════════════════════════════"
