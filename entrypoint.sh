#!/bin/bash
set -euo pipefail

echo "=== OmniMedical Suite v2.0 - Starting ==="

# Wait for dependencies
echo "Waiting for PostgreSQL..."
while ! python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('postgres', 5432)); s.close()" 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready."

echo "Waiting for Redis..."
while ! python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('redis', 6379)); s.close()" 2>/dev/null; do
    sleep 1
done
echo "Redis is ready."

# Run database migrations
echo "Running database migrations..."
python -c "
from app.core.database import engine, Base
Base.metadata.create_all(bind=engine)
print('Migrations complete.')
" 2>/dev/null || echo "Migration step skipped (tables may exist)."

# Execute the command passed to the entrypoint
echo "Starting: $@"
exec "$@"
