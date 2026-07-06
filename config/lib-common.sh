#!/bin/bash
# =============================================
# lib-common.sh — مكتبة الدوال المشتركة
# =============================================

SYNC_DIR="${SYNC_DIR:-$HOME/github-sync-system}"
CONFIG_FILE="$SYNC_DIR/config/repos.txt"
SETTINGS_FILE="$SYNC_DIR/config/settings.env"
LOG_DIR="$SYNC_DIR/logs"
mkdir -p "$LOG_DIR"

# ── الألوان ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; MAGENTA='\033[0;35m'; CYAN='\033[0;36m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

# ── تحميل الإعدادات ──
if [[ -f "$SETTINGS_FILE" ]]; then
    source "$SETTINGS_FILE"
fi
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_USERNAME="${GITHUB_USERNAME:-DrAbdulmalek}"
AUTH_METHOD="${AUTH_METHOD:-token}"
PULL_REBASE="${PULL_REBASE:-true}"
AUTO_COMMIT_MSG="${AUTO_COMMIT_MSG:-"sync: auto-sync %r [%d %t]"}"

# ── التسجيل ──
log() {
    local level="$1"; shift; local msg="$*"; local ts; ts="$(date '+%Y-%m-%d %H:%M:%S')"
    local prefix=""
    case "$level" in
        INFO)  prefix="${GREEN}[INFO]${NC}"  ;;
        WARN)  prefix="${YELLOW}[WARN]${NC}" ;;
        ERROR) prefix="${RED}[ERROR]${NC}" ;;
        OK)    prefix="${GREEN}[OK]${NC}"    ;;
        FAIL)  prefix="${RED}[FAIL]${NC}"   ;;
        *)     prefix="[$level]"             ;;
    esac
    echo -e "${DIM}${ts}${NC} ${prefix} $msg"
    echo "[$ts] [$level] $msg" >> "${CURRENT_LOG:-$LOG_DIR/sync.log}"
}

start_log() {
    local name="$1"
    CURRENT_LOG="$LOG_DIR/${name}-$(date +%Y%m%d-%H%M%S).log"
    mkdir -p "$LOG_DIR"
    echo "=== $name started at $(date) ===" > "$CURRENT_LOG"
    log INFO "Log: $CURRENT_LOG"
}

# ── المصادقة ──
setup_auth() {
    local repo_path="$1" remote_url="$2"
    if [[ -n "$GIT_NAME" ]]; then git -C "$repo_path" config user.name "$GIT_NAME" 2>/dev/null; fi
    if [[ -n "$GIT_EMAIL" ]]; then git -C "$repo_path" config user.email "$GIT_EMAIL" 2>/dev/null; fi
    # فقط GitHub URLs — لا HF
    if [[ "$remote_url" != *"github.com"* ]]; then return 0; fi
    case "$AUTH_METHOD" in
        token)
            if [[ -n "$GITHUB_TOKEN" && -n "$GITHUB_USERNAME" ]]; then
                local token_url="https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${remote_url#https://github.com/}"
                git -C "$repo_path" remote set-url origin "$token_url" 2>/dev/null
            fi ;;
        ssh) return 0 ;;
        store) git -C "$repo_path" config credential.helper store 2>/dev/null ;;
    esac
}

