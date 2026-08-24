#!/bin/sh
set -eu

# The production image must not start before the database schema is current.
# docker-compose.prod.yml already waits for PostgreSQL health before launching us.
echo "[omni] applying database migrations"
alembic upgrade head

# Bootstrap is explicit and idempotent. The compose deployment requires the
# password to come from a deployment secret; the script never prints it.
echo "[omni] ensuring bootstrap administrator exists"
python -m scripts.bootstrap_admin

echo "[omni] starting application: $*"
exec "$@"
