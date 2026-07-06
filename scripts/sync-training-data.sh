#!/bin/bash
# Sync training data to a separate branch for GitHub protected access
# Usage: bash scripts/sync-training-data.sh

set -e

cd /home/z/my-project

echo "=== Training Data Sync Script ==="
echo "This script exports training data and syncs it to a separate Git branch."

# Step 1: Call the export API to generate fresh data
echo "[1/3] Generating training data export..."
EXPORT_RESPONSE=$(curl -s -X POST http://localhost:3000/api/export-training 2>/dev/null || echo '{}')
echo "Export response: $EXPORT_RESPONSE"

# Step 2: Check if training-data directory has content
if [ ! -d "training-data" ] || [ -z "$(ls -A training-data 2>/dev/null)" ]; then
    echo "[2/3] No training data found in training-data/ directory."
    echo "      Please export training data from the UI first."
    exit 0
fi

COUNT=$(ls -1 training-data/*.jsonl 2>/dev/null | wc -l)
echo "[2/3] Found $COUNT export file(s) in training-data/"

# Step 3: Git operations
echo "[3/3] Git operations..."
# Ensure training-data is not ignored
if grep -q "^/training-data" .gitignore 2>/dev/null; then
    echo "      Removing training-data from .gitignore..."
    sed -i '/^\/training-data/d' .gitignore
fi

# Stage and commit on current branch
git add training-data/ .gitignore 2>/dev/null || true
if git diff --cached --quiet; then
    echo "      No changes to commit."
else
    git commit -m "Update training data $(date +%Y-%m-%d_%H:%M)" 2>/dev/null || true
    echo "      Changes committed."
fi

echo ""
echo "=== Sync Complete ==="
echo "Training data is now tracked in git."
echo "To push to a protected branch, use:"
echo "  git push origin HEAD:refs/heads/training-data"
echo ""
echo "To set up a protected branch on GitHub:"
echo "  1. Go to repo Settings > Branches"
echo "  2. Add branch protection rule for 'training-data'"
echo "  3. Require pull request reviews and status checks"
