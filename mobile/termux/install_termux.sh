#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# install_termux.sh — OmniMedical Suite installer for Termux (Android ARM64)
# ═══════════════════════════════════════════════════════════════════════════
# يعمل على Termux مباشرة (بدون proot-distro) أو داخل proot Ubuntu ARM64.
#
# الاستخدام:
#   pkg install -y git curl
#   curl -fsSL https://raw.githubusercontent.com/DrAbdulmalek/omni-medical-suite/main/mobile/termux/install_termux.sh | bash
#
# أو من clone محلي:
#   cd omni-medical-suite/mobile/termux
#   bash install_termux.sh
#
# بعد التثبيت:
#   omni-ocr        # يفتح Gradio UI على http://localhost:7860
#   omni-stop       # يوقف الخادم
#   omni-update     # يحدّث المشروع + النماذج
# ═══════════════════════════════════════════════════════════════════════════
set -e

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*" >&2; }
step() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

# ── Detect environment ─────────────────────────────────────────────────────
IS_PROOT=0
if [ -n "$(command -v proot 2>/dev/null)" ] && [ ! -f "/etc/termux-release" ]; then
    IS_PROOT=1
fi

if [ -d "/data/data/com.termux" ]; then
    ENV_TYPE="termux"
elif [ -f "/etc/lsb-release" ] && grep -q Ubuntu /etc/lsb-release 2>/dev/null; then
    ENV_TYPE="proot-ubuntu"
else
    ENV_TYPE="unknown"
fi
log "Environment: $ENV_TYPE"

# ────────────────────────────────────────────────────────────────────────────
# PATH A: Termux native (no proot)
# ────────────────────────────────────────────────────────────────────────────
install_termux_native() {
    step "1/6 — تحديث الحزم"
    pkg update -y && pkg upgrade -y

    step "2/6 — تثبيت التبعيات النظامية"
    pkg install -y \
        python \
        python-pip \
        git \
        curl \
        wget \
        tesseract \
        tesseract-data \
        libjpeg-turbo \
        libpng \
        zlib \
        openssl \
        proot-distro \
        termux-api
    ok "System deps installed"

    step "3/6 — تثبيت Python packages"
    pip install --upgrade pip wheel setuptools
    pip install \
        "gradio==4.19.2" \
        "pillow==10.2.0" \
        "opencv-python-headless==4.9.0.80" \
        "pytesseract==0.3.10" \
        "numpy==1.26.4" \
        "pdf2image==1.17.0" \
        "huggingface_hub==0.20.3" \
        "transformers==4.40.2" \
        "torch==2.2.1" \
        "tqdm==4.66.3" \
        "ftfy==6.1.3" \
        "regex==2023.12.25"
    ok "Python packages installed"

    step "4/6 — تثبيت poppler (لـ PDF)"
    pkg install -y poppler
    ok "poppler installed"
}

# ────────────────────────────────────────────────────────────────────────────
# PATH B: proot-distro Ubuntu ARM64
# ────────────────────────────────────────────────────────────────────────────
install_proot_ubuntu() {
    step "1/7 — تثبيت proot-distro"
    pkg install -y proot-distro
    ok "proot-distro ready"

    step "2/7 — تثبيت Ubuntu ARM64"
    if ! proot-distro list | grep -q "ubuntu.*installed"; then
        proot-distro install ubuntu
        ok "Ubuntu ARM64 installed"
    else
        ok "Ubuntu already installed"
    fi

    step "3/7 — تثبيت حزم النظام داخل Ubuntu"
    proot-distro login ubuntu -- bash -c "
        apt-get update -y
        apt-get install -y \
            python3 python3-pip python3-venv \
            git curl wget \
            tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng \
            poppler-utils \
            libgl1 libglib2.0-0 \
            build-essential
    "
    ok "System packages installed in Ubuntu"

    step "4/7 — تثبيت Python packages داخل Ubuntu"
    proot-distro login ubuntu -- bash -c "
        pip3 install --upgrade pip wheel setuptools
        pip3 install \
            'gradio==4.19.2' \
            'pillow==10.2.0' \
            'opencv-python-headless==4.9.0.80' \
            'pytesseract==0.3.10' \
            'numpy==1.26.4' \
            'pdf2image==1.17.0' \
            'huggingface_hub==0.20.3' \
            'transformers==4.40.2' \
            'torch==2.2.1' \
            'tqdm==4.66.3' \
            'ftfy==6.1.3' \
            'regex==2023.12.25'
    "
    ok "Python packages installed in Ubuntu"
}

