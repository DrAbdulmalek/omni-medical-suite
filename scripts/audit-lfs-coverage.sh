#!/usr/bin/env bash
# =============================================================================
# audit-lfs-coverage.sh — Verify Git LFS coverage for large files
# =============================================================================
# Scans the working tree for files >1MB and reports which are covered by
# the current .gitattributes LFS patterns.
#
# Usage:
#   ./scripts/audit-lfs-coverage.sh           # report only
#   ./scripts/audit-lfs-coverage.sh --strict  # exit 1 if any uncovered file found
#
# Exit codes:
#   0 — success (or no uncovered files in --strict mode)
#   1 — uncovered large files found (--strict mode only)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STRICT=0

if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
fi

cd "$ROOT_DIR"

echo "=== Git LFS Coverage Audit ==="
echo "Repo: $ROOT_DIR"
echo ""

# Check git-lfs is installed
if ! command -v git-lfs &>/dev/null; then
  echo "WARNING: git-lfs not installed. Install it to enable LFS tracking."
  echo "  Debian/Ubuntu: sudo apt install git-lfs"
  echo "  Arch/Manjaro:  sudo pacman -S git-lfs"
  echo "  macOS:         brew install git-lfs"
  echo ""
fi

# Patterns currently tracked (extracted from .gitattributes)
if [[ ! -f .gitattributes ]]; then
  echo "ERROR: .gitattributes not found" >&2
  exit 1
fi

echo "--- Current .gitattributes LFS patterns ---"
grep 'filter=lfs' .gitattributes | grep -v '^#' | head -30
echo ""

# Find files >1MB
echo "--- Files >1MB in working tree ---"
LARGE_FILES=$(find . -path ./.git -prune -o -type f -size +1M -print 2>/dev/null | sort)

if [[ -z "$LARGE_FILES" ]]; then
  echo "  (no files >1MB found)"
  exit 0
fi

# Check each large file against .gitattributes patterns
COVERED=0
UNCOVERED=0
UNCOVERED_LIST=""

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  # Get file size in KB
  size_bytes=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f" 2>/dev/null)
  size_kb=$((size_bytes / 1024))

  # Check if file is tracked by LFS (git lfs ls-files) or matches a pattern
  # Simple check: extract extensions and path patterns from .gitattributes
  ext="${f##*.}"
  covered=false

  # Check by extension
  if grep -qE "^\*\.$ext\s+filter=lfs" .gitattributes 2>/dev/null; then
    covered=true
  fi

  # Check by path prefix (data/**, etc.)
  if [[ "$covered" == "false" ]]; then
    # Get all path patterns (non-*.ext patterns)
    while IFS= read -r pattern; do
      [[ -z "$pattern" ]] && continue
      # Strip trailing /** and check if file starts with the prefix
      prefix="${pattern%%/\**}"
      if [[ "$f" == "./${prefix}/"* ]] || [[ "$f" == "./${prefix}" ]]; then
        covered=true
        break
      fi
    done < <(grep 'filter=lfs' .gitattributes | grep -v '^#' | awk '{print $1}' | grep -v '^\*\.' | grep '/')
  fi

  # Check exact path match
  if [[ "$covered" == "false" ]]; then
    rel_path="${f#./}"
    if grep -qF "$rel_path" .gitattributes 2>/dev/null; then
      covered=true
    fi
  fi

  # Also check git lfs ls-files if available
  if [[ "$covered" == "false" ]] && command -v git-lfs &>/dev/null; then
    if git lfs ls-files 2>/dev/null | grep -qF "$rel_path"; then
      covered=true
    fi
  fi

  if [[ "$covered" == "true" ]]; then
    echo "  [COVERED]   $f (${size_kb}KB)"
    COVERED=$((COVERED + 1))
  else
    echo "  [UNCOVERED] $f (${size_kb}KB, .${ext})"
    UNCOVERED=$((UNCOVERED + 1))
    UNCOVERED_LIST="${UNCOVERED_LIST}\n  $f"
  fi
done <<< "$LARGE_FILES"

echo ""
echo "=== Summary ==="
echo "  Covered:   $COVERED"
echo "  Uncovered: $UNCOVERED"
echo ""

if [[ "$UNCOVERED" -gt 0 ]]; then
  echo "WARNING: $UNCOVERED large file(s) not covered by LFS patterns."
  echo -e "Uncovered files:$UNCOVERED_LIST"
  echo ""
  echo "To fix: add patterns to .gitattributes for the uncovered extensions/paths."
  if [[ "$STRICT" == "1" ]]; then
    exit 1
  fi
else
  echo "✅ All large files are covered by LFS patterns."
fi
