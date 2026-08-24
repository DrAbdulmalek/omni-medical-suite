"""Role-based access control helpers.

Authorization is deliberately kept independent from the authentication router.
FastAPI resolves ``get_current_user`` as a dependency before these helpers run.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from datetime import datetime
from functools import wraps

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.auth import (
    Role,
    User,
    UserRole,
    UserRoleAssignment,
)

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RBACError(Exception):
    """Custom RBAC exception."""

    def __init__(self, message: str, status_code: int = status.HTTP_403_FORBIDDEN):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def get_user_permissions(user: User, db: AsyncSession | None = None) -> list[str]:
    """Return effective permission codenames for an already-loaded user."""
    if not user:
        return []

    permissions: set[str] = set()
    for assignment in user.user_roles:
        if not assignment.is_active:
            continue
        for role_permission in assignment.role.role_permissions:
            permissions.add(role_permission.permission.codename)

    for assignment in user.user_permissions:
        if not assignment.is_active:
            continue
        if assignment.is_denied:
            permissions.discard(assignment.permission.codename)
        else:
            permissions.add(assignment.permission.codename)

    return sorted(permissions)


async def check_permission(user: User, required_permission: str, db: AsyncSession | None = None) -> bool:
    return required_permission in await get_user_permissions(user, db)


async def check_any_permission(
    user: User,
    required_permissions: list[str],
    db: AsyncSession | None = None,
) -> bool:
    permissions = set(await get_user_permissions(user, db))
    return bool(permissions.intersection(required_permissions))


async def check_all_permissions(
    user: User,
    required_permissions: list[str],
    db: AsyncSession | None = None,
) -> bool:
    permissions = set(await get_user_permissions(user, db))
    return set(required_permissions).issubset(permissions)


async def check_role(user: User, required_role: str, db: AsyncSession | None = None) -> bool:
    if not user:
        return False
    return any(
        assignment.is_active and assignment.role.name == required_role
        for assignment in user.user_roles
    )


async def check_min_role_level(user: User, min_level: int, db: AsyncSession | None = None) -> bool:
    if not user:
        return False
    return any(
        assignment.is_active and assignment.role.level >= min_level
        for assignment in user.user_roles
    )


def _require_authenticated_user(kwargs: dict) -> User:
    """Get the user already resolved by FastAPI; never perform auth manually."""
    user = kwargs.get("current_user")
    if not isinstance(user, User):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(required_permission: str) -> Callable:
    """Decorator for routes that already declare ``current_user`` and ``db`` dependencies."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = _require_authenticated_user(kwargs)
            db = kwargs.get("db")
            if not await check_permission(user, required_permission, db):
                logger.warning(
                    "Permission denied: user=%s id=%s endpoint=%s permission=%s",
                    user.username,
                    user.id,
                    func.__name__,
                    required_permission,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{required_permission}' required",
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(required_permissions: list[str]) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = _require_authenticated_user(kwargs)
            if not await check_any_permission(user, required_permissions, kwargs.get("db")):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of these permissions required: {', '.join(required_permissions)}",
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(required_role: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = _require_authenticated_user(kwargs)
            if not await check_role(user, required_role, kwargs.get("db")):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{required_role}' required",
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_min_role_level(min_level: int) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = _require_authenticated_user(kwargs)
            if not await check_min_role_level(user, min_level, kwargs.get("db")):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role level {min_level} required",
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class RBACMiddleware:
    """Compatibility middleware; route-level dependencies perform authorization."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request, call_next):
        return await call_next(request)


async def create_default_admin(
    db: AsyncSession,
    username: str = "admin",
    email: str = "admin@omni-medical-suite.local",
    password: str | None = None,
    full_name: str = "System Administrator",
) -> User:
    """Create an administrator only when explicitly invoked by setup code."""
    result = await db.execute(select(User).where(User.username == username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        return existing_user

    if not password:
        password = secrets.token_urlsafe(24)
        logger.warning("Generated one-time admin password for %s; rotate it immediately", username)

    user = User(
        username=username,
        email=email,
        hashed_password=pwd_context.hash(password),
        full_name=full_name,
        default_role=UserRole.SUPER_ADMIN,
        is_superuser=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()

    role_result = await db.execute(
        select(Role).where(Role.name == "Super Admin")
    )
    super_admin_role = role_result.scalar_one_or_none()
    if super_admin_role:
        db.add(
            UserRoleAssignment(
                user_id=user.id,
                role_id=super_admin_role.id,
                assigned_by=None,
                assigned_at=datetime.utcnow(),
                is_active=True,
            )
        )

    await db.commit()
    await db.refresh(user)
    return user
