#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# install_mobile_pwa.sh — Full installer for OmniMedical PWA (Linux/Manjaro)
# ═══════════════════════════════════════════════════════════════════════════
# يثبّت خادم OmniMedical PWA كمستخدم systemd service:
#   - فحص pacman للاعتماديات النظامية (python, flask, إلخ)
#   - إنشاء Python venv في ~/.omni-mobile-venv
#   - تثبيت اعتماديات Python في الـ venv
#   - إنشاء systemd user service (omni-mobile-pwa.service)
#   - تشغيل الخدمة + تفعيلها عند تسجيل الدخول
#   - إنشاء اختصار سطح مكتب (.desktop)
#
# الاستخدام:
#   bash scripts/install_mobile_pwa.sh                  # تثبيت كامل
#   bash scripts/install_mobile_pwa.sh --port 8080      # منفذ مخصص
#   bash scripts/install_mobile_pwa.sh --skip-deps      # تخطي فحص pacman
#   bash scripts/install_mobile_pwa.sh --uninstall       # إزالة (يُوجّه لسكربت uninstall)
#
# Exit codes:
#   0 — نجاح
#   1 — خطأ في المتطلبات أو فشل التثبيت
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
    BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; NC=''
fi
log()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*" >&2; }
step() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

# ── Defaults ────────────────────────────────────────────────────────────────
SERVICE_NAME="omni-mobile-pwa"
VENV_DIR="${HOME}/.omni-mobile-venv"
INSTALL_PORT=5000
SKIP_DEPS=false
DO_UNINSTALL=false
DATA_DIR=""   # will be resolved from REPO_ROOT/data

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Parse CLI args ──────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --port)
            shift
            INSTALL_PORT="${1:?--port requires a value}"
            ;;
        --port=*)
            INSTALL_PORT="${arg#--port=}"
            ;;
        --skip-deps)
            SKIP_DEPS=true
            ;;
        --uninstall)
            DO_UNINSTALL=true
            ;;
        --help|-h)
            sed -n '1,/^set -euo/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            warn "وسيط غير معروف: $arg (تجاهل، جرّب --help)"
            ;;
    esac
    shift || true
done

# ── Redirect to uninstall script ───────────────────────────────────────────
if $DO_UNINSTALL; then
    if [ -f "${SCRIPT_DIR}/uninstall_mobile_pwa.sh" ]; then
        exec bash "${SCRIPT_DIR}/uninstall_mobile_pwa.sh" "$@"
    else
        err "uninstall_mobile_pwa.sh غير موجود في ${SCRIPT_DIR}"
        exit 1
    fi
fi

# ── Resolve data directory ─────────────────────────────────────────────────
DATA_DIR="${REPO_ROOT}/data"

step "مثبّت OmniMedical PWA — التثبيت الكامل"
log "REPO_ROOT : ${REPO_ROOT}"
log "VENV_DIR  : ${VENV_DIR}"
log "PORT      : ${INSTALL_PORT}"
log "DATA_DIR  : ${DATA_DIR}"

# ═══════════════════════════════════════════════════════════════════════════
# 1. فحص نظام التشغيل
# ═══════════════════════════════════════════════════════════════════════════
detect_platform() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)       echo "unknown" ;;
    esac
}
PLATFORM="$(detect_platform)"

if [ "$PLATFORM" != "linux" ]; then
    warn "هذا المثبّت مُحسَّن لـ Linux/Manjaro. أنت على: $(uname -s)"
    warn "ستُتابع العمليات المشتركة لكن systemd service قد لا يعمل."
fi

# ═══════════════════════════════════════════════════════════════════════════
# 2. فحص اعتماديات النظام (pacman/apt)
# ═══════════════════════════════════════════════════════════════════════════
check_system_deps() {
    step "فحص اعتماديات النظام"

    # Required Python version
    local python_cmd=""
    if command -v python3 &>/dev/null; then
        python_cmd="python3"
    elif command -v python &>/dev/null; then
        python_cmd="python"
    else
        python_cmd=""
    fi

    if [ -z "$python_cmd" ]; then
        err "Python 3 غير مثبت!"
        if command -v pacman &>/dev/null; then
            echo "  ثبّته: sudo pacman -S python python-pip"
        elif command -v apt-get &>/dev/null; then
            echo "  ثبّته: sudo apt install python3 python3-pip python3-venv"
        fi
        exit 1
    fi

    local py_version
    py_version="$($python_cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    log "Python: ${python_cmd} ${py_version}"

    # Check for python3-venv or equivalent
    if ! $python_cmd -c "import venv" 2>/dev/null; then
        err "وحدة venv غير متوفرة!"
        if command -v pacman &>/dev/null; then
            echo "  ثبّتها: sudo pacman -S python-virtualenv"
        elif command -v apt-get &>/dev/null; then
            echo "  ثبّتها: sudo apt install python3-venv"
        fi
        exit 1
    fi
    ok "وحدة venv متوفرة"

    # Check for systemd (needed for user service)
    if [ "$PLATFORM" = "linux" ]; then
        if command -v systemctl &>/dev/null; then
            ok "systemctl متوفر"
        else
            warn "systemctl غير متوفر — لن يُفعّل الـ service تلقائيًا"
            warn "يمكنك تشغيل الخادم يدويًا (انظر نهاية السكربت)"
        fi
    fi

    # Check for curl (used for health check)
    if command -v curl &>/dev/null; then
        ok "curl متوفر"
    else
        warn "curl غير متوفر — لن يُمكن فحص صحة الخادم بعد التثبيت"
    fi
}

