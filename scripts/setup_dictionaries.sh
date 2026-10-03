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

# Reject unsafe archive member paths before extraction. The checksum protects
# the published bytes; this additionally makes the extraction contract explicit
# and prevents future installer changes from turning path traversal into a live
# filesystem write.
while IFS= read -r member; do
    member="${member#./}"
    if [[ "$member" = /* || "$member" == ".." || "$member" == ../* || "$member" == */../* || "$member" == */.. ]]; then
        echo "ERROR: Archive contains an unsafe path: $member" >&2
        exit 1
    fi
done < <(tar -tzf "$TMP_ARCHIVE")

# Extract into an isolated directory first so a bad/incomplete archive cannot
# partially modify the live dictionary directory. Do not preserve archive
# ownership/permissions in the build environment.
EXTRACT_DIR="$TMP_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
tar --no-same-owner --no-same-permissions -xzf "$TMP_ARCHIVE" -C "$EXTRACT_DIR"

# The published archive is the authoritative artifact, but its internal
# directory prefix is not part of the runtime contract. Locate the one
# directory that contains the complete expected artifact set. This supports
# archives produced with either data/dictionaries/specialty/, specialty/, or a
# release-specific top-level prefix without weakening the filename whitelist.
FOUND_SPECIALTY_DIR=""
while IFS= read -r candidate; do
    complete=true
    for file in "${EXPECTED_FILES[@]}"; do
        if [ ! -f "$candidate/$file" ] || [ -L "$candidate/$file" ]; then
            complete=false
            break
        fi
    done
    if [ "$complete" = true ]; then
        FOUND_SPECIALTY_DIR="$candidate"
        break
    fi
done < <(find "$EXTRACT_DIR" -type d -print)

if [ -z "$FOUND_SPECIALTY_DIR" ]; then
    echo "ERROR: Archive does not contain the complete expected specialty artifact set." >&2
    exit 1
fi

mkdir -p "$SPECIALTY_DIR"
for file in "${EXPECTED_FILES[@]}"; do
    install -m 0644 "$FOUND_SPECIALTY_DIR/$file" "$SPECIALTY_DIR/$file"
done

echo "Done — validated and installed ${#EXPECTED_FILES[@]} specialty dictionary artifacts in $SPECIALTY_DIR"
