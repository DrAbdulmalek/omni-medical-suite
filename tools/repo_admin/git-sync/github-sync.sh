#!/bin/bash
SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"; source "$SYNC_DIR/config/lib-common.sh"
check_requirements || exit 1

show_menu() {
    clear; local total; total="$(count_repos)"
    echo -e "${BOLD}${CYAN}$(printf '=%.0s' {1..65})${NC}"
    echo -e "${BOLD}${CYAN}   Git Sync System for Manjaro${NC}"
    echo -e "${BOLD}${CYAN}$(printf '=%.0s' {1..65})${NC}"
    echo -e "   ${DIM}Repos: $total | $(date '+%Y-%m-%d %H:%M:%S')${NC}"; echo ""
    echo -e " ${GREEN}1.${NC}  ${BOLD}Status Dashboard${NC}         ${DIM}-- all repos status${NC}"
    echo -e " ${GREEN}2.${NC}  ${BOLD}Push to GitHub${NC}           ${DIM}-- local >> GitHub${NC}"
    echo -e " ${GREEN}3.${NC}  ${BOLD}Pull from GitHub${NC}         ${DIM}-- GitHub >> local${NC}"
    echo -e " ${GREEN}4.${NC}  ${BOLD}Bidirectional Sync${NC}       ${DIM}-- local <> GitHub${NC}"
    echo -e " ${GREEN}5.${NC}  ${BOLD}Sync Single Repo${NC}         ${DIM}-- one repo${NC}"
    echo -e " ${GREEN}6.${NC}  ${BOLD}Sync Custom Message${NC}      ${DIM}-- custom commit msg${NC}"
    echo -e " ${GREEN}7.${NC}  ${BOLD}Clone All Missing${NC}        ${DIM}-- clone repos not on disk${NC}"
    echo -e " ${GREEN}8.${NC}  ${BOLD}Dry-Run Push${NC}             ${DIM}-- preview without pushing${NC}"
    echo ""
    echo -e " ${CYAN}9.${NC}  ${BOLD}Monitor (Polling)${NC}        ${DIM}-- every 5 min${NC}"
    echo -e " ${CYAN}10.${NC} ${BOLD}Watch (Real-time)${NC}       ${DIM}-- inotifywait${NC}"
    echo -e " ${CYAN}11.${NC} ${BOLD}Enable systemd Service${NC}   ${DIM}-- auto-sync daemon${NC}"
    echo ""
    echo -e " ${MAGENTA}12.${NC} ${BOLD}Open All in PyCharm${NC}    ${DIM}-- launch PyCharm${NC}"
    echo -e " ${MAGENTA}13.${NC} ${BOLD}Setup Git Hooks${NC}        ${DIM}-- auto-push${NC}"
    echo -e " ${MAGENTA}14.${NC} ${BOLD}Refresh Repos List${NC}     ${DIM}-- fetch from API${NC}"
    echo ""
    echo -e " ${YELLOW}15.${NC} ${BOLD}Edit Repos List${NC}         ${DIM}-- repos.txt${NC}"
    echo -e " ${YELLOW}16.${NC} ${BOLD}Edit Settings${NC}           ${DIM}-- settings.env${NC}"
    echo -e " ${YELLOW}17.${NC} ${BOLD}View Logs${NC}               ${DIM}-- sync logs${NC}"
    echo -e " ${RED}0.${NC}  ${BOLD}Exit${NC}"
    echo -e "${BOLD}${CYAN}$(printf '=%.0s' {1..65})${NC}"; echo ""
}

