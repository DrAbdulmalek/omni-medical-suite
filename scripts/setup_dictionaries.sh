#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# setup_dictionaries.sh — Download dictionary CSVs from GitHub Releases
#
# Usage:
#   bash scripts/setup_dictionaries.sh          # latest release
#   bash scripts/setup_dictionaries.sh v0.1     # specific tag
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="DrAbdulmalek/omni-medical-suite"
TAG="${1:-latest}"
DICT_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/dictionaries"
ARCHIVE="dictionaries.tar.gz"

mkdir -p "$DICT_DIR"

if [ "$TAG" = "latest" ]; then
    URL="https://github.com/${REPO}/releases/latest/download/${ARCHIVE}"
else
    URL="https://github.com/${REPO}/releases/download/${TAG}/${ARCHIVE}"
fi

echo "Downloading dictionaries from: $URL"
if curl -fSL --progress-bar -o "/tmp/${ARCHIVE}" "$URL"; then
    tar xzf "/tmp/${ARCHIVE}" -C "$DICT_DIR"
    rm -f "/tmp/${ARCHIVE}"
    echo "Done — $(ls "$DICT_DIR"/*.csv 2>/dev/null | wc -l) CSV files in $DICT_DIR"
else
    echo "ERROR: Download failed. Check the tag/release exists."
    exit 1
fi