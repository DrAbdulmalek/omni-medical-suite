#!/usr/bin/env bash
set -euo pipefail

REPO="DrAbdulmalek/omni-medical-suite"
TAG="${1:-malek-dictionaries-v2}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DICT_DIR="$ROOT_DIR/data/dictionaries"
SPECIALTY_DIR="$DICT_DIR/specialty"
ARCHIVE="malek-specialty-dictionaries.tar.gz"

# Production-consumable releases must have an explicit immutable checksum.
# malek-dictionaries-v2 is the only production-allowed release: its archive
# passes the deterministic packager's security policy (0644 data files, 0755
# directories, normalized root:root ownership, no symlinks/hardlinks/FIFO/
# device, no .gitkeep, no executable regular files, no path traversal).
#
# malek-dictionaries-v1 is REJECTED by validate_archive (12 executable JSON
# files + .gitkeep). The v1 case below is intentionally omitted: pinning
# the SHA would allow callers to install v1 by passing the tag explicitly,
# bypassing the security policy. The installer must refuse v1 outright.
case "$TAG" in
    malek-dictionaries-v2)
        EXPECTED_SHA256="dfb3167b3f05f35f955d70741d5917a8c6f34ac590c92090358e127e351cecd2"
        ;;
    malek-dictionaries-v1)
        # v1 is a known-insecure artifact (12 executable JSON files + .gitkeep).
        # Refuse it explicitly — no SHA pin, no fallback, no bypass.
        echo "ERROR: malek-dictionaries-v1 is a deprecated, policy-violating release." >&2
        echo "       Its archive contains 12 executable JSON files + .gitkeep," >&2
        echo "       which fail scripts/package_specialty_dictionaries.py --validate-only." >&2
        echo "       Use malek-dictionaries-v2 (the production default) instead." >&2
        exit 1
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

# Validate member paths from tar's name listing before any extraction. Do not
# parse filenames from `tar -tv` columns: that format is human-readable and
# whitespace in a filename would make it ambiguous.
while IFS= read -r member; do
    [ -z "$member" ] && continue
    member="${member#./}"
    if [[ "$member" = /* || "$member" == ".." || "$member" == ../* || "$member" == */../* || "$member" == */.. ]]; then
        echo "ERROR: Archive contains an unsafe path: $member" >&2
        exit 1
    fi
done < <(tar -tzf "$TMP_ARCHIVE")

# Validate member types and permission bits before extraction. SHA-256
# authenticates the exact bytes, but it does not establish that those bytes
# satisfy the archive's security policy.
while IFS= read -r line; do
    [ -z "$line" ] && continue
    mode="${line:0:10}"
    type="${line:0:1}"
    # GNU tar's verbose listing has a fixed ten-character mode field followed
    # by one separator space. Taking the remainder preserves spaces in names.
    member="${line:11}"

    case "$type" in
        d)
            # Directories are allowed; permissions are not restored because
            # extraction uses --no-same-permissions.
            ;;
        -)
            if [[ "$mode" == *x* ]]; then
                echo "ERROR: Archive contains an executable regular file: $member" >&2
                exit 1
            fi
            ;;
        l)
            echo "ERROR: Archive contains a symlink: $member" >&2
            exit 1
            ;;
        h)
            echo "ERROR: Archive contains a hardlink: $member" >&2
            exit 1
            ;;
        p)
            echo "ERROR: Archive contains a FIFO: $member" >&2
            exit 1
            ;;
        c|b)
            echo "ERROR: Archive contains a device node: $member" >&2
            exit 1
            ;;
        s)
            echo "ERROR: Archive contains a socket: $member" >&2
            exit 1
            ;;
        *)
            echo "ERROR: Archive contains an unsupported member type '${type}': $member" >&2
            exit 1
            ;;
    esac
done < <(tar -tvzf "$TMP_ARCHIVE")

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
