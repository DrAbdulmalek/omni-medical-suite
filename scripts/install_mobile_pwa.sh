#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# install_mobile_pwa.sh — Install / register the OmniMedical PWA on desktop
# ═══════════════════════════════════════════════════════════════════════════
# يثبّت تطبيق الويب التقدّمي (PWA) الخاص بـ OmniMedical على Linux/macOS/Windows
# عبر إنشاء اختصار سطح مكتب + (اختياريًا) تسجيل WebAPK على أندرويد عبر adb.
#
# الاستخدام:
#   bash scripts/install_mobile_pwa.sh                  # تثبيت محلي على سطح المكتب
#   bash scripts/install_mobile_pwa.sh --url http://192.168.1.10:8000
#   bash scripts/install_mobile_pwa.sh --adb             # محاولة WebAPK على أندرويد موصول بـ adb
#   bash scripts/install_mobile_pwa.sh --uninstall       # إزالة الاختصارات
#
# المتطلبات:
#   - Python 3.9+ لتشغيل خادم mobile (انظر packages/core/mobile/server.py)
#   - على Linux: xdg-desktop-icon (من desktop-file-utils) — اختياري
#   - على macOS: osascript
#   - على Windows (Git Bash): يُكتب اختصار .url في Desktop
#   - لخيار --adb: adb ضمن PATH وجهاز أندرويد موصول
#
# Exit codes:
#   0 — نجاح
#   1 — خطأ في المتطلبات أو فشل التثبيت
#   2 — غير مدعوم على هذا النظام
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

# ── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_URL="http://localhost:8000/mobile/ocr-review.html"
PWA_URL="${OMNI_PWA_URL:-${DEFAULT_URL}}"
APP_NAME="OmniMedical PWA"
APP_NAME_AR="أومني مديكال"
DO_ADB=false
UNINSTALL=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Parse CLI args ──────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --url)
            shift
            PWA_URL="${1:?--url requires a value}"
            ;;
        --url=*)
            PWA_URL="${arg#--url=}"
            ;;
        --adb)
            DO_ADB=true
            ;;
        --uninstall)
            UNINSTALL=true
            ;;
        --help|-h)
            sed -n '1,/^set -euo/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            warn "Unknown arg: $arg (ignored, try --help)"
            ;;
    esac
    shift || true
done

# ── Detect platform ─────────────────────────────────────────────────────────
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
log "PWA URL : ${PWA_URL}"

# ── Locate desktop directory ────────────────────────────────────────────────
desktop_dir() {
    case "$PLATFORM" in
        linux)
            # Respect XDG, fallback to ~/Desktop
            xdg_user_dir="${XDG_DESKTOP_DIR:-}"
            if [ -n "$xdg_user_dir" ] && [ -d "$xdg_user_dir" ]; then
                echo "$xdg_user_dir"
            elif [ -d "${HOME}/Desktop" ]; then
                echo "${HOME}/Desktop"
            else
                # Create it if missing (some minimal WMs)
                mkdir -p "${HOME}/Desktop" 2>/dev/null || true
                echo "${HOME}/Desktop"
            fi
            ;;
        macos)
            echo "${HOME}/Desktop"
            ;;
        windows)
            # Git Bash: USERPROFILE\\Desktop
            echo "${USERPROFILE:-${HOME}}/Desktop"
            ;;
        *)
            echo "${HOME}"
            ;;
    esac
}

# ── Uninstall path ──────────────────────────────────────────────────────────
do_uninstall() {
    step "إزالة اختصارات OmniMedical PWA"
    DESKTOP="$(desktop_dir)"
    local removed=0

    # Linux .desktop file
    if [ "$PLATFORM" = "linux" ]; then
        for f in \
            "${DESKTOP}/omni-medical-pwa.desktop" \
            "${HOME}/.local/share/applications/omni-medical-pwa.desktop"; do
            if [ -f "$f" ]; then
                rm -f "$f"
                ok "Removed: $f"
                removed=$((removed+1))
            fi
        done
        # Try xdg-desktop-icon uninstall (best-effort, ignore errors)
        if command -v xdg-desktop-icon &>/dev/null; then
            xdg-desktop-icon uninstall "$DESKTOP/omni-medical-pwa.desktop" 2>/dev/null || true
        fi
    elif [ "$PLATFORM" = "macos" ]; then
        for f in \
            "${DESKTOP}/OmniMedical PWA" \
            "${DESKTOP}/OmniMedical PWA.applescript"; do
            if [ -e "$f" ]; then
                rm -rf "$f"
                ok "Removed: $f"
                removed=$((removed+1))
            fi
        done
    elif [ "$PLATFORM" = "windows" ]; then
        for f in \
            "${DESKTOP}/OmniMedical PWA.url" \
            "${DESKTOP}/OmniMedical PWA.lnk"; do
            if [ -e "$f" ]; then
                rm -f "$f"
                ok "Removed: $f"
                removed=$((removed+1))
            fi
        done
    fi

    if [ "$removed" -eq 0 ]; then
        warn "لم يُعثر على اختصارات سابقة — لا شيء للإزالة"
    else
        ok "تمت إزالة ${removed} اختصار/اختصارات"
    fi
    exit 0
}

