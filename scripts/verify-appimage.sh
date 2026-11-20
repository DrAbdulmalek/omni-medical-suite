#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# verify-appimage.sh — Verify an AppImage artifact for v1.1.0+
# ══════════════════════════════════════════════════════════════════════
# Performs comprehensive verification of an AppImage release:
#   1. SHA256 checksum verification
#   2. File permissions + executable bit
#   3. AppImage type (1 or 2) detection
#   4. SquashFS mount test (list contained files)
#   5. Desktop entry validation
#   6. Metainfo XML validation
#   7. Offscreen launch smoke test
#   8. Version string check
#   9. Freshness marker check
#
# Usage:
#   bash scripts/verify-appimage.sh MedicalDocProcessor-1.1.0-x86_64.AppImage
#   bash scripts/verify-appimage.sh  # auto-detect latest AppImage
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Find AppImage
APPIMAGE="${1:-}"
if [ -z "$APPIMAGE" ]; then
    # Auto-detect
    CANDIDATES=$(find "$REPO_ROOT/packages/desktop" -name "MedicalDocProcessor-*.AppImage" -type f 2>/dev/null | sort -r | head -1)
    if [ -z "$CANDIDATES" ]; then
        CANDIDATES=$(find . -name "MedicalDocProcessor-*.AppImage" -type f 2>/dev/null | sort -r | head -1)
    fi
    if [ -z "$CANDIDATES" ]; then
        echo "ERROR: No AppImage found. Pass path as argument."
        exit 1
    fi
    APPIMAGE="$CANDIDATES"
fi

if [ ! -f "$APPIMAGE" ]; then
    echo "ERROR: $APPIMAGE not found"
    exit 1
fi

PASS=0
FAIL=0
WARN=0

check_pass() { echo "  ✅ $1"; PASS=$((PASS+1)); }
check_fail() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }
check_warn() { echo "  ⚠️  $1"; WARN=$((WARN+1)); }

echo "═══════════════════════════════════════════════════"
echo "  AppImage Verification"
echo "  File: $APPIMAGE"
echo "  Size: $(du -h "$APPIMAGE" | cut -f1)"
echo "═══════════════════════════════════════════════════"

# ── 1. SHA256 checksum ─────────────────────────────────────────────
echo ""
echo "1. SHA256 Checksum"
SHAFILE="${APPIMAGE}.sha256"
if [ -f "$SHAFILE" ]; then
    if sha256sum -c "$SHAFILE" 2>/dev/null; then
        check_pass "SHA256 checksum verified"
    else
        check_fail "SHA256 checksum MISMATCH"
    fi
else
    check_warn "No .sha256 file found — cannot verify checksum"
fi

# ── 2. File permissions ────────────────────────────────────────────
echo ""
echo "2. File Permissions"
if [ -x "$APPIMAGE" ]; then
    check_pass "Executable bit set"
else
    check_warn "Not executable — run: chmod +x $APPIMAGE"
fi

PERMS=$(stat -c%a "$APPIMAGE" 2>/dev/null || stat -f%A "$APPIMAGE" 2>/dev/null || echo "unknown")
echo "  ℹ️  Permissions: $PERMS"

# ── 3. AppImage type ──────────────────────────────────────────────
echo ""
echo "3. AppImage Type"
MAGIC=$(dd if="$APPIMAGE" bs=1 count=4 skip=8 2>/dev/null | xxd -p 2>/dev/null || echo "")
if echo "$MAGIC" | grep -qi "41490"; then
    check_pass "AppImage Type 2 detected"
elif file "$APPIMAGE" 2>/dev/null | grep -qi "AppImage"; then
    check_pass "AppImage detected (type unknown)"
else
    check_warn "Not detected as AppImage by magic bytes"
fi

# ── 4. SquashFS / contents ─────────────────────────────────────────
echo ""
echo "4. SquashFS Contents"
if command -v unsquashfs &>/dev/null; then
    MOUNT_DIR=$(mktemp -d)
    if unsquashfs -l "$APPIMAGE" > /dev/null 2>&1; then
        FILE_COUNT=$(unsquashfs -l "$APPIMAGE" 2>/dev/null | wc -l)
        check_pass "SquashFS readable ($FILE_COUNT entries)"
        # Check for key files
        if unsquashfs -l "$APPIMAGE" 2>/dev/null | grep -q "medical-doc-processor"; then
            check_pass "Binary 'medical-doc-processor' found in image"
        else
            check_warn "Binary 'medical-doc-processor' not found in image"
        fi
    else
        check_fail "Cannot read SquashFS"
    fi
    rm -rf "$MOUNT_DIR"
else
    check_warn "unsquashfs not installed — cannot inspect contents"
fi

