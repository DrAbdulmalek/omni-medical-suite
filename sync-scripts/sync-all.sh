#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"
echo -e "${BOLD}${CYAN}=========================================${NC}"
echo -e "${BOLD}${CYAN}  Full Sync -- All Repositories${NC}"
echo -e "${BOLD}${CYAN}=========================================${NC}"; echo ""
"$SYNC_DIR/sync-scripts/sync-bidirectional.sh"