cleanup_auth() {
    local repo_path="$1"
    if [[ "$AUTH_METHOD" == "token" && -n "$GITHUB_USERNAME" ]]; then
        local current_url
        current_url="$(git -C "$repo_path" remote get-url origin 2>/dev/null)"
        if [[ "$current_url" == *"${GITHUB_USERNAME}:"*@github.com/* ]]; then
            local clean_url="${current_url#https://}"; clean_url="https://${clean_url#*@}"
            git -C "$repo_path" remote set-url origin "$clean_url" 2>/dev/null
        fi
    fi
}

# ── قراءة مستودع واحد ──
read_repo() {
    local repo_name="$1"
    while IFS='|' read -r name local_path github_url branch; do
        [[ -z "$name" || "$name" == \#* ]] && continue
        if [[ "$name" == "$repo_name" ]]; then echo "$name|$local_path|$github_url|$branch"; return 0; fi
    done < "$CONFIG_FILE"
    return 1
}

# ── عمليات Pull/Push ──
_do_pull() {
    local local_path="$1" branch="$2"
    local has_changes; has_changes="$(git -C "$local_path" status --porcelain 2>/dev/null)"
    local stashed=false
    if [[ -n "$has_changes" ]]; then
        git -C "$local_path" stash push -m "auto-stash $(date +%Y%m%d_%H%M%S)" 2>>"$CURRENT_LOG"; stashed=true
    fi
    git -C "$local_path" fetch origin "$branch" 2>>"$CURRENT_LOG"
    if [[ "$PULL_REBASE" == "true" ]]; then
        git -C "$local_path" pull --rebase origin "$branch" 2>>"$CURRENT_LOG"
    else
        git -C "$local_path" pull origin "$branch" 2>>"$CURRENT_LOG"
    fi
    local rc=$?
    if [[ "$stashed" == true ]]; then git -C "$local_path" stash pop 2>>"$CURRENT_LOG" || true; fi
    return $rc
}

_do_push() {
    local local_path="$1" branch="$2" repo_name="$3"
    local has_changes; has_changes="$(git -C "$local_path" status --porcelain 2>/dev/null)"
    if [[ -z "$has_changes" ]]; then
        local ahead; ahead="$(git -C "$local_path" rev-list --count '@{upstream}..HEAD' 2>/dev/null || echo 0)"
        if [[ "${ahead:-0}" -eq 0 ]]; then log INFO "$repo_name: nothing to push"; return 0; fi
    fi
    if [[ -n "$has_changes" ]]; then
        local msg="${AUTO_COMMIT_MSG:-"sync: auto-sync [%d %t]"}"
        msg="${msg//%d/$(date +%Y-%m-%d)}"; msg="${msg//%t/$(date +%H:%M:%S)}"; msg="${msg//%r/$repo_name}"
        git -C "$local_path" add -A 2>>"$CURRENT_LOG"
        git -C "$local_path" commit -m "$msg" 2>>"$CURRENT_LOG"
    fi
    git -C "$local_path" push origin "$branch" 2>>"$CURRENT_LOG"
}

# ── معالجة مستودع ──
DRY_RUN="${DRY_RUN:-false}"

process_repo() {
    local repo_name="$1" local_path="$2" github_url="$3" branch="$4" operation="$5"
    local_path="${local_path/#\~/$HOME}"
    echo -n "  $repo_name ... "
    if [[ ! -d "$local_path" ]]; then
        echo -e "${RED}NOT FOUND${NC}"; log WARN "Not found: $local_path"
        if [[ "$operation" == "pull" || "$operation" == "bidi" ]]; then
            echo -e "    ${YELLOW}Cloning...${NC}"
            git clone --branch "$branch" "$github_url" "$local_path" 2>>"$CURRENT_LOG" && \
                { echo -e "    ${GREEN}Cloned${NC}"; log OK "Cloned $repo_name"; } || \
                { echo -e "    ${RED}Clone failed${NC}"; log ERROR "Clone failed: $repo_name"; }
        fi
        return 1
    fi
    if [[ ! -d "$local_path/.git" ]]; then
        log WARN "Not a git repo: $local_path"; git -C "$local_path" init 2>>"$CURRENT_LOG"; git -C "$local_path" remote add origin "$github_url" 2>>"$CURRENT_LOG"
    fi
    if ! git -C "$local_path" remote | grep -q "^origin$"; then git -C "$local_path" remote add origin "$github_url" 2>>"$CURRENT_LOG"; fi

    # dry-run: عرض فقط بدون تنفيذ
    if [[ "$DRY_RUN" == "true" ]]; then
        local status; status="$(git -C "$local_path" status --porcelain 2>/dev/null)"
        if [[ -n "$status" ]]; then
            local cnt; cnt="$(echo "$status" | wc -l)"
            echo -e "${YELLOW}DRY${NC} $cnt file(s) would be committed + pushed"
        else
            echo -e "${DIM}DRY${NC} nothing to do"
        fi
        return 0
    fi

    setup_auth "$local_path" "$github_url"
    local result=0
    case "$operation" in
        pull) _do_pull "$local_path" "$branch" || result=1 ;;
        push) _do_push "$local_path" "$branch" "$repo_name" || result=1 ;;
        bidi) _do_pull "$local_path" "$branch" || result=1; _do_push "$local_path" "$branch" "$repo_name" || result=1 ;;
    esac
    cleanup_auth "$local_path"
    [[ $result -eq 0 ]] && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAILED${NC}"
    return $result
}

# ── لوحة الحالة ──
show_dashboard() {
    local total; total="$(count_repos)"
    echo ""; echo -e "${BOLD}${CYAN}$(printf '=%.0s' {1..65})${NC}"
    echo -e "${BOLD}${CYAN}  Git Sync System -- Status Dashboard${NC}"
    echo -e "${BOLD}${CYAN}$(printf '=%.0s' {1..65})${NC}"
    echo -e "  ${DIM}Total repos: $total | GitHub: 28 | HF Spaces: 11 | $(date '+%Y-%m-%d %H:%M:%S')${NC}"; echo ""
    local ok_count=0 mod_count=0 err_count=0
    while IFS='|' read -r name local_path github_url branch; do
        [[ -z "$name" || "$name" == \#* ]] && continue
        local_path="${local_path/#\~/$HOME}"
        if [[ ! -d "$local_path" ]]; then
            ((err_count++)); printf "  ${RED}MISS%-4s${NC} %-35s %s\n" "" "$name" "(not cloned)"; continue
        fi
        if [[ ! -d "$local_path/.git" ]]; then
            ((err_count++)); printf "  ${YELLOW}NOGIT%-3s${NC} %-35s %s\n" "" "$name" "(not git)"; continue
        fi
        local current_branch; current_branch="$(git -C "$local_path" branch --show-current 2>/dev/null)"
        local status; status="$(git -C "$local_path" status --porcelain 2>/dev/null)"
        if [[ -n "$status" ]]; then
            ((mod_count++)); local cnt; cnt="$(echo "$status" | wc -l)"
            printf "  ${YELLOW}MOD   ${NC} %-35s %-10s %s changed\n" "$name" "${current_branch:-?}" "$cnt"
        else
            local ahead behind
            ahead="$(git -C "$local_path" rev-list --count '@{upstream}..HEAD' 2>/dev/null || echo 0)"
            behind="$(git -C "$local_path" rev-list --count 'HEAD..@{upstream}' 2>/dev/null || echo 0)"
            if [[ "$ahead" -eq 0 && "$behind" -eq 0 ]]; then
                ((ok_count++)); printf "  ${GREEN}OK    ${NC} %-35s %-10s synced\n" "$name" "${current_branch:-?}"
            elif [[ "$ahead" -gt 0 && "$behind" -eq 0 ]]; then
                printf "  ${GREEN}+%s${NC}    %-35s %-10s needs push\n" "$ahead" "$name" "${current_branch:-?}"
            elif [[ "$behind" -gt 0 && "$ahead" -eq 0 ]]; then
                printf "  ${BLUE}-%s${NC}    %-35s %-10s needs pull\n" "$behind" "$name" "${current_branch:-?}"
            else
                printf "  ${MAGENTA}<>    ${NC} %-35s %-10s diverged (+%s/-%s)\n" "$name" "${current_branch:-?}" "$ahead" "$behind"
            fi
        fi
    done < "$CONFIG_FILE"
    echo ""; echo -e "${BOLD}$(printf '-%.0s' {1..65})${NC}"
    printf "  ${GREEN}Synced: %-3s${NC} | ${YELLOW}Modified: %-3s${NC} | ${RED}Missing: %-3s${NC}\n" "$ok_count" "$mod_count" "$err_count"
    echo -e "${BOLD}$(printf '=%.0s' {1..65})${NC}"; echo ""
}

count_repos() { grep -v -E '^#|^$' "$CONFIG_FILE" 2>/dev/null | wc -l; }

check_requirements() {
    local missing=()
    command -v git &>/dev/null || missing+=("git")
    [[ ${#missing[@]} -gt 0 ]] && { echo -e "${RED}Missing: ${missing[*]}; sudo pacman -S ${missing[*]}${NC}"; return 1; }
    return 0
}

press_enter() { echo ""; read -rp "  Press Enter to continue..." -n1 -s; echo ""; }
