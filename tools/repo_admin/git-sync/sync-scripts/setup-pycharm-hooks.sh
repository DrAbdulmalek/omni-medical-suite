#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
HOOK='#!/bin/bash
repo_name="$(basename "$(git rev-parse --show-toplevel)")"
echo ">>> Auto-pushing $repo_name..."
'"$SYNC_DIR"'/sync-scripts/sync-single.sh "$repo_name" push
'
echo -e "${BOLD}${CYAN}Setting up Git Hooks...${NC}"; echo ""; count=0
while IFS='|' read -r repo_name local_path _; do
    [[ -z "$repo_name" || "$repo_name" == \#* ]] && continue; local_path="${local_path/#\~/$HOME}"
    [[ ! -d "$local_path/.git" ]] && { echo -e "  ${DIM}skip${NC} $repo_name"; continue; }
    hooks_dir="$local_path/.git/hooks"; mkdir -p "$hooks_dir"
    echo "$HOOK" > "$hooks_dir/post-commit"; chmod +x "$hooks_dir/post-commit"
    echo "$HOOK" > "$hooks_dir/post-merge"; chmod +x "$hooks_dir/post-merge"
    echo -e "  ${GREEN}OK${NC} $repo_name"; ((count++))
done < "$CONFIG_FILE"
echo ""; echo -e "  ${GREEN}Hooks in $count repos${NC}"; echo ""