if $UNINSTALL; then
    do_uninstall
fi

# ── Sanity: warn if PWA server may not be running ───────────────────────────
check_url_reachable() {
    local url="$1"
    if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
        warn "تعذّر فحص توافر URL (curl/wget غير مثبت)"
        return 0
    fi
    if command -v curl &>/dev/null; then
        if curl -fsS -o /dev/null --max-time 5 "$url" 2>/dev/null; then
            ok "الخادم يستجيب على: $url"
            return 0
        fi
    else
        if wget -q -O /dev/null --timeout=5 "$url" 2>/dev/null; then
            ok "الخادم يستجيب على: $url"
            return 0
        fi
    fi
    warn "تعذّر الوصول إلى $url — تأكد أن خادم mobile يعمل"
    warn "  شغّله: cd packages/core/mobile && python server.py"
    return 0
}

# ── Linux installer (.desktop file) ─────────────────────────────────────────
install_linux() {
    step "تثبيت اختصار سطح المكتب على Linux"
    DESKTOP="$(desktop_dir)"

    # Find an icon: prefer repo icon, fallback to a generated one
    ICON_PATH="${REPO_ROOT}/packages/core/mobile/static/icon-512.png"
    if [ ! -f "$ICON_PATH" ]; then
        ICON_PATH="${REPO_ROOT}/mobile/android/assets/icon.png"
    fi
    if [ ! -f "$ICON_PATH" ]; then
        # Generate a 256x256 placeholder so the .desktop file has a valid icon
        ICON_PATH="${HOME}/.local/share/icons/omni-medical-pwa.png"
        mkdir -p "$(dirname "$ICON_PATH")"
        if command -v python3 &>/dev/null; then
            python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (79, 70, 229, 255))
draw = ImageDraw.Draw(img)
draw.rectangle([98, 40, 158, 216], fill='white')
draw.rectangle([40, 98, 216, 158], fill='white')
img.save('$ICON_PATH')
" 2>/dev/null || warn "PIL غير متوفر — سيُستخدم أيقونة افتراضية"
        fi
    fi

    # Find a browser to launch the PWA in app mode
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
        # Firefox has no --app flag; use a profile-window
        browser_cmd="firefox --ssb ${PWA_URL}"
    else
        warn "لم يُعثر على متصفح مدعوم — سيستخدم xdg-open"
        browser_cmd="xdg-open ${PWA_URL}"
    fi

    local desktop_file="${DESKTOP}/omni-medical-pwa.desktop"
    cat > "$desktop_file" << EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Name[ar]=${APP_NAME_AR}
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
    ok "Created: $desktop_file"

    # Mirror into ~/.local/share/applications for launcher integration
    local apps_dir="${HOME}/.local/share/applications"
    mkdir -p "$apps_dir"
    cp "$desktop_file" "$apps_dir/omni-medical-pwa.desktop"
    ok "Installed to: $apps_dir/omni-medical-pwa.desktop"

    # Refresh desktop database (best-effort)
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$apps_dir" 2>/dev/null || true
    fi

    # Try xdg-desktop-icon install (works on some distros)
    if command -v xdg-desktop-icon &>/dev/null; then
        xdg-desktop-icon install "$desktop_file" 2>/dev/null || true
    fi
}

# ── macOS installer (AppleScript wrapper) ───────────────────────────────────
install_macos() {
    step "تثبيت اختصار سطح المكتب على macOS"
    DESKTOP="$(desktop_dir)"

    # Use a .webloc file (simplest, works with default browser in app mode)
    local webloc="${DESKTOP}/OmniMedical PWA.webloc"
    # webloc is a binary plist; easier: write as XML plist via python or plutil
    cat > "$webloc" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>URL</key>
    <string>__PWA_URL__</string>
</dict>
</plist>
EOF
    # Substitute the URL
    if command -v sed &>/dev/null; then
        # Use a delimiter unlikely to be in URL
        sed -i.bak "s|__PWA_URL__|${PWA_URL}|g" "$webloc" && rm -f "${webloc}.bak"
    fi
    ok "Created: $webloc"
    warn "للحصول على وضع تطبيق مستقل (SSB): استخدم Chrome → Install OmniMedical PWA…"
}

