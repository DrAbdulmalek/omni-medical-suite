#!/usr/bin/env bash
# =============================================================================
# sync-hf-space.sh — Sync monorepo → hf-space/ deployment snapshot
# =============================================================================
# Source of truth:
#   app/gradio_full_hitl.py  — official Gradio HITL app
#   app/services/*           — service layer (lazy-loaded)
#   packages/*               — shared subpackages (scanner_fixer, observability, core, ...)
#   src/ocr/*                — OCR + RTL + field extraction
#
# Deployment snapshot (read-only by convention):
#   hf-space/app.py          — HF Space entrypoint (frozen, NOT auto-overwritten)
#   hf-space/Dockerfile      — HF-optimized Docker build
#   hf-space/requirements.txt — HF-specific deps
#
# Synced paths (source → snapshot):
#   src/ocr/             → hf-space/src/ocr/
#   packages/vision/     → hf-space/packages/vision/
#   packages/nlp/        → hf-space/packages/nlp/
#   packages/core/       → hf-space/packages/core/
#   packages/medical/     → hf-space/packages/medical/   (PR #92: dictionary registry + router)
#   config/              → hf-space/config/
#
# Modes:
#   ./scripts/sync-hf-space.sh             # default: sync + verify
#   ./scripts/sync-hf-space.sh --verify    # verify-only, no copy
#   ./scripts/sync-hf-space.sh --force     # sync without confirmation
#
# Exit codes:
#   0 — success (or verify-only with no drift)
#   1 — configuration error (missing dirs)
#   2 — drift detected in --verify mode
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HF_DIR="$ROOT_DIR/hf-space"

MODE="sync"
if [[ "${1:-}" == "--verify" ]]; then
  MODE="verify"
elif [[ "${1:-}" == "--force" ]]; then
  MODE="force"
fi

echo "=== sync-hf-space.sh (mode: $MODE) ==="
echo "Repo: $ROOT_DIR"
echo ""

# --- Sanity ------------------------------------------------------------------
if [[ ! -d "$HF_DIR" ]]; then
  echo "ERROR: hf-space/ not found at $HF_DIR" >&2
  exit 1
fi

# --- Sync mapping ------------------------------------------------------------
SYNC_MAP=(
  "src/ocr:src/ocr"
  "packages/vision:packages/vision"
  "packages/nlp:packages/nlp"
  "packages/core:packages/core"
  "packages/medical:packages/medical"
  "config:config"
)

# --- Functions ---------------------------------------------------------------
count_py() {
  find "$1" -name '*.py' -type f 2>/dev/null | wc -l
}

verify_dir() {
  local src="$1" dst="$2"
  if [[ ! -d "$src" ]]; then
    echo "  SKIP: $src (not found)"
    return 0
  fi
  if [[ ! -d "$dst" ]]; then
    echo "  DRIFT: $dst missing (would be created by sync)"
    return 2
  fi
  local diff_out
  diff_out=$(diff -rq --exclude='__pycache__' --exclude='*.pyc' "$src" "$dst" 2>&1 || true)
  if [[ -z "$diff_out" ]]; then
    echo "  OK: $src ↔ $dst (in sync)"
    return 0
  else
    echo "  DRIFT: $src vs $dst"
    echo "$diff_out" | head -10 | sed 's/^/    /'
    return 2
  fi
}

sync_dir() {
  local src="$1" dst="$2"
  if [[ ! -d "$src" ]]; then
    echo "  SKIP: $src (not found)"
    return 0
  fi
  mkdir -p "$dst"
  if command -v rsync &>/dev/null; then
    rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' \
      "$src/" "$dst/" >/dev/null 2>&1
  else
    rm -rf "$dst"/*
    cp -r "$src"/* "$dst/" 2>/dev/null || true
  fi
  local n
  n=$(count_py "$dst")
  echo "  SYNCED: $src → $dst ($n .py files)"
}

# --- Main --------------------------------------------------------------------
DRIFT=0

if [[ "$MODE" == "verify" ]]; then
  echo "--- Verify-only mode: checking drift ---"
  for entry in "${SYNC_MAP[@]}"; do
    IFS=':' read -r src_sub hf_sub <<< "$entry"
    verify_dir "$ROOT_DIR/$src_sub" "$HF_DIR/$hf_sub" || DRIFT=1
  done
  if [[ "$DRIFT" -ne 0 ]]; then
    echo ""
    echo "❌ Drift detected. Run: ./scripts/sync-hf-space.sh"
    exit 2
  fi
  echo ""
  echo "✅ hf-space/ is in sync with monorepo sources."
  exit 0
fi

# sync or force mode
echo "--- Syncing monorepo → hf-space/ ---"
for entry in "${SYNC_MAP[@]}"; do
  IFS=':' read -r src_sub hf_sub <<< "$entry"
  sync_dir "$ROOT_DIR/$src_sub" "$HF_DIR/$hf_sub"
done

echo ""
echo "--- Post-sync verification ---"
for entry in "${SYNC_MAP[@]}"; do
  IFS=':' read -r src_sub hf_sub <<< "$entry"
  verify_dir "$ROOT_DIR/$src_sub" "$HF_DIR/$hf_sub" || DRIFT=1
done

echo ""
echo "=== Summary ==="
echo "  Directories synced: ${#SYNC_MAP[@]}"
if [[ "$DRIFT" -ne 0 ]]; then
  echo "  ⚠️  Post-sync drift detected (probably __pycache__ leftover). Re-run --verify."
  exit 2
fi
echo "  ✅ All synced paths verified clean."
echo ""
echo "NOTE: hf-space/app.py, Dockerfile, requirements.txt are HF-specific"
echo "      and NOT overwritten by this sync."
echo ""
echo "Next: git add hf-space/ && git commit -m 'chore(hf-space): sync from monorepo'"
