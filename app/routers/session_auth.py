"""Credential-based session endpoints.

Kept separate from RBAC management routes so authentication does not depend on
router-level authorization helpers.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_security_config
from app.core.security import get_current_user
from app.core.security.tokens import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from app.db.models.auth import RefreshToken, User, UserStatus
from app.db.session import get_db

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Pre-computed once: never generate a fresh bcrypt hash for every unknown username.
_DUMMY_PASSWORD_HASH = pwd_context.hash("omni-medical-invalid-login")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=40, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize DB timestamps for safe aware-vs-naive comparisons."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def _constant_time_dummy_verify(password: str) -> None:
    """Perform one bcrypt verification for unknown usernames."""
    _verify_password(password, _DUMMY_PASSWORD_HASH)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a username and issue short-lived access + opaque refresh tokens."""
    config = get_security_config()
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if user is None:
        _constant_time_dummy_verify(form_data.password)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    now = _utcnow()
    if user.locked_until is not None and _as_utc(user.locked_until) > now:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account temporarily locked")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    if not _verify_password(form_data.password, user.hashed_password):
        user.failed_login_attempts += 1
        user.last_failed_login = now
        if user.failed_login_attempts >= config.MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=config.LOCKOUT_DURATION_MINUTES)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    user.failed_login_attempts = 0
    user.last_failed_login = None
    user.locked_until = None
    user.last_login = now

    refresh_plain, refresh_hash, refresh_expires = create_refresh_token()
    db.add(
        RefreshToken(
            token_hash=refresh_hash,
            user_id=user.id,
            jti=uuid4().hex,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            expires_at=refresh_expires,
        )
    )
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_plain,
        expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Rotate a refresh token atomically and revoke the consumed credential."""
    now = _utcnow()
    digest = hash_refresh_token(payload.refresh_token)

    # Lock the credential row so concurrent refresh requests cannot both consume it.
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == digest,
            RefreshToken.is_revoked.is_(False),
        )
        .with_for_update()
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if _as_utc(stored.expires_at) <= now:
        stored.is_revoked = True
        stored.revoked_at = now
        stored.revoked_reason = "expired"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user_result = await db.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE or not user.is_active:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")

    stored.is_revoked = True
    stored.revoked_at = now
    stored.revoked_reason = "rotated"
    stored.last_used_at = now

    refresh_plain, refresh_hash, refresh_expires = create_refresh_token()
    db.add(
        RefreshToken(
            token_hash=refresh_hash,
            user_id=user.id,
            jti=uuid4().hex,
            expires_at=refresh_expires,
        )
    )
    await db.commit()

    config = get_security_config()
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_plain,
        expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the supplied refresh token if it belongs to the authenticated user."""
    digest = hash_refresh_token(payload.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest,
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked.is_(False),
        )
    )
    stored = result.scalar_one_or_none()
    if stored is not None:
        stored.is_revoked = True
        stored.revoked_at = _utcnow()
        stored.revoked_reason = "logout"
        await db.commit()
    return None
