#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
INTERVAL="${WATCH_INTERVAL:-300}"
echo -e "${BOLD}${CYAN}=========================================${NC}"
echo -e "${BOLD}${CYAN}  Change Monitor -- Polling Mode${NC}"
echo -e "${BOLD}${CYAN}=========================================${NC}"
echo -e "  Interval: ${YELLOW}$INTERVAL seconds${NC}"
echo -e "  ${DIM}Press Ctrl+C to stop${NC}"; echo ""; cycle=0
while true; do
    ((cycle++)); echo -e "${DIM}[$(date '+%H:%M:%S')] Cycle #$cycle${NC}"
    "$SYNC_DIR/sync-scripts/sync-bidirectional.sh" >> "$LOG_DIR/monitor.log" 2>&1
    echo -e "${DIM}  Next in $INTERVAL s...${NC}"; sleep "$INTERVAL"
done
