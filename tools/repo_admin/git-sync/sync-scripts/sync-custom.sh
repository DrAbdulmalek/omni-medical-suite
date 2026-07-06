#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
MESSAGE="$1"; OPERATION="${2:-push}"
if [[ -z "$MESSAGE" ]]; then echo -e "${RED}Usage: sync-custom.sh \"<msg>\" [push|pull|bidi]${NC}"; exit 1; fi
export AUTO_COMMIT_MSG="$MESSAGE"; start_log "custom"; log INFO "Custom: $MESSAGE"
total=0; ok=0; fail=0
while IFS='|' read -r repo_name local_path github_url branch; do
    [[ -z "$repo_name" || "$repo_name" == \#* ]] && continue; ((total++))
    process_repo "$repo_name" "$local_path" "$github_url" "$branch" "$OPERATION" && ((ok++)) || ((fail++))
done < "$CONFIG_FILE"
echo ""; echo -e "  ${GREEN}$ok/$total${NC} synced: ${BOLD}$MESSAGE${NC}"; echo ""