# ────────────────────────────────────────────────────────────────────────────
# Common: clone project + setup workspace
# ────────────────────────────────────────────────────────────────────────────
setup_workspace() {
    step "5/6 — استنساخ المشروع"

    if [ "$ENV_TYPE" = "proot-ubuntu" ]; then
        WORKDIR="$HOME/ubuntu-fs/root/omni-medical-suite"
    else
        WORKDIR="$HOME/omni-medical-suite"
    fi

    if [ -d "$WORKDIR" ]; then
        ok "Project exists at $WORKDIR — pulling updates"
        cd "$WORKDIR" && git pull --rebase || warn "git pull failed (continue anyway)"
    else
        log "Cloning to $WORKDIR..."
        git clone --depth 1 https://github.com/DrAbdulmalek/omni-medical-suite.git "$WORKDIR"
        ok "Project cloned"
    fi

    step "6/6 — إعداد مساحة العمل"
    WORKSPACE="$HOME/omni_workspace"
    mkdir -p "$WORKSPACE"/{uploads,exports,models,corrections_db,logs}
    ok "Workspace ready at: $WORKSPACE"

    # Install scanner_fixer as an editable pip package so `import scanner_fixer`
    # works without any sys.path hacks. Falls back silently if pip install
    # fails (termux_app.py has its own sys.path bootstrap as a safety net).
    if [ -f "$WORKDIR/packages/scanner_fixer/pyproject.toml" ]; then
        log "Installing scanner_fixer (editable)..."
        pip install -e "$WORKDIR/packages/scanner_fixer" 2>/dev/null && \
            ok "scanner_fixer installed (editable)" || \
            warn "pip install -e scanner_fixer failed — termux_app.py will use sys.path fallback"
    fi

    # Copy termux_app.py to workspace if it exists in repo. The launcher
    # exports OMNI_REPO_ROOT so the copied file can still discover the
    # repo root (for packages.core.* imports) even though it's running
    # from $WORKSPACE.
    if [ -f "$WORKDIR/mobile/termux/termux_app.py" ]; then
        cp "$WORKDIR/mobile/termux/termux_app.py" "$WORKSPACE/termux_app.py"
        ok "termux_app.py copied to workspace"
    fi

    # Generate launcher scripts
    generate_launchers
}

