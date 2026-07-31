#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# bulk-lfs-convert.sh — Convert large files (>1MB) to LFS pointers
# ══════════════════════════════════════════════════════════════════════
# This script finds all files > 1MB currently stored as regular git
# objects and converts them to LFS pointers by removing from the index
# and re-adding (the .gitattributes LFS filter handles the conversion).
#
# Usage:
#   bash scripts/bulk-lfs-convert.sh           # Convert all
#   bash scripts/bulk-lfs-convert.sh --dry-run # Preview only
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

echo "============================================================"
echo "  Bulk LFS Conversion"
echo "  Dry run: ${DRY_RUN}"
echo "============================================================"

# Find files > 1MB
LARGE_FILES=()
while IFS= read -r line; do
    if [ -n "$line" ]; then
        LARGE_FILES+=("$line")
    fi
done < <(find . -type f -size +1M -not -path './.git/*' -printf '%P\n' 2>/dev/null | sort)

# Get currently tracked LFS files
LFS_FILES=$(git lfs ls-files 2>/dev/null | awk '{print $NF}' || true)

CONVERTED=0
SKIPPED=0
TOTAL_SIZE=0

for f in "${LARGE_FILES[@]}"; do
    # Check if already LFS-tracked
    BASENAME=$(basename "$f")
    if echo "$LFS_FILES" | grep -qF "$f" || echo "$LFS_FILES" | grep -qF "$BASENAME"; then
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    SIZE=$(stat -c%s "$f" 2>/dev/null || echo "0")
    SIZE_MB=$((SIZE / 1024 / 1024))
    TOTAL_SIZE=$((TOTAL_SIZE + SIZE))

    if $DRY_RUN; then
        echo "  WOULD CONVERT: $f (${SIZE_MB} MB)"
        CONVERTED=$((CONVERTED + 1))
        continue
    fi

    echo -n "  Converting: $f (${SIZE_MB} MB)... "

    # Remove from index (keep working tree)
    if ! git rm --cached "$f" >/dev/null 2>&1; then
        echo "SKIP (git rm failed)"
        continue
    fi

    # Re-add with LFS filter
    if ! git add -f "$f" >/dev/null 2>&1; then
        echo "SKIP (git add failed)"
        continue
    fi

    # Verify pointer
    DIFF_STAT=$(git diff --cached --stat "$f" 2>/dev/null || true)
    if echo "$DIFF_STAT" | grep -q "133 bytes\|132 bytes\|134 bytes"; then
        echo "✅"
        CONVERTED=$((CONVERTED + 1))
    else
        echo "⚠️  (may not be pointer)"
        CONVERTED=$((CONVERTED + 1))
    fi
done

TOTAL_MB=$((TOTAL_SIZE / 1024 / 1024))

echo ""
echo "============================================================"
echo "  Converted: ${CONVERTED}"
echo "  Skipped (already LFS): ${SKIPPED}"
echo "  Total converted size: ${TOTAL_MB} MB"
echo "============================================================"

if [ $CONVERTED -gt 0 ] && ! $DRY_RUN; then
    echo ""
    echo "Next: git commit -m 'chore(lfs): convert ${CONVERTED} large files to LFS pointers'"
fi
