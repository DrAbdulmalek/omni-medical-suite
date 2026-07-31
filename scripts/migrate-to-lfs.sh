#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# migrate-to-lfs.sh — One-time Git LFS migration for omni-medical-suite
# ═══════════════════════════════════════════════════════════════════════════
# Transitions all matching binary/large files to Git LFS by rewriting
# history. Run this ONCE on a dedicated branch, then force-push.
#
# Prerequisites:
#   - git-lfs >= 3.0 installed
#   - Clean working tree (no uncommitted changes)
#   - Sufficient disk space (~3x repo size)
#   - Coordinate with all contributors (force-push required after)
#
# Usage:
#   bash scripts/migrate-to-lfs.sh                  # Full migration
#   bash scripts/migrate-to-lfs.sh --dry-run        # Preview only
#   bash scripts/migrate-to-lfs.sh --above=50KB     # Only files >50KB
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
ABOVE_SIZE="0"

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --above=*) ABOVE_SIZE="${arg#--above=}" ;;
        --help|-h)
            sed -n '1,/^set -euo/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown arg: $arg" ;;
    esac
done

echo "============================================================"
echo "  Git LFS Migration"
echo "  Dry run: ${DRY_RUN}"
echo "  Above size: ${ABOVE_SIZE}"
echo "============================================================"

if ! command -v git-lfs &>/dev/null; then
    echo "ERROR: git-lfs not installed."
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Working tree is dirty. Commit or stash changes first."
    exit 1
fi

PATTERNS="*.csv,*.jsonl,*.parquet,*.pdf,*.pt,*.bin,*.safetensors,*.onnx,*.h5,*.gguf,*.ckpt,*.pth,*.weights,*.model,*.mp4,*.mp3,*.wav,*.webm,*.mov,*.flac,*.ogg,*.zip,*.tar,*.tar.gz,*.tgz,*.tar.bz2,*.bz2,*.7z,*.rar,*.docx,*.xlsx,*.pptx,*.odt,*.ods,*.odp,*.ipynb,*.gif,*.webp,*.bmp,*.svg,*.ico"

ABOVE_FLAG=""
if [ "$ABOVE_SIZE" != "0" ]; then
    ABOVE_FLAG="--above=${ABOVE_SIZE}"
fi

if $DRY_RUN; then
    echo "DRY RUN — would execute:"
    echo "  git lfs migrate import ${ABOVE_FLAG} --include=\"${PATTERNS}\""
    exit 0
fi

echo "Starting migration (this may take 10-30 minutes)..."
START_TIME=$(date +%s)

git lfs migrate import ${ABOVE_FLAG} --include="${PATTERNS}"

END_TIME=$(date +%s)
echo "Migration complete in $((END_TIME - START_TIME))s"
echo ""
echo "Post-migration steps:"
echo "  1. git lfs ls-files | head -20"
echo "  2. git push --force origin main"
echo "  3. Notify all contributors to re-clone"
