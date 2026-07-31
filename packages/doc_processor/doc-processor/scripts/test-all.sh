#!/usr/bin/env bash
# test-all.sh — Run all tests across the monorepo
set -e

echo "🧪 Running Medical Doc Suite Tests..."
echo "======================================="

FAILED=0

# ── Python Tests ──
echo ""
echo "🐍 [1/2] Running Python tests..."
cd "$(dirname "$0")/.." || exit 1

if command -v python3 &>/dev/null && python3 -c "import pytest" 2>/dev/null; then
    if python3 -m pytest test_core.py -v --tb=short 2>&1; then
        echo "✅ Python tests passed"
    else
        echo "❌ Python tests failed"
        FAILED=1
    fi
else
    echo "⚠️  Skipping Python tests (pytest not installed)"
    echo "   Install: pip install pytest numpy opencv-python-headless"
fi

# ── TypeScript Lint ──
echo ""
echo "📐 [2/2] Running TypeScript lint..."
if command -v bun &>/dev/null; then
    if bun run lint 2>&1; then
        echo "✅ TypeScript lint passed"
    else
        echo "❌ TypeScript lint failed"
        FAILED=1
    fi
else
    echo "⚠️  Skipping TypeScript lint (bun not found)"
fi

echo ""
echo "======================================="
if [ "$FAILED" -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed!"
    exit 1
fi