if ! $SKIP_DEPS; then
    check_system_deps
else
    step "تخطّي فحص اعتماديات النظام (--skip-deps)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 3. إنشاء Python virtual environment
# ═══════════════════════════════════════════════════════════════════════════
setup_venv() {
    step "إعداد Python virtual environment"

    if [ -d "${VENV_DIR}" ] && [ -f "${VENV_DIR}/bin/python" ]; then
        log "venv موجود في ${VENV_DIR} — إعادة استخدام"
        # Upgrade pip in existing venv
        "${VENV_DIR}/bin/python" -m pip install --upgrade pip --quiet 2>/dev/null || true
    else
        log "إنشاء venv جديد في ${VENV_DIR}…"
        python3 -m venv "${VENV_DIR}" || python -m venv "${VENV_DIR}"
        "${VENV_DIR}/bin/python" -m pip install --upgrade pip --quiet 2>/dev/null || true
    fi
    ok "venv جاهز: ${VENV_DIR}"
    log "Python في venv: $(${VENV_DIR}/bin/python --version 2>&1)"
}

setup_venv

# ═══════════════════════════════════════════════════════════════════════════
# 4. تثبيت اعتماديات Python
# ═══════════════════════════════════════════════════════════════════════════
install_python_deps() {
    step "تثبيت اعتماديات Python"

    local pip_cmd="${VENV_DIR}/bin/pip"

    # Install core dependencies for the mobile server
    # These are the minimum packages needed to start the server successfully.
    # requirements.txt may contain many more packages; if full install fails,
    # these core deps guarantee the mobile server can at least boot.
    local deps=(
        "flask>=2.3"
        "Pillow>=9.0"
        "opencv-python-headless>=4.5"
        "pydantic>=2.0"
        "numpy>=1.21"
    )

    # Install from requirements.txt if it exists
    if [ -f "${REPO_ROOT}/requirements.txt" ]; then
        log "تثبيت من requirements.txt…"
        "$pip_cmd" install -r "${REPO_ROOT}/requirements.txt" --quiet 2>/dev/null || {
            warn "فشل تثبيت بعض الحزم من requirements.txt — تثبيت الأساسية فقط"
            for dep in "${deps[@]}"; do
                "$pip_cmd" install "$dep" --quiet 2>/dev/null || warn "تعذّر تثبيت: $dep"
            done
        }
    else
        log "تثبيت الاعتماديات الأساسية…"
        for dep in "${deps[@]}"; do
            "$pip_cmd" install "$dep" --quiet 2>/dev/null || warn "تعذّر تثبيت: $dep"
        done
    fi

    # Verify flask is available
    if "${VENV_DIR}/bin/python" -c "import flask" 2>/dev/null; then
        ok "Flask مُثبّت في الـ venv"
    else
        err "Flask غير متوفر في الـ venv — الخادم لن يعمل"
        exit 1
    fi
}

install_python_deps

