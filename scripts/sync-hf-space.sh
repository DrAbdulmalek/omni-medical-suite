#!/usr/bin/env bash
# =============================================================================
# sync-hf-space.sh — Sync shared source files into hf-space/ deployment snapshot
# =============================================================================
# Usage: ./scripts/sync-hf-space.sh
#
# This script copies the latest versions of shared modules from the monorepo
# into hf-space/ so the HF Space deployment always reflects the current code.
#
# Files synced:
#   src/ocr/          → hf-space/src/ocr/        (normalization, ensemble, engines)
#   packages/vision/  → hf-space/packages/vision/  (text_reconstructor, preprocessor)
#   packages/nlp/     → hf-space/packages/nlp/     (arabic_rtl, arabic_nlp_utils)
#   packages/core/    → hf-space/packages/core/    (engine_registry, engine_router)
#   config/           → hf-space/config/           (config files)
#
# Files NOT synced (HF-specific overrides):
#   hf-space/app.py          — standalone Gradio app for HF deployment
#   hf-space/Dockerfile      — HF-optimized Docker build
#   hf-space/requirements.txt — HF-specific dependency list
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HF_DIR="$ROOT_DIR/hf-space"

echo "=== Syncing monorepo → hf-space/ ==="

# Define sync mappings: SOURCE_DIR HF_SUBDIR
SYNC_MAP=(
  "src/ocr:src/ocr"
  "packages/vision:packages/vision"
  "packages/nlp:packages/nlp"
  "packages/core:packages/core"
  "config:config"
)

CHANGED=0
COPIED=0

for entry in "${SYNC_MAP[@]}"; do
  IFS=':' read -r src_sub hf_sub <<< "$entry"
  src_dir="$ROOT_DIR/$src_sub"
  hf_sub_dir="$HF_DIR/$hf_sub"

  if [ ! -d "$src_dir" ]; then
    echo "  SKIP: $src_dir (not found)"
    continue
  fi

  mkdir -p "$hf_sub_dir"

  # Use rsync if available, otherwise cp -r
  if command -v rsync &>/dev/null; then
    result=$(rsync -av --delete --exclude='__pycache__' --exclude='*.pyc' \
      "$src_dir/" "$hf_sub_dir/" 2>&1)
  else
    rm -rf "$hf_sub_dir"/*
    cp -r "$src_dir"/* "$hf_sub_dir/"
    result="copied recursively"
  fi

  file_count=$(find "$hf_sub_dir" -name '*.py' -type f 2>/dev/null | wc -l)
  echo "  SYNCED: $src_sub → hf-space/$hf_sub ($file_count .py files)"
  COPIED=$((COPIED + file_count))
  CHANGED=$((CHANGED + 1))
done

echo ""
echo "=== Sync Summary ==="
echo "  Directories synced: $CHANGED"
echo "  Total .py files:    $COPIED"
echo ""
echo "NOTE: hf-space/app.py, Dockerfile, requirements.txt are HF-specific"
echo "      and NOT overwritten by this sync."
echo ""
echo "Next: git add hf-space/ && git commit && git push"