# ── Windows installer (.url shortcut via Git Bash) ──────────────────────────
install_windows() {
    step "تثبيت اختصار سطح المكتب على Windows"
    DESKTOP="$(desktop_dir)"

    local url_file="${DESKTOP}/OmniMedical PWA.url"
    cat > "$url_file" << EOF
[InternetShortcut]
URL=${PWA_URL}
IconFile=$(cygpath -w "${REPO_ROOT}/packages/core/mobile/static/icon-512.png" 2>/dev/null || echo "")
IconIndex=0
EOF
    ok "Created: $url_file"
    warn "لوضع تطبيق مستقل: افتح Edge/Chrome → … → Apps → Install this site as an app"
}

# ── Android WebAPK via adb (optional) ──────────────────────────────────────
install_android_webapk() {
    step "محاولة تثبيت WebAPK على أندرويد عبر adb"

    if ! command -v adb &>/dev/null; then
        err "adb غير مثبت على هذا النظام"
        echo "  ثبّته:"
        echo "    Linux : sudo apt install adb  /  pacman -S android-tools"
        echo "    macOS : brew install android-platform-tools"
        echo "    Win   : تنزيل platform-tools من developer.android.com"
        exit 1
    fi

    # Check device
    local devices
    devices="$(adb devices 2>/dev/null | grep -E '^[0-9A-Za-z]+\s+device$' || true)"
    if [ -z "$devices" ]; then
        err "لا يوجد جهاز أندرويد موصول"
        echo "  تأكد أن:"
        echo "    1. USB debugging مُفعّل في إعدادات المطور"
        echo "    2. الجهاز موصول بكابل USB ومُصرّح عليه"
        echo "  ثم أعد تشغيل هذا السكربت مع --adb"
        adb devices
        exit 1
    fi
    ok "تم اكتشاف جهاز أندرويد"

    # Trigger Chrome's WebAPK install via an intent.
    # Chrome 117+ supports the webapp install intent.
    local manifest_url="${PWA_URL%/mobile/*}/mobile/manifest.json"
    # Resolve to absolute URL if relative
    case "$manifest_url" in
        http*) : ;;
        *) manifest_url="${PWA_URL}/${manifest_url}" ;;
    esac

    log "إرسال intent لتثبيت PWA…"
    # Open the PWA URL in Chrome; the user will then use "Add to Home Screen"
    # We also send the install-bound intent URL for WebAPK.
    adb shell am start \
        -a android.intent.action.VIEW \
        -d "${PWA_URL}" \
        -n com.android.chrome/com.google.android.apps.chrome.Main 2>/dev/null \
        || adb shell am start -a android.intent.action.VIEW -d "${PWA_URL}"

    ok "تم فتح Chrome على الجهاز"
    echo ""
    echo "  على الجهاز:"
    echo "    1. افتح قائمة Chrome (⋮)"
    echo "    2. اختر \"Add to Home screen\" / \"إضافة إلى الشاشة الرئيسية\""
    echo "    3. سيُثبَّت WebAPK بشكل مستقل (أيقونة + إشعارات + وضع standalone)"
    echo ""
    warn "إذا لم يظهر الخيار: تأكد أن manifest.json يُخدَّم من نفس نطاق PWA_URL"
}

# ── Main ────────────────────────────────────────────────────────────────────
step "تثبيت OmniMedical PWA"
log "URL: ${PWA_URL}"

check_url_reachable "$PWA_URL"

case "$PLATFORM" in
    linux)  install_linux ;;
    macos)  install_macos ;;
    windows) install_windows ;;
    *)
        err "نظام غير مدعوم: $(uname -s)"
        exit 2
        ;;
esac

if $DO_ADB; then
    install_android_webapk
fi

step "اكتمل التثبيت"
ok "يمكنك الآن فتح OmniMedical PWA من سطح المكتب"
echo ""
echo "  للتشغيل في وضع تطبيق مستقل (recommended):"
echo "    افتح Chrome/Edge → قائمة (⋮) → \"Install OmniMedical PWA…\""
echo ""
echo "  لإزالة الاختصارات لاحقًا:"
echo "    bash scripts/install_mobile_pwa.sh --uninstall"
echo ""
