"""JWT access-token and opaque refresh-token primitives.

Access tokens are short-lived signed JWTs. Refresh tokens are opaque random
values; only their SHA-256 digest is persisted, so a database leak does not
immediately expose usable refresh credentials.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import jwt

from app.config import get_security_config


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int) -> str:
    config = get_security_config()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "jti": str(uuid4()),
        "iss": config.JWT_ISSUER,
        "aud": config.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def create_refresh_token() -> tuple[str, str, datetime]:
    config = get_security_config()
    token = secrets.token_urlsafe(64)
    digest = hash_refresh_token(token)
    expires_at = utcnow() + timedelta(days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    return token, digest, expires_at


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
