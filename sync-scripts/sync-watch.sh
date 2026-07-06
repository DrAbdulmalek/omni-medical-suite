#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
WATCH_DIR="${HOME}/github~"; DEBOUNCE=3; WATCH_LOG="$LOG_DIR/watch.log"
if ! command -v inotifywait &>/dev/null; then
    echo -e "${RED}inotifywait not found. Install: sudo pacman -S inotify-tools${NC}"; exit 1
fi
declare -A REPO_MAP BRANCH_MAP URL_MAP
while IFS='|' read -r name local_path github_url branch; do
    [[ -z "$name" || "$name" == \#* ]] && continue; local_path="${local_path/#\~/$HOME}"
    REPO_MAP["$local_path"]="$name"; BRANCH_MAP["$local_path"]="$branch"; URL_MAP["$local_path"]="$github_url"
done < "$CONFIG_FILE"
echo -e "${BOLD}${CYAN}=========================================${NC}"
echo -e "${BOLD}${CYAN}  Real-time Watch -- inotifywait${NC}"
echo -e "${BOLD}${CYAN}=========================================${NC}"
echo -e "  Watching: ${YELLOW}$WATCH_DIR${NC} | Repos: ${YELLOW}${#REPO_MAP[@]}${NC}"
echo -e "  ${DIM}Press Ctrl+C to stop${NC}"; echo ""
declare -A LAST_SYNC
inotifywait -m -r -e modify,create,delete,move \
    --exclude '(\.git|__pycache__|\.pyc|\.idea|node_modules|\.venv|venv|\.DS_Store|\.egg-info)' \
    "$WATCH_DIR" 2>/dev/null | while read -r dir event file; do
    repo_dir="$dir"
    while [[ "$repo_dir" != "/" && -z "${REPO_MAP[$repo_dir]}" ]]; do repo_dir="$(dirname "$repo_dir")"; done
    [[ -z "${REPO_MAP[$repo_dir]}" ]] && continue
    repo_name="${REPO_MAP[$repo_dir]}"; now="$(date +%s)"; last="${LAST_SYNC[$repo_name]:-0}"
    (( now - last < DEBOUNCE )) && continue; LAST_SYNC["$repo_name"]="$now"
    ts="$(date '+%H:%M:%S')"
    echo -e "[${ts}] ${CYAN}$event${NC} ${DIM}$file${NC} in ${BOLD}$repo_name${NC}"
    process_repo "$repo_name" "$repo_dir" "${URL_MAP[$repo_dir]}" "${BRANCH_MAP[$repo_dir]}" "push"
done >> "$WATCH_LOG" 2>&1
