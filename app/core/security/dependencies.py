"""Authentication dependencies used by FastAPI routes and RBAC.

This module is intentionally independent from routers to avoid circular imports.
JWT verification is performed here; authorization remains in ``app.core.rbac``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_security_config
from app.db.models.auth import User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Could not validate authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_access_token(token: str) -> dict:
    """Validate an access JWT and return its claims.

    The token must contain ``sub`` and must match configured issuer/audience.
    ``python-jose`` performs signature and standard time-claim validation.
    """
    config = get_security_config()
    try:
        return jwt.decode(
            token,
            config.JWT_SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM],
            issuer=config.JWT_ISSUER,
            audience=config.JWT_AUDIENCE,
            options={"require_sub": True, "require_exp": True},
        )
    except JWTError as exc:
        raise _unauthorized() from exc


async def _load_user(db: AsyncSession, subject: str) -> User:
    """Load an active user with RBAC relationships eagerly available."""
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Invalid token subject") from exc

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.user_roles)
            .selectinload("role")
            .selectinload("role_permissions")
            .selectinload("permission"),
            selectinload(User.user_permissions).selectinload("permission"),
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _unauthorized("User is inactive or does not exist")
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """FastAPI dependency returning the authenticated active user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Authentication required")

    claims = _decode_access_token(credentials.credentials)
    return await _load_user(db, claims["sub"])


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Return the current user when credentials are valid, otherwise ``None``."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    claims = _decode_access_token(credentials.credentials)
    return await _load_user(db, claims["sub"])
