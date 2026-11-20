#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# build_apk.sh — End-to-end APK build script for OmniMedical Android
# ═══════════════════════════════════════════════════════════════════════════
# Tested on:
#   • Ubuntu 22.04 LTS (x86_64)
#   • Debian 12 (bookworm)
#   • Manjaro 23 (with `pacman -S android-tools build-essential zip`)
#
# Requirements:
#   • ~6 GB free disk (SDK + NDK + build artifacts)
#   • ~4 GB RAM
#   • Internet access (downloads ~2 GB on first run)
#
# Usage:
#   ./build_apk.sh setup       # one-time env setup
#   ./build_apk.sh debug       # build debug APK
#   ./build_apk.sh release     # build release APK (signed)
#   ./build_apk.sh deploy      # deploy to connected device + run
#   ./build_apk.sh clean       # remove build artifacts
#   ./build_apk.sh smoke       # post-build smoke test (size + sha)
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*" >&2; }

# ── Commands ────────────────────────────────────────────────────────────────
setup() {
    log "Setting up buildozer environment..."
    sudo apt-get update -y
    sudo apt-get install -y --no-install-recommends \
        build-essential \
        ccache \
        git \
        zip \
        unzip \
        openjdk-17-jdk \
        autoconf \
        libtool \
        pkg-config \
        zlib1g-dev \
        libncurses5-dev \
        libncursesw5-dev \
        libtinfo5 \
        cmake \
        libffi-dev \
        libssl-dev \
        android-tools-adb \
        android-tools-fastboot

    # Python buildozer + dependencies
    pip install --upgrade pip
    pip install \
        "buildozer==1.5.0" \
        "cython==0.29.36" \
        "virtualenv" \
        "sh" \
        "jinja2" \
        "six"

    # Java env
    export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(which javac)")")")"
    export PATH="$JAVA_HOME/bin:$PATH"
    grep -q "JAVA_HOME" ~/.bashrc || echo "export JAVA_HOME=$JAVA_HOME" >> ~/.bashrc
    grep -q "JAVA_HOME/bin" ~/.bashrc || echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> ~/.bashrc

    # Verify
    java -version
    python3 --version
    buildozer version
    ok "Setup complete. Run: ./build_apk.sh debug"
}

debug() {
    log "Running prebuild..."
    python3 prebuild.py

    log "Building debug APK (this takes 20-40 min on first run)..."
    buildozer -v android debug

    log "Running postbuild..."
    python3 postbuild.py
    ok "Debug APK ready in bin/"
}

release() {
    if [[ -z "${KEYSTORE_PASS:-}" ]]; then
        err "KEYSTORE_PASS env var required for release build"
        err "Generate keystore first:"
        err "  keytool -genkey -v -keystore omnimedical-release.keystore -alias omnimedical -keyalg RSA -keysize 2048 -validity 10000"
        exit 1
    fi
    log "Building release APK (signed)..."
    buildozer -v android release
    ok "Release APK ready in bin/"
}

deploy() {
    log "Deploying to connected device..."
    adb devices
    buildozer android deploy run
    ok "Deployed. Watch logcat:"
    log "  adb logcat -s python"
}

clean() {
    log "Cleaning build artifacts..."
    rm -rf build/ bin/ .buildozer/ 2>/dev/null || true
    ok "Clean"
}

smoke() {
    log "Smoke test: APK integrity..."
    APK=$(ls bin/*.apk 2>/dev/null | head -1)
    if [[ -z "$APK" ]]; then
        err "no APK in bin/"
        exit 1
    fi
    SIZE_MB=$(du -m "$APK" | cut -f1)
    SHA=$(sha256sum "$APK" | cut -d' ' -f1)
    log "APK: $APK"
    log "Size: ${SIZE_MB} MB"
    log "SHA256: $SHA"
    if (( SIZE_MB > 150 )); then
        warn "APK exceeds 150MB"
        exit 1
    fi
    ok "smoke test passed"
}

# ── Main ────────────────────────────────────────────────────────────────────
case "${1:-debug}" in
    setup)   setup ;;
    debug)   debug ;;
    release) release ;;
    deploy)  deploy ;;
    clean)   clean ;;
    smoke)   smoke ;;
    *)
        echo "Usage: $0 {setup|debug|release|deploy|clean|smoke}"
        exit 1
        ;;
esac
