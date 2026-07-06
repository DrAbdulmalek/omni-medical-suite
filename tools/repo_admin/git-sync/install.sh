#!/bin/bash
set -e; SYNC_DIR="$HOME/github-sync-system"
echo -e "${BOLD}${CYAN}=========================================${NC}"
echo -e "${BOLD}${CYAN}  Installing Git Sync System v2${NC}"
echo -e "${BOLD}${CYAN}=========================================${NC}"; echo ""

echo -n "  [1/7] git... "; command -v git &>/dev/null && echo -e "${GREEN}OK${NC}" || { sudo pacman -S git --noconfirm >/dev/null 2>&1; echo -e "${GREEN}installed${NC}"; }
echo -n "  [2/7] directories... "; mkdir -p "$SYNC_DIR"/{sync-scripts,config,pycharm-config,logs}; echo -e "${GREEN}OK${NC}"
echo -n "  [3/7] copying files... "
SCRIPT_SRC="$(cd "$(dirname "$0")" && pwd)"
for f in "$SCRIPT_SRC"/sync-scripts/*.sh; do [[ -f "$f" ]] && cp "$f" "$SYNC_DIR/sync-scripts/"; done
for f in "$SCRIPT_SRC"/config/*; do [[ -f "$f" ]] && cp "$f" "$SYNC_DIR/config/"; done
cp "$SCRIPT_SRC/github-sync.sh" "$SYNC_DIR/" 2>/dev/null || true; echo -e "${GREEN}OK${NC}"
echo -n "  [4/7] permissions... "
chmod +x "$SYNC_DIR/github-sync.sh" "$SYNC_DIR/sync-scripts/"*.sh "$SYNC_DIR/config/lib-common.sh" 2>/dev/null; echo -e "${GREEN}OK${NC}"
echo -n "  [5/7] command 'github-sync'... "
sudo ln -sf "$SYNC_DIR/github-sync.sh" /usr/local/bin/github-sync 2>/dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}needs sudo${NC}"
echo -n "  [6/7] bashrc... "
if ! grep -qF "# >>> git-sync-system >>>" "$HOME/.bashrc" 2>/dev/null; then
    printf '\n# >>> git-sync-system >>>\nexport SYNC_DIR="$HOME/github-sync-system"\nexport PATH="$PATH:$HOME/github-sync-system/sync-scripts"\n# <<< git-sync-system <<<\n' >> "$HOME/.bashrc"
    echo -e "${GREEN}OK${NC}"
else echo -e "${DIM}already set${NC}"; fi
echo -n "  [7/7] inotify-tools... "
command -v inotifywait &>/dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}optional (sudo pacman -S inotify-tools)${NC}"

echo ""
echo -e "${BOLD}${GREEN}=========================================${NC}"
echo -e "${BOLD}${GREEN}  Installed!${NC}"
echo -e "${BOLD}${GREEN}=========================================${NC}"
echo -e "  ${GREEN}1.${NC} source ~/.bashrc"
echo -e "  ${GREEN}2.${NC} github-sync"
echo -e "  ${DIM}Repos: 28 GitHub + 11 HF = 39 total (auto-fetched)${NC}"
echo -e "  ${DIM}All tokens pre-configured in settings.env${NC}"
echo ""
