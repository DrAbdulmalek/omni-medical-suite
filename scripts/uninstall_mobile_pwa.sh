#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# uninstall_mobile_pwa.sh — Remove OmniMedical PWA shortcuts/icons
# ═══════════════════════════════════════════════════════════════════════════
# يزيل أي اختصارات وأيقونات أنشأها install_mobile_pwa.sh.
#
# الاستخدام:
#   bash scripts/uninstall_mobile_pwa.sh             # إزالة فقط
#   bash scripts/uninstall_mobile_pwa.sh --purge     # إزالة + حذف أيقونة مولّدة
#   bash scripts/uninstall_mobile_pwa.sh --adb        # إزالة WebAPK من أندرويد موصول
#
# ملاحظة: لا يحذف المستودع أو خادم mobile — فقط الاختصارات.
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
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*" >&2; }
step() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

# ── Args ────────────────────────────────────────────────────────────────────
PURGE=false
DO_ADB=false
for arg in "$@"; do
    case "$arg" in
        --purge) PURGE=true ;;
        --adb)   DO_ADB=true ;;
        --help|-h)
            sed -n '1,/^set -euo/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) warn "Unknown arg: $arg (ignored)" ;;
    esac
done

# ── Detect platform ────────────────────────────────────────────────────────
detect_platform() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)       echo "unknown" ;;
    esac
}
PLATFORM="$(detect_platform)"
log "Platform: ${PLATFORM}"

# ── Desktop dir locator (mirror of install script) ─────────────────────────
desktop_dir() {
    case "$PLATFORM" in
        linux)
            local xdg="${XDG_DESKTOP_DIR:-}"
            if [ -n "$xdg" ] && [ -d "$xdg" ]; then echo "$xdg"
            elif [ -d "${HOME}/Desktop" ]; then echo "${HOME}/Desktop"
            else echo "${HOME}"; fi
            ;;
        macos)   echo "${HOME}/Desktop" ;;
        windows) echo "${USERPROFILE:-${HOME}}/Desktop" ;;
        *)       echo "${HOME}" ;;
    esac
}

# ── Linux uninstall ────────────────────────────────────────────────────────
uninstall_linux() {
    step "إزالة اختصارات Linux"
    local desktop; desktop="$(desktop_dir)"
    local apps_dir="${HOME}/.local/share/applications"
    local removed=0

    for f in \
        "${desktop}/omni-medical-pwa.desktop" \
        "${apps_dir}/omni-medical-pwa.desktop"; do
        if [ -f "$f" ]; then
            rm -f "$f"
            ok "Removed: $f"
            removed=$((removed+1))
        fi
    done

    if command -v xdg-desktop-icon &>/dev/null; then
        xdg-desktop-icon uninstall "${desktop}/omni-medical-pwa.desktop" 2>/dev/null || true
    fi
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$apps_dir" 2>/dev/null || true
    fi

    if $PURGE; then
        local icon="${HOME}/.local/share/icons/omni-medical-pwa.png"
        if [ -f "$icon" ]; then
            rm -f "$icon"
            ok "Purged generated icon: $icon"
            removed=$((removed+1))
        fi
    fi

    if [ "$removed" -eq 0 ]; then
        warn "لم يُعثر على اختصارات — لا شيء للإزالة"
    else
        ok "تمت إزالة ${removed} عنصر"
    fi
}

# ── macOS uninstall ────────────────────────────────────────────────────────
uninstall_macos() {
    step "إزالة اختصارات macOS"
    local desktop; desktop="$(desktop_dir)"
    local removed=0
    for f in \
        "${desktop}/OmniMedical PWA.webloc" \
        "${desktop}/OmniMedical PWA" \
        "${desktop}/OmniMedical PWA.applescript"; do
        if [ -e "$f" ]; then
            rm -rf "$f"
            ok "Removed: $f"
            removed=$((removed+1))
        fi
    done
    if [ "$removed" -eq 0 ]; then
        warn "لم يُعثر على اختصارات — لا شيء للإزالة"
    else
        ok "تمت إزالة ${removed} عنصر"
    fi
}

# ── Windows uninstall ──────────────────────────────────────────────────────
uninstall_windows() {
    step "إزالة اختصارات Windows"
    local desktop; desktop="$(desktop_dir)"
    local removed=0
    for f in \
        "${desktop}/OmniMedical PWA.url" \
        "${desktop}/OmniMedical PWA.lnk"; do
        if [ -e "$f" ]; then
            rm -f "$f"
            ok "Removed: $f"
            removed=$((removed+1))
        fi
    done
    if [ "$removed" -eq 0 ]; then
        warn "لم يُعثر على اختصارات — لا شيء للإزالة"
    else
        ok "تمت إزالة ${removed} عنصر"
    fi
}

# ── Android WebAPK uninstall via adb ───────────────────────────────────────
uninstall_android_webapk() {
    step "إزالة WebAPK من أندرويد عبر adb"
    if ! command -v adb &>/dev/null; then
        err "adb غير مثبت"
        exit 1
    fi
    local devices
    devices="$(adb devices 2>/dev/null | grep -E '^[0-9A-Za-z]+\s+device$' || true)"
    if [ -z "$devices" ]; then
        err "لا يوجد جهاز أندرويد موصول"
        adb devices
        exit 1
    fi
    ok "تم اكتشاف جهاز أندرويد"

    # WebAPK package names follow: com.google.android.webapk.<hash>
    # We list packages and uninstall ones matching our origin.
    log "البحث عن WebAPKs مثبتة من Chrome…"
    local webapks
    webapks="$(adb shell pm list packages 'webapk' 2>/dev/null || true)"
    if [ -z "$webapks" ]; then
        warn "لا توجد WebAPKs مثبتة عبر Chrome"
        return 0
    fi

    log "WebAPKs المثبتة:"
    echo "$webapks"
    echo ""
    warn "لا يمكن تحديد أي WebAPK يخص OmniMedical تلقائيًا (أسماؤها مجزّأة)."
    echo "  للحذف يدويًا على الجهاز:"
    echo "    الإعدادات → التطبيقات → ابحث عن \"OmniFile\" أو \"OmniMedical\" → إلغاء التثبيت"
    echo ""
    echo "  أو للحذف عبر adb (استبدل الحزمة):"
    echo "$webapks" | sed 's/^package:/    adb uninstall /'
}

# ── Main ────────────────────────────────────────────────────────────────────
step "إزالة OmniMedical PWA"

case "$PLATFORM" in
    linux)   uninstall_linux ;;
    macos)   uninstall_macos ;;
    windows) uninstall_windows ;;
    *)
        err "نظام غير مدعوم: $(uname -s)"
        exit 2
        ;;
esac

if $DO_ADB; then
    uninstall_android_webapk
fi

step "اكتملت الإزالة"
ok "تم تنظيف اختصارات OmniMedical PWA"
