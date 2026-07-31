#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# uninstall_mobile_pwa.sh — Uninstall OmniMedical PWA service + shortcuts
# ═══════════════════════════════════════════════════════════════════════════
# يزيل تثبيت OmniMedical PWA بالكامل:
#   - إيقاف وتعطيل systemd user service
#   - حذف ملف الخدمة + venv
#   - حذف اختصارات سطح المكتب
#   - افتراضياً: يحفظ data/ (قاعدة البيانات والتعلم)
#   - مع --purge-data: يحذف data/ أيضًا (بعد تأكيد)
#
# الاستخدام:
#   bash scripts/uninstall_mobile_pwa.sh                # إزالة مع حفظ data/
#   bash scripts/uninstall_mobile_pwa.sh --purge-data   # إزالة + حذف data/
#   bash scripts/uninstall_mobile_pwa.sh --yes          # تخطّي التأكيدات التفاعلية
#
# Exit codes:
#   0 — نجاح
#   1 — خطأ
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
PURGE_DATA=false
AUTO_YES=false
DATA_DIR=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data"

# ── Parse CLI args ──────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --purge-data)
            PURGE_DATA=true
            ;;
        --yes|-y)
            AUTO_YES=true
            ;;
        --help|-h)
            sed -n '1,/^set -euo/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            warn "وسيط غير معروف: $arg (تجاهل)"
            ;;
    esac
done

step "إزالة تثبيت OmniMedical PWA"

# ── Confirmation ────────────────────────────────────────────────────────────
confirm_action() {
    local message="$1"
    if $AUTO_YES; then
        return 0
    fi
    echo ""
    echo -e "${YELLOW}⚠ ${message}${NC}"
    read -r -p "أمتأكد؟ (yes/N): " response
    case "$response" in
        [yY][eE][sS]) return 0 ;;
        *) echo "أُلغِيَت العملية."; exit 0 ;;
    esac
}

if $PURGE_DATA; then
    echo ""
    echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  تحذير: سيتم حذف data/ بشكل دائم!${NC}"
    echo -e "${RED}  هذا يشمل قاعدة البيانات ونماذج التعلم والتصحيحات.${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
    confirm_action "اكتب YES (بحروف كبيرة) لحذف data/:"
    # Second confirmation for data purge (must type YES in capitals)
    if ! $AUTO_YES; then
        read -r -p "اكتب YES (بحروف كبيرة) للتأكيد النهائي: " final_confirm
        if [ "$final_confirm" != "YES" ]; then
            echo "أُلغِيَ حذف data/. سيتم الإزالة مع حفظ data/."
            PURGE_DATA=false
        fi
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# 1. إيقاف systemd service
# ═══════════════════════════════════════════════════════════════════════════
stop_service() {
    step "إيقاف الخدمة"

    if ! command -v systemctl &>/dev/null; then
        warn "systemctl غير متوفر — تخطّي إيقاف الخدمة"
        # Try to kill any running server process manually
        local pids
        pids="$(pgrep -f "packages.core.mobile.server" 2>/dev/null || true)"
        if [ -n "$pids" ]; then
            log "عمليات خادم قيد التشغيل: $pids"
            for pid in $pids; do
                kill "$pid" 2>/dev/null && ok "أُوقِفت العملية $pid" || warn "تعذّر إيقاف العملية $pid"
            done
        else
            log "لا توجد عمليات خادم قيد التشغيل"
        fi
        return 0
    fi

    # Stop the service
    if systemctl --user is-active "${SERVICE_NAME}.service" &>/dev/null; then
        systemctl --user stop "${SERVICE_NAME}.service" 2>/dev/null && ok "تم إيقاف الخدمة" || warn "تعذّر إيقاف الخدمة"
    else
        log "الخدمة غير نشطة أصلاً"
    fi

    # Disable the service
    if systemctl --user is-enabled "${SERVICE_NAME}.service" &>/dev/null; then
        systemctl --user disable "${SERVICE_NAME}.service" 2>/dev/null && ok "تم تعطيل الخدمة" || warn "تعذّر تعطيل الخدمة"
    else
        log "الخدمة غير مفعّلة أصلاً"
    fi

    # Also kill any lingering processes (manual launches)
    local pids
    pids="$(pgrep -f "packages.core.mobile.server" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
        for pid in $pids; do
            kill "$pid" 2>/dev/null || true
        done
        ok "أُوقِفت العمليات المتبقية: $pids"
    fi
}

