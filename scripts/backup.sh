#!/bin/bash
# =============================================================================
# OmniMedical Suite — Backup Script
# =============================================================================
# Backs up: Git repos, databases (if running), and model caches.
# Usage: ./scripts/backup.sh [--dry-run]
#
# Schedule: 0 2 * * * (daily at 2 AM via cron)
# Retention: 30 days (configurable below)
# =============================================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
BACKUP_BASE="${BACKUP_DIR:-/var/backups/omni-medical}"
RETENTION_DAYS=30
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"
REPOS=("omni-medical-suite" "intelli-file-manager" "repo-sync-toolkit" "sync-github")
GITHUB_USER="DrAbdulmalek"
DRY_RUN=false

for arg in "$@"; do
    [ "$arg" = "--dry-run" ] && DRY_RUN=true
done

# ── Functions ────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

backup_repo() {
    local repo="$1"
    local dest="${BACKUP_DIR}/repos/${repo}.bundle"
    log "Backing up repo: ${repo}"
    if [ "$DRY_RUN" = true ]; then
        log "  [DRY-RUN] Would create: ${dest}"
        return
    fi
    git bundle create "$dest" "https://github.com/${GITHUB_USER}/${repo}.git" --all 2>/dev/null \
        && log "  OK: ${dest}" \
        || log "  WARN: Failed to bundle ${repo} (may be private or empty)"
}

backup_database() {
    local name="$1"
    local dest="${BACKUP_DIR}/databases/"
    log "Backing up ${name}..."
    if [ "$DRY_RUN" = true ]; then
        log "  [DRY-RUN] Would dump ${name}"
        return
    fi
    mkdir -p "$dest"
    if [ "$name" = "postgres" ]; then
        if docker ps --format '{{.Names}}' | grep -q postgres 2>/dev/null; then
            docker exec postgres pg_dump -U omnimedical omnimedical > "${dest}/postgres.dump" 2>/dev/null \
                && log "  OK: postgres.dump" || log "  WARN: Postgres dump failed"
        else
            log "  SKIP: Postgres not running"
        fi
    elif [ "$name" = "redis" ]; then
        if docker ps --format '{{.Names}}' | grep -q redis 2>/dev/null; then
            docker exec redis redis-cli SAVE 2>/dev/null || true
            docker cp redis:/data/dump.rdb "${dest}/redis.rdb" 2>/dev/null \
                && log "  OK: redis.rdb" || log "  WARN: Redis backup failed"
        else
            log "  SKIP: Redis not running"
        fi
    fi
}

cleanup_old() {
    log "Cleaning up backups older than ${RETENTION_DAYS} days..."
    if [ "$DRY_RUN" = true ]; then
        log "  [DRY-RUN] Would remove old backups"
        return
    fi
    find "$BACKUP_BASE" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true
    log "  Cleanup complete"
}

# ── Main ─────────────────────────────────────────────────────────────────────
log "=== OmniMedical Suite Backup ==="
log "Timestamp: ${TIMESTAMP}"
log "Target: ${BACKUP_DIR}"

mkdir -p "${BACKUP_DIR}/repos" "${BACKUP_DIR}/databases"

# 1. Backup Git repositories as bundles
log "--- Repositories ---"
for repo in "${REPOS[@]}"; do
    backup_repo "$repo"
done

# 2. Backup databases (if Docker is available)
log "--- Databases ---"
if command -v docker &>/dev/null; then
    backup_database "postgres"
    backup_database "redis"
else
    log "Docker not available — skipping database backups"
fi

# 3. Compress
if [ "$DRY_RUN" = false ]; then
    log "Compressing..."
    tar czf "${BACKUP_DIR}.tar.gz" -C "${BACKUP_BASE}" "${TIMESTAMP}" 2>/dev/null
    SIZE=$(du -sh "${BACKUP_DIR}.tar.gz" 2>/dev/null | cut -f1)
    log "Archive: ${BACKUP_DIR}.tar.gz (${SIZE})"
    rm -rf "${BACKUP_DIR}"
fi

# 4. Cleanup
cleanup_old

log "=== Backup complete ==="