#!/usr/bin/env bash
set -euo pipefail

REPO="DrAbdulmalek/omni-medical-suite"
TAG="${1:-malek-dictionaries-v1}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DICT_DIR="$ROOT_DIR/data/dictionaries"
SPECIALTY_DIR="$DICT_DIR/specialty"
ARCHIVE="malek-specialty-dictionaries.tar.gz"

# Production-consumable releases must have an explicit immutable checksum.
case "$TAG" in
    malek-dictionaries-v1)
        EXPECTED_SHA256="377f65f33d52df03a44dd759ac3cb145f22718dd446fd6e5cba4f14278c78820"
        ;;
    *)
        echo "ERROR: No pinned SHA-256 is registered for release tag '${TAG}'." >&2
        echo "Add the release and its verified SHA-256 to this installer before use." >&2
        exit 1
        ;;
esac

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

mkdir -p "$DICT_DIR"
URL="https://github.com/${REPO}/releases/download/${TAG}/${ARCHIVE}"
TMP_DIR="$(mktemp -d)"
TMP_ARCHIVE="$TMP_DIR/$ARCHIVE"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Downloading specialty dictionaries from: $URL"
if ! curl -fSL --progress-bar -o "$TMP_ARCHIVE" "$URL"; then
    echo "ERROR: Download failed. Check that release ${TAG} contains ${ARCHIVE}." >&2
    exit 1
fi

ACTUAL_SHA256="$(sha256sum "$TMP_ARCHIVE" | awk '{print $1}')"
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
    echo "ERROR: SHA-256 mismatch for ${TAG}." >&2
    echo "Expected: ${EXPECTED_SHA256}" >&2
    echo "Actual:   ${ACTUAL_SHA256}" >&2
    exit 1
fi
echo "Verified SHA-256: ${ACTUAL_SHA256}"

# Extract into an isolated directory first so a bad/incomplete archive cannot
# partially modify the live dictionary directory.
EXTRACT_DIR="$TMP_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
tar xzf "$TMP_ARCHIVE" -C "$EXTRACT_DIR"

FOUND_SPECIALTY_DIR=""
if [ -d "$EXTRACT_DIR/data/dictionaries/specialty" ]; then
    FOUND_SPECIALTY_DIR="$EXTRACT_DIR/data/dictionaries/specialty"
elif [ -d "$EXTRACT_DIR/specialty" ]; then
    FOUND_SPECIALTY_DIR="$EXTRACT_DIR/specialty"
else
    CANDIDATE="$(find "$EXTRACT_DIR" -type d -path '*/data/dictionaries/specialty' -print -quit)"
    if [ -n "$CANDIDATE" ]; then
        FOUND_SPECIALTY_DIR="$CANDIDATE"
    fi
fi

if [ -z "$FOUND_SPECIALTY_DIR" ]; then
    echo "ERROR: Archive does not contain a data/dictionaries/specialty directory." >&2
    exit 1
fi

for file in "${EXPECTED_FILES[@]}"; do
    if [ ! -f "$FOUND_SPECIALTY_DIR/$file" ]; then
        echo "ERROR: Missing required specialty dictionary artifact: $file" >&2
        exit 1
    fi
done

mkdir -p "$SPECIALTY_DIR"
for file in "${EXPECTED_FILES[@]}"; do
    install -m 0644 "$FOUND_SPECIALTY_DIR/$file" "$SPECIALTY_DIR/$file"
done

echo "Done — validated and installed ${#EXPECTED_FILES[@]} specialty dictionary artifacts in $SPECIALTY_DIR"