stop_service

# ═══════════════════════════════════════════════════════════════════════════
# 2. حذف ملف الخدمة
# ═══════════════════════════════════════════════════════════════════════════
remove_service_file() {
    step "حذف ملف الخدمة"

    local service_file="${HOME}/.config/systemd/user/${SERVICE_NAME}.service"
    if [ -f "$service_file" ]; then
        rm -f "$service_file"
        ok "حُذف: ${service_file}"

        # Reload systemd daemon (best-effort)
        if command -v systemctl &>/dev/null; then
            systemctl --user daemon-reload 2>/dev/null || true
        fi
    else
        log "ملف الخدمة غير موجود — تخطّي"
    fi
}

remove_service_file

# ═══════════════════════════════════════════════════════════════════════════
# 3. حذف virtual environment
# ═══════════════════════════════════════════════════════════════════════════
remove_venv() {
    step "حذف virtual environment"

    if [ -d "${VENV_DIR}" ]; then
        rm -rf "${VENV_DIR}"
        ok "حُذف: ${VENV_DIR}"
    else
        log "venv غير موجود — تخطّي"
    fi
}

remove_venv

# ═══════════════════════════════════════════════════════════════════════════
# 4. حذف اختصارات سطح المكتب
# ═══════════════════════════════════════════════════════════════════════════
remove_shortcuts() {
    step "حذف اختصارات سطح المكتب"

    local removed=0

    # Desktop directory
    local DESKTOP_DIR="${XDG_DESKTOP_DIR:-}"
    if [ -z "$DESKTOP_DIR" ] || [ ! -d "$DESKTOP_DIR" ]; then
        DESKTOP_DIR="${HOME}/Desktop"
    fi

    # Linux .desktop file
    for f in \
        "${DESKTOP_DIR}/omni-medical-pwa.desktop" \
        "${HOME}/.local/share/applications/omni-medical-pwa.desktop"; do
        if [ -f "$f" ]; then
            rm -f "$f"
            ok "حُذف: $f"
            removed=$((removed+1))
        fi
    done

    # Generated icon
    local icon="${HOME}/.local/share/icons/omni-medical-pwa.png"
    if [ -f "$icon" ]; then
        rm -f "$icon"
        ok "حُذفت الأيقونة المولّدة: $icon"
        removed=$((removed+1))
    fi

    # Try xdg-desktop-icon uninstall (best-effort)
    if command -v xdg-desktop-icon &>/dev/null; then
        xdg-desktop-icon uninstall "${DESKTOP_DIR}/omni-medical-pwa.desktop" 2>/dev/null || true
    fi

    # Refresh desktop database (best-effort)
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
    fi

    if [ "$removed" -eq 0 ]; then
        log "لم يُعثر على اختصارات — تخطّي"
    else
        ok "حُذف ${removed} اختصار/عنصر"
    fi
}

remove_shortcuts

# ═══════════════════════════════════════════════════════════════════════════
# 5. حذف data/ (اختياري — مع --purge-data فقط)
# ═══════════════════════════════════════════════════════════════════════════
purge_data() {
    if ! $PURGE_DATA; then
        step "حفظ data/"
        if [ -d "${DATA_DIR}" ]; then
            ok "data/ محفوظة في: ${DATA_DIR}"
            log "لحذفها يدويًا لاحقًا: rm -rf ${DATA_DIR}"
        else
            log "data/ غير موجودة — تخطّي"
        fi
        return 0
    fi

    step "حذف data/ (--purge-data)"
    if [ -d "${DATA_DIR}" ]; then
        rm -rf "${DATA_DIR}"
        ok "حُذفت: ${DATA_DIR}"
    else
        log "data/ غير موجودة — تخطّي"
    fi
}

purge_data

# ═══════════════════════════════════════════════════════════════════════════
# 6. ملخص الإزالة
# ═══════════════════════════════════════════════════════════════════════════
step "اكتملت الإزالة"
echo ""
ok "تم تنظيف:"
echo "  ├── systemd service  : أُوقِف + حُذف"
echo "  ├── venv             : حُذف (${VENV_DIR})"
echo "  ├── desktop shortcuts: حُذفت"
if $PURGE_DATA; then
    echo "  └── data/            : حُذفت (--purge-data)"
else
    echo "  └── data/            : محفوظة (${DATA_DIR})"
fi
echo ""
echo "  لإعادة التثبيت:"
echo "    bash scripts/install_mobile_pwa.sh"
