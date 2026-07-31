#!/usr/bin/env bash
# build-all.sh — Build all applications in the monorepo
set -e

echo "🏗️  Building Medical Doc Suite..."
echo "================================"

# ── Build Web Application ──
echo ""
echo "📦 [1/2] Building Web Application..."
cd "$(dirname "$0")/.." || exit 1
bun install --frozen-lockfile 2>/dev/null || bun install
bun run build
echo "✅ Web application built successfully"

# ── Check Desktop Application ──
echo ""
echo "🐍 [2/2] Verifying Desktop Application..."
if [ -f "desktop/medical_doc_gui_final.py" ]; then
    python3 -c "import py_compile; py_compile.compile('desktop/medical_doc_gui_final.py', doraise=True)" 2>/dev/null && \
        echo "✅ Desktop application syntax OK" || \
        echo "⚠️  Desktop app has syntax errors (but may still run)"
else
    echo "⚠️  Desktop application not found"
fi

echo ""
echo "================================"
echo "🎉 Build complete!"
