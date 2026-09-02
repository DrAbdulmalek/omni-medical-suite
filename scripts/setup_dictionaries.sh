#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# setup_dictionaries.sh — Download Specialty TM dictionaries from GitHub Release
#
# Usage:
#   bash scripts/setup_dictionaries.sh          # latest release
#   bash scripts/setup_dictionaries.sh v0.1     # specific tag
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="DrAbdulmalek/omni-medical-suite"
TAG="${1:-latest}"
DICT_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/dictionaries"
ARCHIVE="malek-specialty-dictionaries.tar.gz"
EXPECTED_V1_SHA256="377f65f33d52df03a44dd759ac3cb145f22718dd446fd6e5cba4f14278c78820"

mkdir -p "$DICT_DIR"

if [ "$TAG" = "latest" ]; then
    URL="https://github.com/${REPO}/releases/latest/download/${ARCHIVE}"
else
    URL="https://github.com/${REPO}/releases/download/${TAG}/${ARCHIVE}"
fi

echo "Downloading specialty dictionaries from: $URL"
if ! curl -fSL --progress-bar -o "/tmp/${ARCHIVE}" "$URL"; then
    echo "ERROR: Download failed. Check the tag/release exists and contains ${ARCHIVE}." >&2
    exit 1
fi

# The published v1 artifact has a recorded SHA-256 digest. Verify it whenever
# that exact release is requested; do not silently accept a modified archive.
if [ "$TAG" = "malek-dictionaries-v1" ]; then
    ACTUAL_SHA256="$(sha256sum "/tmp/${ARCHIVE}" | awk '{print $1}')"
    if [ "$ACTUAL_SHA256" != "$EXPECTED_V1_SHA256" ]; then
        echo "ERROR: SHA-256 mismatch for ${TAG}." >&2
        echo "Expected: ${EXPECTED_V1_SHA256}" >&2
        echo "Actual:   ${ACTUAL_SHA256}" >&2
        rm -f "/tmp/${ARCHIVE}"
        exit 1
    fi
    echo "Verified SHA-256: ${ACTUAL_SHA256}"
fi

tar xzf "/tmp/${ARCHIVE}" -C "$DICT_DIR"
rm -f "/tmp/${ARCHIVE}"

SPECIALTY_DIR="$DICT_DIR/specialty"
EXPECTED_FILES=(
    orthopedic_surgery.json
    anatomy.json
    general_medical.json
    surgery_general.json
    cardiovascular.json
    oncology.json
    abdomen_pelvis.json
    endocrinology.json
    _summary.json
    _quarantined.json
    _monolingual_corpus.json
    _hashes.json
)

for file in "${EXPECTED_FILES[@]}"; do
    if [ ! -f "$SPECIALTY_DIR/$file" ]; then
        echo "ERROR: Missing required specialty dictionary artifact: $SPECIALTY_DIR/$file" >&2
        exit 1
    fi
done

echo "Done — validated ${#EXPECTED_FILES[@]} specialty dictionary artifacts in $SPECIALTY_DIR"