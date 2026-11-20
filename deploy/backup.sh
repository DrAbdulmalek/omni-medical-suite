#!/bin/bash
# =============================================================================
# Omni Medical Suite — Backup & Restore Utilities
# =============================================================================

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/omni-medical-suite}"
BACKUP_DIR="${BACKUP_DIR:-/opt/omni-medical-suite/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="docker-compose.prod.yml"

# ── Backup ───────────────────────────────────────────────────────────────────
backup() {
    echo "=== Omni Medical Suite Backup — $(date) ==="
    mkdir -p "$BACKUP_DIR"

    # PostgreSQL dump
    echo "[1/4] Backing up PostgreSQL..."
    docker exec omni-postgres pg_dump -U omni_user -d omni_medical \
        | gzip > "${BACKUP_DIR}/postgres_${TIMESTAMP}.sql.gz"
    echo "  → postgres_${TIMESTAMP}.sql.gz"

    # Redis dump
    echo "[2/4] Backing up Redis..."
    docker exec omni-redis redis-cli BGSAVE
    sleep 2
    docker cp omni-redis:/data/dump.rdb "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"
    echo "  → redis_${TIMESTAMP}.rdb"

    # Uploads
    echo "[3/4] Backing up uploads..."
    tar czf "${BACKUP_DIR}/uploads_${TIMESTAMP}.tar.gz" -C "$PROJECT_DIR" data/uploads/ 2>/dev/null || true
    echo "  → uploads_${TIMESTAMP}.tar.gz"

    # Qdrant snapshot
    echo "[4/4] Creating Qdrant snapshot..."
    curl -sf -X POST http://localhost:6333/collections/medical_documents/snapshots 2>/dev/null || true
    echo "  → Qdrant snapshot created"

    # Cleanup old backups (keep last 7 days)
    find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name "*.rdb" -mtime +7 -delete 2>/dev/null || true

    echo "=== Backup complete ==="
}

# ── Restore ──────────────────────────────────────────────────────────────────
restore() {
    local BACKUP_NAME="${1:-}"
    if [[ -z "$BACKUP_NAME" ]]; then
        echo "Available backups:"
        ls -1 "${BACKUP_DIR}"/postgres_*.sql.gz 2>/dev/null | sed 's/.*postgres_\(.*\)\.sql\.gz/  \1/'
        echo ""
        echo "Usage: $0 restore YYYYMMDD_HHMMSS"
        return
    fi

    echo "=== Restoring from backup: $BACKUP_NAME ==="

    # PostgreSQL
    echo "[1/3] Restoring PostgreSQL..."
    docker exec -i omni-postgres psql -U omni_user -d omni_medical \
        < <(gunzip -c "${BACKUP_DIR}/postgres_${BACKUP_NAME}.sql.gz")

    # Redis
    echo "[2/3] Restoring Redis..."
    docker compose -f "$COMPOSE_FILE" stop redis
    docker cp "${BACKUP_DIR}/redis_${BACKUP_NAME}.rdb" omni-redis:/data/dump.rdb
    docker compose -f "$COMPOSE_FILE" start redis

    # Uploads
    echo "[3/3] Restoring uploads..."
    tar xzf "${BACKUP_DIR}/uploads_${BACKUP_NAME}.tar.gz" -C "$PROJECT_DIR" 2>/dev/null || true

    echo "=== Restore complete ==="
}

# ── Main ─────────────────────────────────────────────────────────────────────
case "${1:-backup}" in
    backup)  backup ;;
    restore) restore "${2:-}" ;;
    *)
        echo "Usage: $0 {backup|restore [TIMESTAMP]}"
        echo ""
        echo "  backup              — Create a full backup"
        echo "  restore TIMESTAMP   — Restore from a specific backup"
        ;;
esac
