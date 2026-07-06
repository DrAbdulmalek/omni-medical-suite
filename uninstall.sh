#!/bin/bash
# ============================================================
# uninstall.sh — إلغاء تثبيت reset-net
# الاستخدام: sudo bash uninstall.sh
# ============================================================
set -eu

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}يجب تشغيل المُثبّت بصلاحيات الجذر:${NC} sudo bash $0"
    exit 1
fi

echo -e "${BOLD}إلغاء تثبيت reset-net...${NC}"

pkill -f /usr/local/bin/reset-net-tray 2>/dev/null || true

rm -f /usr/local/bin/reset-net
rm -f /usr/local/bin/reset-net-gui
rm -f /usr/local/bin/reset-net-tray
rm -f /usr/share/applications/com.drabdulmalek.reset-net.desktop
rm -f /usr/share/polkit-1/actions/com.drabdulmalek.reset-net.policy
rm -f /etc/xdg/autostart/reset-net-tray.desktop
rm -f /etc/sudoers.d/reset-net

update-desktop-database /usr/share/applications/ 2>/dev/null || true

echo -e "${GREEN}تم إلغاء التثبيت بالكامل.${NC}"