# ═══════════════════════════════════════════════════════════════════════════
# 5. إنشاء systemd user service
# ═══════════════════════════════════════════════════════════════════════════
create_systemd_service() {
    step "إنشاء systemd user service"

    local systemd_dir="${HOME}/.config/systemd/user"
    mkdir -p "$systemd_dir"

    local service_file="${systemd_dir}/${SERVICE_NAME}.service"

    cat > "$service_file" << EOF
[Unit]
Description=OmniMedical Mobile PWA Server
After=network.target

[Service]
Type=simple
WorkingDirectory=${REPO_ROOT}
Environment=PYTHONPATH=${REPO_ROOT}
Environment=OMNI_MOBILE_DB_DIR=${DATA_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python -m packages.core.mobile.server --host 0.0.0.0 --port ${INSTALL_PORT}
Restart=on-failure
RestartSec=3
KillMode=mixed

[Install]
WantedBy=default.target
EOF

    ok "ملف الخدمة: ${service_file}"
    log "ExecStart: ${VENV_DIR}/bin/python -m packages.core.mobile.server --host 0.0.0.0 --port ${INSTALL_PORT}"

    # Reload systemd daemon (best-effort — may fail in containers)
    if command -v systemctl &>/dev/null; then
        systemctl --user daemon-reload 2>/dev/null || {
            warn "daemon-reload فشل (طبيعي في حاوية بدون DBUS) — لن يؤثر على التشغيل اليدوي"
        }
    fi
}

create_systemd_service

# ═══════════════════════════════════════════════════════════════════════════
# 6. تفعيل الخدمة (systemd --user enable --now)
# ═══════════════════════════════════════════════════════════════════════════
enable_service() {
    step "تفعيل الخدمة"

    if command -v systemctl &>/dev/null; then
        # Try enable+start
        if systemctl --user enable "${SERVICE_NAME}.service" 2>/dev/null; then
            ok "تم تفعيل الخدمة (enable)"
        else
            warn "تعذّر enable — جرّب يدويًا: systemctl --user enable ${SERVICE_NAME}.service"
        fi

        if systemctl --user start "${SERVICE_NAME}.service" 2>/dev/null; then
            ok "تم تشغيل الخدمة (start)"
        else
            warn "تعذّر start — جرّب يدويًا: systemctl --user start ${SERVICE_NAME}.service"
        fi
    else
        warn "systemctl غير متوفر — لن تُفعّل الخدمة تلقائيًا"
    fi
}

enable_service

# ═══════════════════════════════════════════════════════════════════════════
# 7. فحص صحة الخادم (health check)
# ═══════════════════════════════════════════════════════════════════════════
health_check() {
    step "فحص صحة الخادم"

    if ! command -v curl &>/dev/null; then
        warn "curl غير متوفر — تخطّي فحص الصحة"
        return 0
    fi

    local health_url="http://localhost:${INSTALL_PORT}/health"
    local max_attempts=15
    local attempt=1

    log "انتظار الخادم على ${health_url}…"

    while [ $attempt -le $max_attempts ]; do
        if curl -fsS -o /dev/null --max-time 3 "$health_url" 2>/dev/null; then
            local response
            response="$(curl -fsS --max-time 5 "$health_url" 2>/dev/null || echo '{}')"
            ok "الخادم يستجيب! استجابة /health:"
            echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
            return 0
        fi
        log "محاولة ${attempt}/${max_attempts} — الخادم لم يستجب بعد…"
        sleep 2
        attempt=$((attempt+1))
    done

    warn "الخادم لم يستجب خلال $((max_attempts * 2)) ثانية"
    warn "قد يكون قيد التشغيل — تحقّق يدويًا:"
    echo "  curl http://localhost:${INSTALL_PORT}/health"
    echo ""
    echo "  أو شغّل الخادم يدويًا:"
    echo "  ${VENV_DIR}/bin/python -m packages.core.mobile.server --host 0.0.0.0 --port ${INSTALL_PORT}"
}

# Try health check — but first start the server manually if systemd didn't work
# This handles the container case where systemd --user doesn't function
manual_start_if_needed() {
    # Check if something is already listening on the port
    if command -v curl &>/dev/null; then
        if curl -fsS -o /dev/null --max-time 2 "http://localhost:${INSTALL_PORT}/health" 2>/dev/null; then
            log "الخادم يعمل بالفعل على المنفذ ${INSTALL_PORT}"
            return 0
        fi
    fi

    # Try systemd status first
    local systemd_running=false
    if command -v systemctl &>/dev/null; then
        if systemctl --user is-active "${SERVICE_NAME}.service" &>/dev/null; then
            systemd_running=true
        fi
    fi

    if ! $systemd_running; then
        log "محاولة تشغيل الخادم يدويًا (systemd غير متوفر/غير فعّال في هذه البيئة)…"
        # Start the server in background
        OMNI_MOBILE_DB_DIR="${DATA_DIR}" PYTHONPATH="${REPO_ROOT}" PYTHONUNBUFFERED=1 \
            "${VENV_DIR}/bin/python" -m packages.core.mobile.server \
            --host 0.0.0.0 --port "${INSTALL_PORT}" &
        local server_pid=$!
        log "الخادم يعمل في الخلفية (PID: ${server_pid})"
        # Give it a moment to start
        sleep 3
    fi
}

manual_start_if_needed
health_check

# ═══════════════════════════════════════════════════════════════════════════
# 8. إنشاء اختصار سطح المكتب
# ═══════════════════════════════════════════════════════════════════════════
create_desktop_shortcut() {
    step "إنشاء اختصار سطح المكتب"

    local PWA_URL="http://localhost:${INSTALL_PORT}/mobile/ocr-review.html"

    # Find an icon
    local ICON_PATH="${REPO_ROOT}/packages/core/mobile/static/icon-512.png"
    if [ ! -f "$ICON_PATH" ]; then
        ICON_PATH="${REPO_ROOT}/mobile/android/assets/icon.png"
    fi
    if [ ! -f "$ICON_PATH" ]; then
        ICON_PATH="${HOME}/.local/share/icons/omni-medical-pwa.png"
        mkdir -p "$(dirname "$ICON_PATH")"
        if command -v python3 &>/dev/null; then
            python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (79, 70, 229, 255))
draw = ImageDraw.Draw(img)
draw.rectangle([98, 40, 158, 216], fill='white')
draw.rectangle([40, 98, 216, 158], fill='white')
img.save('${ICON_PATH}')
" 2>/dev/null || warn "PIL غير متوفر — سيُستخدم أيقونة افتراضية"
        fi
    fi

    # Find a browser for app mode
    local browser_cmd=""
    if command -v chromium &>/dev/null; then
        browser_cmd="chromium --app=${PWA_URL}"
    elif command -v chromium-browser &>/dev/null; then
        browser_cmd="chromium-browser --app=${PWA_URL}"
    elif command -v google-chrome &>/dev/null; then
        browser_cmd="google-chrome --app=${PWA_URL}"
    elif command -v brave-browser &>/dev/null; then
        browser_cmd="brave-browser --app=${PWA_URL}"
    elif command -v firefox &>/dev/null; then
        browser_cmd="firefox --ssb ${PWA_URL}"
    else
        browser_cmd="xdg-open ${PWA_URL}"
    fi

    # Desktop directory
    local DESKTOP_DIR="${XDG_DESKTOP_DIR:-}"
    if [ -z "$DESKTOP_DIR" ] || [ ! -d "$DESKTOP_DIR" ]; then
        DESKTOP_DIR="${HOME}/Desktop"
    fi
    if [ ! -d "$DESKTOP_DIR" ]; then
        mkdir -p "$DESKTOP_DIR" 2>/dev/null || DESKTOP_DIR="${HOME}"
    fi

    local desktop_file="${DESKTOP_DIR}/omni-medical-pwa.desktop"
    cat > "$desktop_file" << EOF
[Desktop Entry]
Type=Application
Name=OmniMedical PWA
Name[ar]=أومني مديكال
Comment=OmniMedical Progressive Web App
Comment[ar]=تطبيق الويب التقدّمي لأومني مديكال
Exec=${browser_cmd}
Icon=${ICON_PATH}
Terminal=false
Categories=Office;Medical;Utility;
Keywords=OCR;medical;PWA;mobile;Arabic;
StartupWMClass=omni-medical-pwa
EOF
    chmod +x "$desktop_file"
    ok "اختصار سطح المكتب: ${desktop_file}"

    # Also install to ~/.local/share/applications for launcher integration
    local apps_dir="${HOME}/.local/share/applications"
    mkdir -p "$apps_dir"
    cp "$desktop_file" "${apps_dir}/omni-medical-pwa.desktop"
    ok "مُثبّت في مشغّل التطبيقات: ${apps_dir}/omni-medical-pwa.desktop"

    # Refresh desktop database (best-effort)
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$apps_dir" 2>/dev/null || true
    fi
}

