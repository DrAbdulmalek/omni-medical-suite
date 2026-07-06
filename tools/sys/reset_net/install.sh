#!/bin/bash
# ============================================================
# install.sh — مُثبّت reset-net
# ينسخ السكربتات، يضبط الصلاحيات، ينشئ sudoers، يثبّت القائمة
# وأيقونة علبة النظام، الاستخدام: sudo bash install.sh
# ============================================================
set -eu

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}${BOLD}"
echo "══════════════════════════════════════════════════"
echo "  reset-net v1.3.0 — المُثبّت"
echo "══════════════════════════════════════════════════"
echo -e "${NC}"

# ── فحص الصلاحيات ──
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}يجب تشغيل المُثبّت بصلاحيات الجذر:${NC} sudo bash $0"
    exit 1
fi

CURRENT_USER="${SUDO_USER:-$USER}"
echo -e "المستخدم: ${BOLD}${CURRENT_USER}${NC}"
echo ""

# ── 1. نسخ السكربت الرئيسي ──
echo -e "${BOLD}[1/7] تثبيت السكربت الرئيسي...${NC}"
cp "${SCRIPT_DIR}/reset-net" /usr/local/bin/reset-net
chown root:root /usr/local/bin/reset-net
chmod 755 /usr/local/bin/reset-net
echo -e "  ${GREEN}/usr/local/bin/reset-net${NC}"

# ── 2. نسخ واجهة GUI ──
echo -e "${BOLD}[2/7] تثبيت واجهة GUI...${NC}"
cp "${SCRIPT_DIR}/reset-net-gui" /usr/local/bin/reset-net-gui
chown root:root /usr/local/bin/reset-net-gui
chmod 755 /usr/local/bin/reset-net-gui
echo -e "  ${GREEN}/usr/local/bin/reset-net-gui${NC}"

# ── 3. تثبيت ملف .desktop ──
echo -e "${BOLD}[3/7] تثبيت ملف القائمة...${NC}"
cp "${SCRIPT_DIR}/com.drabdulmalek.reset-net.desktop" /usr/share/applications/
chmod 644 /usr/share/applications/com.drabdulmalek.reset-net.desktop
update-desktop-database /usr/share/applications/ 2>/dev/null || true
echo -e "  ${GREEN}أُضيف إلى قائمة التطبيقات${NC}"

# ── 4. تثبيت سياسة Polkit ──
echo -e "${BOLD}[4/7] تثبيت سياسة Polkit...${NC}"
cp "${SCRIPT_DIR}/com.drabdulmalek.reset-net.policy" /usr/share/polkit-1/actions/
chmod 644 /usr/share/polkit-1/actions/com.drabdulmalek.reset-net.policy
echo -e "  ${GREEN}تم تثبيت سياسة المصادقة${NC}"

# ── 5. إعداد sudoers (NOPASSWD) ──
echo -e "${BOLD}[5/7] إعداد sudoers...${NC}"
SUDOERS_FILE="/etc/sudoers.d/reset-net"
if [[ ! -f "$SUDOERS_FILE" ]] || ! grep -q "reset-net" "$SUDOERS_FILE" 2>/dev/null; then
    echo "${CURRENT_USER} ALL=(root) NOPASSWD: /usr/local/bin/reset-net" > "$SUDOERS_FILE"
    chmod 440 "$SUDOERS_FILE"
    echo -e "  ${GREEN}تم إنشاء ${SUDOERS_FILE}${NC}"
else
    echo -e "  ${YELLOW}sudoers مُعد مسبقاً${NC}"
fi

# ── 6. تثبيت أيقونة علبة النظام + التشغيل التلقائي ──
echo -e "${BOLD}[6/7] تثبيت أيقونة علبة النظام...${NC}"
if [[ -f "${SCRIPT_DIR}/reset-net-tray" ]]; then
    cp "${SCRIPT_DIR}/reset-net-tray" /usr/local/bin/reset-net-tray
    chown root:root /usr/local/bin/reset-net-tray
    chmod 755 /usr/local/bin/reset-net-tray
    echo -e "  ${GREEN}/usr/local/bin/reset-net-tray${NC}"

    mkdir -p /etc/xdg/autostart
    cp "${SCRIPT_DIR}/reset-net-tray.desktop" /etc/xdg/autostart/reset-net-tray.desktop
    chmod 644 /etc/xdg/autostart/reset-net-tray.desktop
    echo -e "  ${GREEN}سيبدأ تلقائياً عند تسجيل الدخول (لكل المستخدمين)${NC}"

    if ! /usr/bin/command -v yad &>/dev/null; then
        echo -e "  ${YELLOW}تنبيه: الحزمة yad غير مثبتة — الأيقونة لن تعمل حتى تُثبّتها:${NC}"
        echo -e "  ${YELLOW}sudo pacman -S yad${NC}"
    fi
else
    echo -e "  ${YELLOW}تخطّي: reset-net-tray غير موجود في المستودع${NC}"
fi

# ── 7. إعادة تحديث قاعدة بيانات التطبيقات ──
echo -e "${BOLD}[7/7] تحديث النظام...${NC}"
if [[ -x /usr/bin/kbuildsycoca6 ]]; then
    su - "${CURRENT_USER}" -c "/usr/bin/kbuildsycoca6" 2>/dev/null || true
fi
systemctl daemon-reload 2>/dev/null || true

echo ""
echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  تم التثبيت بنجاح!${NC}"
echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BOLD}طرق الاستخدام:${NC}"
echo ""
echo -e "  ${CYAN}1. من الطرفية:${NC}"
echo -e "     ${GREEN}reset-net${NC}"
echo ""
echo -e "  ${CYAN}2. من قائمة التطبيقات (الرسومية):${NC}"
echo -e "     ابحث عن ${GREEN}\"Reset Network\"${NC} أو ${GREEN}\"إعادة ضبط الشبكة\"${NC}"
echo ""
echo -e "  ${CYAN}3. أيقونة علبة النظام (الأسهل):${NC}"
echo -e "     ستظهر تلقائياً بعد إعادة تسجيل الدخول — انقر مرتين لإعادة الضبط"
echo -e "     أو شغّلها الآن يدوياً: ${GREEN}reset-net-tray &${NC}"
echo ""
echo -e "${YELLOW}ملاحظة: التثبيت الرسومي يطلب كلمة مرور مرة واحدة فقط عبر Polkit.${NC}"
