#!/bin/bash
# =============================================================================
# Omni Medical Suite — Docker Entrypoint (Production)
# =============================================================================
set -euo pipefail

echo "=========================================="
echo " Omni Medical Suite v2.0 - Production"
echo " Starting up..."
echo "=========================================="

export PYTHONPATH="${PYTHONPATH:-/app}"
export APP_ENV="${APP_ENV:-production}"
export ENVIRONMENT="${ENVIRONMENT:-production}"

# ── Wait for PostgreSQL ─────────────────────────────────────────────────────
if [ -n "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] Waiting for PostgreSQL..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! python -c "
import socket, os, re
url = os.environ.get('DATABASE_URL', '')
m = re.match(r'postgresql(?:\\+[a-z]+)?://[^:]+:[^@]+@([^:]+):(\\d+)', url)
if m:
    host, port = m.group(1), int(m.group(2))
    s = socket.socket(); s.settimeout(2); s.connect((host, port)); s.close()
else:
    raise ValueError(f'Cannot parse DATABASE_URL: {url[:30]}...')
" 2>/dev/null; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "[entrypoint] ERROR: PostgreSQL not available after ${MAX_RETRIES}s"
            exit 1
        fi
        sleep 1
    done
    echo "[entrypoint] PostgreSQL is ready."
fi

# ── Run Alembic Migrations ───────────────────────────────────────────────────
if [ -f /app/alembic.ini ] && [ -d /app/migrations ]; then
    echo "[entrypoint] Running Alembic migrations..."
    cd /app
    alembic upgrade head
    echo "[entrypoint] Database migrations completed."
else
    echo "[entrypoint] ERROR: Alembic configuration is missing; refusing production startup."
    exit 1
fi

# ── Explicit first-admin bootstrap ──────────────────────────────────────────
# Never generate or print a password in production. An operator must provide
# ADMIN_BOOTSTRAP_PASSWORD through a secret manager/environment for first setup.
if [ -n "${ADMIN_BOOTSTRAP_PASSWORD:-}" ]; then
    echo "[entrypoint] Bootstrapping administrator account (idempotent)..."
    python /app/scripts/bootstrap_admin.py
    unset ADMIN_BOOTSTRAP_PASSWORD
    echo "[entrypoint] Administrator bootstrap completed."
fi

mkdir -p /app/uploads /app/results /app/logs /app/encrypted /app/model /app/backups

echo "[entrypoint] Environment: ${ENVIRONMENT}"
echo "[entrypoint] Python: $(python --version 2>&1)"
echo "[entrypoint] Tesseract: $(tesseract --version 2>&1 | head -1 || echo 'N/A')"
echo "[entrypoint] Starting: $@"
exec "$@"