select_repo() {
    echo -e "${BOLD}Repos:${NC}"; local i=1; local repos=()
    while IFS='|' read -r name _; do
        [[ -z "$name" || "$name" == \#* ]] && continue; repos+=("$name")
        printf "  ${GREEN}%3d.${NC} %s\n" "$i" "$name"; ((i++))
    done < "$CONFIG_FILE"
    echo ""; read -rp "  Select number: " choice
    [[ "$choice" -ge 1 && "$choice" -le ${#repos[@]} ]] && echo "${repos[$((choice-1))]}"
}

view_logs() {
    echo -e "${BOLD}${CYAN}Logs:${NC}"; ls -lht "$LOG_DIR"/*.log 2>/dev/null | head -15
    echo ""; read -rp "  Log to view (name or 'q'): " logfile
    [[ "$logfile" == "q" || -z "$logfile" ]] && return
    local found=""; for f in "$LOG_DIR"/"$logfile" "$LOG_DIR"/*"$logfile"*; do [[ -f "$f" ]] && { found="$f"; break; }; done
    [[ -n "$found" ]] && less "$found" || echo -e "  ${RED}Not found${NC}"
}

refresh_repos() {
    echo -e "${BOLD}${CYAN}Fetching repos from GitHub + HuggingFace...${NC}"; echo ""
    source "$SETTINGS_FILE"
    local tmp="$SYNC_DIR/config/repos.txt.new"
    echo "# Auto-fetched $(date '+%Y-%m-%d %H:%M:%S')" > "$tmp"
    echo "# GitHub Repositories" >> "$tmp"
    curl -s -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/user/repos?per_page=100&sort=updated" 2>/dev/null | \
        python3 -c "
import json,sys
for r in json.load(sys.stdin):
    print(f\"{r['name']}|~/github~/{r['name']}|{r.get('clone_url','')}|{r.get('default_branch','main')}\")
" >> "$tmp" 2>/dev/null
    echo "" >> "$tmp"; echo "# HuggingFace Spaces" >> "$tmp"
    curl -s -H "Authorization: Bearer $HF_TOKEN" "https://huggingface.co/api/spaces?author=DrAbdulmalek" 2>/dev/null | \
        python3 -c "
import json,sys
for s in json.load(sys.stdin):
    sid=s.get('id',''); name=sid.split('/')[-1]
    print(f'hf-{name}|~/github~/hf-{name}|https://huggingface.co/spaces/{sid}|main')
" >> "$tmp" 2>/dev/null
    local count; count=$(grep -v -E '^#|^$' "$tmp" | wc -l)
    mv "$tmp" "$CONFIG_FILE"
    echo -e "  ${GREEN}Found $count repos${NC}"; echo ""
}

while true; do
    show_menu; read -rp "  Choice [0-17]: " choice
    case "$choice" in
        1) show_dashboard; press_enter ;;
        2) echo ""; "$SYNC_DIR/sync-scripts/sync-push.sh"; press_enter ;;
        3) echo ""; "$SYNC_DIR/sync-scripts/sync-pull.sh"; press_enter ;;
        4) echo ""; "$SYNC_DIR/sync-scripts/sync-bidirectional.sh"; press_enter ;;
        5)
            echo ""; repo="$(select_repo)"
            if [[ -n "$repo" ]]; then
                echo -e "  ${DIM}(1)push (2)pull (3)bidi [default=3]:${NC}"
                read -rp "  Select: " op
                case "$op" in 1) op="push";; 2) op="pull";; *) op="bidi";; esac
                "$SYNC_DIR/sync-scripts/sync-single.sh" "$repo" "$op"
            else echo -e "  ${RED}Invalid${NC}"; fi
            press_enter ;;
        6)
            echo ""; read -rp "  Commit message: " msg
            [[ -n "$msg" ]] && "$SYNC_DIR/sync-scripts/sync-custom.sh" "$msg" push
            press_enter ;;
        7)
            echo -e "\n${BOLD}${CYAN}Cloning missing repos...${NC}"; echo ""
            while IFS='|' read -r name local_path github_url branch; do
                [[ -z "$name" || "$name" == \#* ]] && continue; local_path="${local_path/#\~/$HOME}"
                if [[ ! -d "$local_path" ]]; then
                    echo -n "  $name ... "; git clone --branch "$branch" "$github_url" "$local_path" 2>/dev/null && \
                        echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAILED${NC}"
                else echo -e "  ${DIM}skip${NC} $name (exists)"
                fi
            done < "$CONFIG_FILE"; echo ""; press_enter ;;
        8)
            echo -e "\n${BOLD}${YELLOW}Dry-Run: preview without pushing...${NC}\n"
            DRY_RUN=true; source "$SYNC_DIR/config/lib-common.sh"
            total=0; has_changes=0
            while IFS='|' read -r repo_name local_path github_url branch; do
                [[ -z "$repo_name" || "$repo_name" == \#* ]] && continue; ((total++))
                local_path="${local_path/#\~/$HOME}"
                if [[ -d "$local_path" && -d "$local_path/.git" ]]; then
                    local st; st="$(git -C "$local_path" status --porcelain 2>/dev/null)"
                    if [[ -n "$st" ]]; then
                        ((has_changes++)); local cnt; cnt="$(echo "$st" | wc -l)"
                        echo -e "  ${YELLOW}CHG${NC}   $repo_name  ($cnt files)"
                        git -C "$local_path" diff --stat 2>/dev/null | sed 's/^/         /'
                    else
                        echo -e "  ${DIM}---${NC}   $repo_name  (clean)"
                    fi
                else
                    echo -e "  ${RED}MISS${NC}  $repo_name  (not cloned)"
                fi
            done < "$CONFIG_FILE"
            echo -e "\n  ${YELLOW}$has_changes/$total repos have changes${NC}"; press_enter ;;
        9) echo ""; "$SYNC_DIR/sync-scripts/monitor-changes.sh" ;;
        10) echo ""; "$SYNC_DIR/sync-scripts/sync-watch.sh" ;;
        11)
            echo -e "\n${BOLD}${CYAN}Enabling git-sync-watch systemd service...${NC}"
            mkdir -p "$HOME/.config/systemd/user"
            cat > "$HOME/.config/systemd/user/git-sync-watch.service" << SYSEOF
[Unit]
Description=Git Sync Watch (inotify)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$SYNC_DIR/sync-scripts/sync-watch.sh
Restart=on-failure
RestartSec=10
Environment=SYNC_DIR=$SYNC_DIR

[Install]
WantedBy=default.target
SYSEOF
            systemctl --user daemon-reload
            systemctl --user enable git-sync-watch.service
            echo -e "  ${GREEN}Enabled!${NC}"
            echo -e "  Start:  ${CYAN}systemctl --user start git-sync-watch${NC}"
            echo -e "  Status: ${CYAN}systemctl --user status git-sync-watch${NC}"
            echo -e "  Logs:   ${CYAN}journalctl --user -u git-sync-watch -f${NC}"
            echo -e "  Stop:   ${CYAN}systemctl --user stop git-sync-watch${NC}"
            press_enter ;;
        12) echo ""; "$SYNC_DIR/sync-scripts/open-pycharm.sh"; press_enter ;;
        13) echo ""; "$SYNC_DIR/sync-scripts/setup-pycharm-hooks.sh"; press_enter ;;
        14) refresh_repos; press_enter ;;
        15) ${EDITOR:-nano} "$CONFIG_FILE" ;;
        16) ${EDITOR:-nano} "$SETTINGS_FILE" ;;
        17) view_logs ;;
        0|q|Q) echo -e "\n${GREEN}Bye!${NC}\n"; exit 0 ;;
        *) echo -e "\n${RED}Invalid!${NC}"; sleep 1 ;;
    esac
done
