#!/bin/bash
set -e

echo "=== OmniMedix Integration Script ==="

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# 1. Create new package directories
mkdir -p packages/{core-ocr,medical-nlp,data-extractor,trainer,shared}
mkdir -p apps/{desktop,mobile}
mkdir -p legacy

echo "Directory structure created."

# 2. Run deduplication (dry-run first)
if [ -f "scripts/deduplicate_packages.py" ]; then
    echo ""
    echo "Running deduplication (dry-run)..."
    python scripts/deduplicate_packages.py --dry-run
    echo ""
    echo "To apply: python scripts/deduplicate_packages.py --apply"
else
    echo "WARNING: scripts/deduplicate_packages.py not found"
fi

# 3. Verify structure
echo ""
echo "=== Current packages/ structure ==="
ls packages/ 2>/dev/null

echo ""
echo "Done. Review the output and apply deduplication when ready."
