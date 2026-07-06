#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
start_log "push"; log INFO "=== Push Sync ==="; echo ""; total=0; ok=0; fail=0
while IFS='|' read -r repo_name local_path github_url branch; do
    [[ -z "$repo_name" || "$repo_name" == \#* ]] && continue; ((total++))
    process_repo "$repo_name" "$local_path" "$github_url" "$branch" "push" && ((ok++)) || ((fail++))
done < "$CONFIG_FILE"
echo ""; echo -e "  ${GREEN}$ok pushed${NC} / ${RED}$fail failed${NC} / $total total"; echo ""
