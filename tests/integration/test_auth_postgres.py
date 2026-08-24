"""PostgreSQL-backed authentication integration tests.

These tests intentionally run against the real database engine because SQLite
does not implement SELECT ... FOR UPDATE semantics.
"""
from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.security.tokens import create_refresh_token
from app.db.models.auth import RefreshToken, User
from app.db.session import AsyncSessionLocal
from app.main import app
from app.routers.session_auth import pwd_context


pytestmark = pytest.mark.asyncio


async def _cleanup(username: str) -> None:
    assert AsyncSessionLocal is not None
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is not None:
            await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
            await db.delete(user)
            await db.commit()


@pytest.mark.integration
async def test_concurrent_refresh_rotation_is_single_use_postgres():
    assert AsyncSessionLocal is not None, "PostgreSQL session factory was not initialized"
    username = f"pg-refresh-{uuid4().hex[:12]}"
    password = "Integration-Password-123!"
    refresh_plain, refresh_hash, refresh_expires = create_refresh_token()

    async with AsyncSessionLocal() as db:
        user = User(
            username=username,
            email=f"{username}@example.invalid",
            hashed_password=pwd_context.hash(password),
            full_name="Integration Test",
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        db.add(
            RefreshToken(
                token_hash=refresh_hash,
                user_id=user.id,
                jti=uuid4().hex,
                expires_at=refresh_expires,
            )
        )
        await db.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        results = await asyncio.gather(
            client.post("/api/auth/refresh", json={"refresh_token": refresh_plain}),
            client.post("/api/auth/refresh", json={"refresh_token": refresh_plain}),
        )

    statuses = sorted(response.status_code for response in results)
    assert statuses == [200, 401], [response.text for response in results]

    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).where(User.username == username))
        user = user_result.scalar_one()
        token_result = await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        tokens = token_result.scalars().all()
        # The successful rotation creates one new token; replay detection then
        # revokes the complete active family, including that replacement.
        assert tokens
        assert all(token.is_revoked for token in tokens)

    await _cleanup(username)