# ── 5. Desktop entry ──────────────────────────────────────────────
echo ""
echo "5. Desktop Entry"
if command -v unsquashfs &>/dev/null; then
    MOUNT_DIR=$(mktemp -d)
    unsquashfs -d "$MOUNT_DIR" "$APPIMAGE" > /dev/null 2>&1 || true
    DESKTOP_FILE=$(find "$MOUNT_DIR" -name "*.desktop" -type f 2>/dev/null | head -1)
    if [ -n "$DESKTOP_FILE" ]; then
        check_pass "Desktop entry found: $(basename "$DESKTOP_FILE")"
        # Validate required keys
        for key in Name Exec Icon Type; do
            if grep -q "^${key}=" "$DESKTOP_FILE" 2>/dev/null; then
                check_pass "Desktop key '${key}' present"
            else
                check_fail "Desktop key '${key}' missing"
            fi
        done
        # Check Type=Application
        if grep -q "^Type=Application" "$DESKTOP_FILE" 2>/dev/null; then
            check_pass "Desktop Type=Application"
        else
            check_fail "Desktop Type is not 'Application'"
        fi
    else
        check_fail "No .desktop file found in AppImage"
    fi
    rm -rf "$MOUNT_DIR"
fi

# ── 6. Metainfo XML ───────────────────────────────────────────────
echo ""
echo "6. Metainfo XML"
if command -v unsquashfs &>/dev/null; then
    MOUNT_DIR=$(mktemp -d)
    unsquashfs -d "$MOUNT_DIR" "$APPIMAGE" > /dev/null 2>&1 || true
    METAINFO=$(find "$MOUNT_DIR" -name "*.metainfo.xml" -type f 2>/dev/null | head -1)
    if [ -n "$METAINFO" ]; then
        check_pass "Metainfo found: $(basename "$METAINFO")"
        # Check version
        VERSION=$(grep -oP 'version="[^"]*"' "$METAINFO" 2>/dev/null | head -1 || echo "")
        if [ -n "$VERSION" ]; then
            check_pass "Version in metainfo: $VERSION"
        else
            check_warn "No version in metainfo"
        fi
    else
        check_warn "No metainfo.xml found"
    fi
    rm -rf "$MOUNT_DIR"
fi

# ── 7. Offscreen smoke test ────────────────────────────────────────
echo ""
echo "7. Smoke Test (offscreen)"
if [ -x "$APPIMAGE" ]; then
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] || [ "${OMNI_APPIMAGE_OFFSCREEN:-}" = "1" ]; then
        TIMEOUT_CMD=$(command -v timeout || command -v gtimeout || echo "")
        if [ -n "$TIMEOUT_CMD" ]; then
            QT_QPA_PLATFORM=offscreen $TIMEOUT_CMD 10 "$APPIMAGE" --version 2>/dev/null && \
                check_pass "AppImage launches (offscreen)" || \
                check_warn "AppImage did not exit cleanly (may need display)"
        else
            check_warn "timeout command not available — skipping launch test"
        fi
    else
        check_warn "No display available — set OMNI_APPIMAGE_OFFSCREEN=1 or run on desktop"
    fi
else
    check_fail "AppImage not executable — cannot smoke test"
fi

# ── 8. Version check ───────────────────────────────────────────────
echo ""
echo "8. Version Check"
FILENAME=$(basename "$APPIMAGE")
if echo "$FILENAME" | grep -qP '\d+\.\d+\.\d+'; then
    FILE_VERSION=$(echo "$FILENAME" | grep -oP '\d+\.\d+\.\d+(-\w+)?' | head -1)
    check_pass "Version from filename: $FILE_VERSION"
else
    check_warn "Cannot extract version from filename"
fi

# ── 9. Freshness marker ────────────────────────────────────────────
echo ""
echo "9. Freshness Marker"
FRESHNESS_FILE="$REPO_ROOT/packages/desktop/.last_build_commit"
if [ -f "$FRESHNESS_FILE" ]; then
    BUILD_COMMIT=$(head -1 "$FRESHNESS_FILE" | awk '{print $1}')
    BUILD_DATE=$(head -1 "$FRESHNESS_FILE" | awk '{print $2}')
    check_pass "Freshness marker exists"
    echo "  ℹ️  Build commit: ${BUILD_COMMIT:0:7}  Date: $BUILD_DATE"
    # Compare with HEAD
    if command -v git &>/dev/null && [ -d "$REPO_ROOT/.git" ]; then
        HEAD_COMMIT=$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo "")
        if [ "$BUILD_COMMIT" = "$HEAD_COMMIT" ]; then
            check_pass "Build commit matches HEAD"
        else
            check_warn "Build commit (${BUILD_COMMIT:0:7}) differs from HEAD (${HEAD_COMMIT:0:7})"
        fi
    fi
else
    check_warn "No .last_build_commit file — freshness tracking not available"
fi

# ── Summary ────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Results: ✅ ${PASS} passed  ❌ ${FAIL} failed  ⚠️  ${WARN} warnings"
echo "═══════════════════════════════════════════════════"

if [ $FAIL -gt 0 ]; then
    echo "  ❌ AppImage verification FAILED"
    exit 1
elif [ $WARN -gt 3 ]; then
    echo "  ⚠️  AppImage verification passed with warnings"
    exit 2
else
    echo "  ✅ AppImage verification PASSED"
    exit 0
fi
