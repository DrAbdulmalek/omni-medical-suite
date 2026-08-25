#!/usr/bin/env sh
set -eu

# The production image runs as the non-root `omni` user. Database migrations
# and the idempotent admin bootstrap therefore run with the same application
# identity as the service itself.
if [ "${ENVIRONMENT:-development}" = "production" ]; then
  echo "[omni] applying Alembic migrations"
  alembic upgrade head

  echo "[omni] bootstrapping production administrator"
  python /app/deploy/bootstrap_admin.py
fi

exec "$@"