# ────────────────────────────────────────────────────────────────────────────
# Generate launcher scripts (omni-ocr, omni-stop, omni-update)
# ────────────────────────────────────────────────────────────────────────────
generate_launchers() {
    local BIN_DIR="$HOME/bin"
    mkdir -p "$BIN_DIR"

    # Add ~/bin to PATH if not already there
    if ! echo "$PATH" | grep -q "$BIN_DIR"; then
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$HOME/.bashrc"
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$HOME/.zshrc" 2>/dev/null || true
        export PATH="$BIN_DIR:$PATH"
    fi

    # ── omni-ocr ─────────────────────────────────────────────────────────
    cat > "$BIN_DIR/omni-ocr" << 'OCR_EOF'
#!/data/data/com.termux/files/usr/bin/bash
# OmniMedical OCR — launcher for Termux
set -e

WORKSPACE="$HOME/omni_workspace"
WORKDIR="$HOME/omni-medical-suite"
PORT="${1:-7860}"

# Export repo root so the copied termux_app.py at $WORKSPACE can find
# packages.core.* and (as a fallback) packages/scanner_fixer/src via
# its sys.path bootstrap. If the repo isn't cloned, termux_app.py will
# silently fall back to standalone mode (local OpenCV + local SQLite).
if [ -d "$WORKDIR/packages" ]; then
    export OMNI_REPO_ROOT="$WORKDIR"
fi

cd "$WORKSPACE"

# Determine python command
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "✗ Python not found. Run install_termux.sh first."
    exit 1
fi

# Start server in background
echo "🚀 Starting OmniMedical OCR on port $PORT..."
echo "📱 Open in browser: http://localhost:$PORT"
echo "⏹  Stop with: omni-stop"
echo ""

# Save PID for stop script
echo $$ > "$WORKSPACE/.omni_pid"

# Run gradio app
exec "$PY" "$WORKSPACE/termux_app.py" --port "$PORT"
OCR_EOF
    chmod +x "$BIN_DIR/omni-ocr"

    # ── omni-stop ────────────────────────────────────────────────────────
    cat > "$BIN_DIR/omni-stop" << 'STOP_EOF'
#!/data/data/com.termux/files/usr/bin/bash
WORKSPACE="$HOME/omni_workspace"
PID_FILE="$WORKSPACE/.omni_pid"

if [ ! -f "$PID_FILE" ]; then
    echo "ℹ  No running server found"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "✓ Stopped OmniMedical OCR (PID: $PID)"
else
    echo "ℹ  Process not running (stale PID file)"
fi
rm -f "$PID_FILE"

# Also kill any python process running termux_app.py
pkill -f "termux_app.py" 2>/dev/null || true
STOP_EOF
    chmod +x "$BIN_DIR/omni-stop"

    # ── omni-update ──────────────────────────────────────────────────────
    cat > "$BIN_DIR/omni-update" << 'UPDATE_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -e
WORKDIR="$HOME/omni-medical-suite"
WORKSPACE="$HOME/omni_workspace"

echo "📥 Updating omni-medical-suite..."
cd "$WORKDIR" && git pull --rebase

echo "📦 Updating Python packages..."
pip install --upgrade \
    gradio pillow opencv-python-headless pytesseract numpy pdf2image \
    huggingface_hub transformers torch tqdm ftfy regex 2>/dev/null || \
pip3 install --upgrade \
    gradio pillow opencv-python-headless pytesseract numpy pdf2image \
    huggingface_hub transformers torch tqdm ftfy regex

# Refresh termux_app.py
if [ -f "$WORKDIR/mobile/termux/termux_app.py" ]; then
    cp "$WORKDIR/mobile/termux/termux_app.py" "$WORKSPACE/termux_app.py"
    echo "✓ termux_app.py updated"
fi

# Re-install scanner_fixer in case its pyproject.toml / dependencies changed
if [ -f "$WORKDIR/packages/scanner_fixer/pyproject.toml" ]; then
    pip install -e "$WORKDIR/packages/scanner_fixer" 2>/dev/null && \
        echo "✓ scanner_fixer reinstalled (editable)" || \
        echo "⚠ scanner_fixer reinstall failed — sys.path fallback will be used"
fi

echo "✅ Update complete. Run: omni-ocr"
UPDATE_EOF
    chmod +x "$BIN_DIR/omni-update"

    ok "Launchers installed: omni-ocr, omni-stop, omni-update (in ~/bin)"
}

# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
main() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     OmniMedical Suite — Termux Installer (Android ARM64)    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Mode selection
    MODE="${1:-auto}"
    if [ "$MODE" = "auto" ]; then
        echo "اختر وضع التثبيت:"
        echo "  1) Termux native (أسرع، يستخدم pkg مباشرة)"
        echo "  2) proot-distro Ubuntu ARM64 (أكثر توافقاً مع المشروع الأم)"
        echo "  3) Exit"
        read -rp "اختر [1/2/3]: " choice
        case "$choice" in
            1) MODE="native" ;;
            2) MODE="proot" ;;
            *) exit 0 ;;
        esac
    fi

    if [ "$MODE" = "native" ]; then
        install_termux_native
        setup_workspace
    elif [ "$MODE" = "proot" ]; then
        install_proot_ubuntu
        setup_workspace
    else
        err "Unknown mode: $MODE"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✅ التثبيت اكتمل بنجاح!                       ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "📋 الأوامر المتاحة:"
    echo -e "  ${CYAN}omni-ocr${NC}        يفتح Gradio UI على http://localhost:7860"
    echo -e "  ${CYAN}omni-stop${NC}       يوقف الخادم"
    echo -e "  ${CYAN}omni-update${NC}     يحدّث المشروع + Python packages"
    echo ""
    echo "🚀 للتشغيل:"
    echo -e "  ${CYAN}omni-ocr${NC}"
    echo ""
    echo "📱 افتح المتصفح على:"
    echo -e "  ${CYAN}http://localhost:7860${NC}"
    echo ""
    echo "💾 التصحيحات تُحفظ في:"
    echo -e "  ${CYAN}\$HOME/omni_workspace/corrections_db/${NC}"
    echo ""
    warn "إذا لم تجد الأوامر، شغّل: source ~/.bashrc"
}

main "$@"
