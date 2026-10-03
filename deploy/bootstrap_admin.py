"""Bootstrap the first production administrator.

This command is intentionally explicit: production deployments must provide
ADMIN_BOOTSTRAP_PASSWORD and the identity fields through the environment.
It is idempotent for an existing username.
"""
from __future__ import annotations

import asyncio
import os

from app.core.rbac import create_default_admin
from app.db.session import AsyncSessionLocal, close_db, init_db


async def main() -> None:
    username = os.environ.get("ADMIN_BOOTSTRAP_USERNAME", "admin").strip()
    email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@omni-medical-suite.local").strip()
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")

    if not username or not email or not password:
        raise SystemExit(
            "ADMIN_BOOTSTRAP_USERNAME, ADMIN_BOOTSTRAP_EMAIL and "
            "ADMIN_BOOTSTRAP_PASSWORD are required for bootstrap"
        )
    if len(password) < 12:
        raise SystemExit("ADMIN_BOOTSTRAP_PASSWORD must be at least 12 characters")

    init_db()
    assert AsyncSessionLocal is not None
    try:
        async with AsyncSessionLocal() as db:
            user = await create_default_admin(
                db,
                username=username,
                email=email,
                password=password,
            )
            print(f"Production admin bootstrap complete for username={user.username!r}")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
