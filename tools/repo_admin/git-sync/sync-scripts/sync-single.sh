#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
REPO_NAME="$1"; OPERATION="${2:-bidi}"
if [[ -z "$REPO_NAME" ]]; then
    echo -e "${RED}Usage: sync-single.sh <repo_name> [push|pull|bidi]${NC}"; echo ""
    echo "Available repos:"; while IFS='|' read -r name _; do
        [[ -z "$name" || "$name" == \#* ]] && continue; echo "  - $name"
    done < "$CONFIG_FILE"; exit 1
fi
repo_line="$(read_repo "$REPO_NAME")"
if [[ -z "$repo_line" ]]; then echo -e "${RED}Repo '$REPO_NAME' not found!${NC}"; exit 1; fi
IFS='|' read -r name local_path github_url branch <<< "$repo_line"
echo -e "${BOLD}${CYAN}Syncing: $name [$OPERATION]${NC}"; echo ""
start_log "single-$REPO_NAME"; process_repo "$name" "$local_path" "$github_url" "$branch" "$OPERATION"