create_desktop_shortcut

# ═══════════════════════════════════════════════════════════════════════════
# 9. ملخص التثبيت
# ═══════════════════════════════════════════════════════════════════════════
step "اكتمل التثبيت"
echo ""
ok "ملخص التثبيت:"
echo "  ├── venv           : ${VENV_DIR}"
echo "  ├── data           : ${DATA_DIR}"
echo "  ├── port           : ${INSTALL_PORT}"
echo "  ├── service file   : ${HOME}/.config/systemd/user/${SERVICE_NAME}.service"
echo "  ├── desktop shortcut: ${HOME}/Desktop/omni-medical-pwa.desktop (أو حيثما كان سطح المكتب)"
echo "  └── health endpoint: http://localhost:${INSTALL_PORT}/health"
echo ""
echo "  أوامر systemd:"
echo "    systemctl --user status ${SERVICE_NAME}"
echo "    systemctl --user restart ${SERVICE_NAME}"
echo "    systemctl --user stop ${SERVICE_NAME}"
echo "    journalctl --user -u ${SERVICE_NAME} -f"
echo ""
echo "  لإزالة التثبيت:"
echo "    bash scripts/uninstall_mobile_pwa.sh"
echo "    bash scripts/uninstall_mobile_pwa.sh --purge-data   # حذف data/ أيضًا"
