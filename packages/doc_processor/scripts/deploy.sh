#!/usr/bin/env bash
# deploy.sh — Deploy the Medical Doc Suite
set -e

echo "🚀 Deploying Medical Doc Suite..."
echo "================================="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# ── Step 1: Build ──
echo ""
echo "📦 Step 1: Building..."
bash scripts/build-all.sh

# ── Step 2: Run Tests ──
echo ""
echo "🧪 Step 2: Running tests..."
bash scripts/test-all.sh

# ── Step 3: Git Status ──
echo ""
echo "📊 Step 3: Git status..."
git status --short

echo ""
echo "================================="
echo "🎉 Deploy preparation complete!"
echo ""
echo "Next steps:"
echo "  git add -A"
echo "  git commit -m 'release: vX.Y.Z'"
echo "  git push origin main"
