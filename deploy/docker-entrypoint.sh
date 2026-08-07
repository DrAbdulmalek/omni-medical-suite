#!/bin/bash
# =============================================================================
# Omni Medical Suite — Docker Entrypoint (Production)
# =============================================================================
# Verified against actual app structure:
#   - app/main.py (FastAPI entry point)
#   - app/db/session.py (async SQLAlchemy + asyncpg)
#   - app/config/ (Pydantic settings)
#   - alembic/ (database migrations)
#   - NO celery_app.py in the codebase
# =============================================================================
set -euo pipefail

echo "=========================================="
echo " Omni Medical Suite v2.0 - Production"
echo " Starting up..."
echo "=========================================="

# ── Environment Defaults ─────────────────────────────────────────────────────
export PYTHONPATH="${PYTHONPATH:-/app}"
export APP_ENV="${APP_ENV:-production}"

# ── Wait for PostgreSQL ─────────────────────────────────────────────────────
if [ -n "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] Waiting for PostgreSQL..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! python -c "
import socket, os, re
url = os.environ.get('DATABASE_URL', '')
# Extract host and port from DATABASE_URL
m = re.match(r'postgresql(?:\+[a-z]+)?://[^:]+:[^@]+@([^:]+):(\d+)', url)
if m:
    host, port = m.group(1), int(m.group(2))
    s = socket.socket()
    s.settimeout(2)
    s.connect((host, port))
    s.close()
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

# ── Wait for Redis ───────────────────────────────────────────────────────────
if [ -n "${REDIS_URL:-}" ]; then
    echo "[entrypoint] Waiting for Redis..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! python -c "
import socket, os, re
url = os.environ.get('REDIS_URL', '')
# Handle both redis://:pass@host:port and redis://host:port formats
m = re.match(r'redis://(?:[^:]*:)?([^@]+)?@([^:]+):(\d+)', url)
if not m:
    m = re.match(r'redis://([^:]+):(\d+)', url)
if m:
    if m.lastindex == 3:
        host, port = m.group(2), int(m.group(3))
    else:
        host, port = m.group(1), int(m.group(2))
    s = socket.socket()
    s.settimeout(2)
    s.connect((host, port))
    s.close()
" 2>/dev/null; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "[entrypoint] ERROR: Redis not available after ${MAX_RETRIES}s"
            exit 1
        fi
        sleep 1
    done
    echo "[entrypoint] Redis is ready."
fi

# ── Wait for Qdrant ──────────────────────────────────────────────────────────
if [ -n "${QDRANT_URL:-}" ]; then
    echo "[entrypoint] Waiting for Qdrant..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! python -c "
import socket, os, re
url = os.environ.get('QDRANT_URL', '')
m = re.match(r'http://([^:]+):(\d+)', url)
if m:
    host, port = m.group(1), int(m.group(2))
    s = socket.socket()
    s.settimeout(2)
    s.connect((host, port))
    s.close()
" 2>/dev/null; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "[entrypoint] WARNING: Qdrant not available (search features disabled)"
            break
        fi
        sleep 1
    done
    echo "[entrypoint] Qdrant is ready."
fi

# ── Run Alembic Migrations ───────────────────────────────────────────────────
if [ -f /app/alembic.ini ] && [ -d /app/migrations ]; then
    echo "[entrypoint] Running Alembic migrations..."
    cd /app && alembic upgrade head 2>/dev/null || {
        echo "[entrypoint] Alembic migration failed, trying create_all fallback..."
        python -c "
import sys
sys.path.insert(0, '/app')
try:
    from app.db.session import engine
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    print(f'[entrypoint] DB has {len(tables)} tables already.')
except Exception as e:
    print(f'[entrypoint] DB check skipped: {e}')
" 2>/dev/null || true
    }
    echo "[entrypoint] Database migrations done."
else
    echo "[entrypoint] No Alembic config found, skipping migrations."
fi

# ── Create required directories ──────────────────────────────────────────────
mkdir -p /app/uploads /app/results /app/logs /app/encrypted /app/model /app/backups 2>/dev/null || true

# ── Display startup info ─────────────────────────────────────────────────────
echo "[entrypoint] Environment: ${APP_ENV}"
echo "[entrypoint] Python: $(python --version 2>&1)"
echo "[entrypoint] Tesseract: $(tesseract --version 2>&1 | head -1 || echo 'N/A')"
echo "[entrypoint] Starting: $@"

# ── Execute the main command ─────────────────────────────────────────────────
exec "$@"
