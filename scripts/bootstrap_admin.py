"""Bootstrap the first administrator for a fresh deployment.

Usage is intentionally explicit: ADMIN_BOOTSTRAP_PASSWORD must be supplied by
an operator/secret manager. The command is idempotent and never prints the
password.
"""
from __future__ import annotations

import asyncio
import os
import sys

from app.core.rbac import create_default_admin
from app.db.session import AsyncSessionLocal, close_db, init_db


async def main() -> None:
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
    if not password:
        print("ADMIN_BOOTSTRAP_PASSWORD is not set; refusing to bootstrap an admin.", file=sys.stderr)
        raise SystemExit(2)
    if len(password) < 12:
        print("ADMIN_BOOTSTRAP_PASSWORD must be at least 12 characters.", file=sys.stderr)
        raise SystemExit(2)

    init_db()
    assert AsyncSessionLocal is not None
    try:
        async with AsyncSessionLocal() as db:
            await create_default_admin(
                db,
                username=os.environ.get("ADMIN_BOOTSTRAP_USERNAME", "admin"),
                email=os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@omni-medical-suite.local"),
                password=password,
            )
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
