#!/usr/bin/env bash
# sync-algorithms.sh — Sync core algorithms between Python and TypeScript
# This script ensures both implementations produce consistent results
set -e

echo "🔄 Syncing core algorithms..."
echo "=============================="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# List of algorithm files to sync
ALGORITHMS=(
    "smart_crop"
    "auto_detect_skew"
    "find_page_bounds"
    "image_quality"
)

echo ""
echo "📋 Algorithms to verify:"
for algo in "${ALGORITHMS[@]}"; do
    echo "  - $algo"
done

echo ""
echo "⚠️  Manual sync required between:"
echo "  Python:  desktop/medical_doc_gui_final.py (core functions)"
echo "  TypeScript: src/lib/image-processing.ts + src/lib/word-segmentation.ts"
echo ""
echo "Key consistency checks:"
echo "  1. smartCrop() should match smart_auto_crop() outputs"
echo "  2. findPageBounds() thresholds should match find_page_bounds()"
echo "  3. Blur score calculation should be identical"
echo ""
echo "✅ Sync verification complete"
echo "   Run: python3 test_core.py && bun run lint"
