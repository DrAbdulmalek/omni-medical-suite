#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
PYCHARM_CMD=""
for cmd in pycharm-professional pycharm-community pycharm; do
    command -v "$cmd" &>/dev/null && { PYCHARM_CMD="$cmd"; break; }
done
[[ -z "$PYCHARM_CMD" ]] && for p in /opt/pycharm-professional/bin/pycharm.sh /opt/pycharm-community/bin/pycharm.sh; do
    [[ -x "$p" ]] && { PYCHARM_CMD="$p"; break; }
done
if [[ -z "$PYCHARM_CMD" ]]; then echo -e "${RED}PyCharm not found!${NC}"; exit 1; fi
echo -e "${BOLD}${CYAN}Opening repos in PyCharm: $PYCHARM_CMD${NC}"; echo ""
opened=0
while IFS='|' read -r repo_name local_path _; do
    [[ -z "$repo_name" || "$repo_name" == \#* ]] && continue; local_path="${local_path/#\~/$HOME}"
    if [[ -d "$local_path" ]]; then
        echo -e "  ${GREEN}Opening${NC} $repo_name"; nohup "$PYCHARM_CMD" "$local_path" >/dev/null 2>&1 &
        ((opened++)); sleep 1
    else echo -e "  ${DIM}skip${NC} $repo_name (not cloned)"
    fi
done < "$CONFIG_FILE"
echo ""; echo -e "  ${GREEN}$opened repo(s) opened${NC}"; echo ""
