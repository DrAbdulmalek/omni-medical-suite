"""Security utilities for OmniMedicalSuite.

Provides API-key verification, password hashing (bcrypt via passlib),
JWT access-token creation / verification, and an in-memory sliding-window
rate limiter.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

import jwt
from passlib.context import CryptContext

__all__ = [
    "verify_api_key",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "RateLimiter",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing context
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)

# ---------------------------------------------------------------------------
# JWT constants
# ---------------------------------------------------------------------------
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY: str | None = None


def _get_jwt_secret() -> str:
    """Lazily resolve the JWT signing secret.

    Falls back to a SHA-256 hash of the API key when a dedicated secret is
    not available.  In production, always set ``JWT_SECRET_KEY`` explicitly.
    """
    global JWT_SECRET_KEY  # noqa: PLW0603
    if JWT_SECRET_KEY is not None:
        return JWT_SECRET_KEY

    # Lazy import to avoid circular dependency
    from app.core.config import settings  # noqa: WPS433

    JWT_SECRET_KEY = hashlib.sha256(
        f"omni-medical-jwt-{settings.API_KEY}".encode()
    ).hexdigest()
    return JWT_SECRET_KEY


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------
def verify_api_key(api_key: str, expected: str) -> bool:
    """Constant-time comparison of *api_key* against the *expected* value.

    Uses :func:`hmac.compare_digest` to prevent timing attacks.
    """
    if not api_key or not expected:
        return False
    return hmac.compare_digest(api_key, expected)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches the *hashed* password."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------
def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Parameters
    ----------
    data:
        Payload to encode (e.g. ``{"sub": "user_id"}``).
    expires_delta:
        Token lifetime.  Defaults to 30 minutes when *None*.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None else timedelta(minutes=30)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises
    ------
    jwt.ExpiredSignatureError, jwt.InvalidTokenError
        On expired or malformed tokens.
    """
    return jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# Rate limiter – sliding window (in-memory)
# ---------------------------------------------------------------------------
class RateLimiter:
    """Thread-safe, in-memory sliding-window rate limiter.

    Parameters
    ----------
    max_requests:
        Maximum number of requests allowed within *window_seconds*.
    window_seconds:
        Duration of the sliding window in seconds.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """Check whether *client_id* is within its rate limit.

        Returns
        -------
        tuple[bool, int]
            ``(allowed, remaining_requests)``.  When *allowed* is ``False``,
            *remaining_requests* is always ``0``.
        """
        now = time.monotonic()
        window_start = now - self._window_seconds

        with self._lock:
            timestamps = self._timestamps[client_id]

            # Prune timestamps outside the current window
            while timestamps and timestamps[0] <= window_start:
                timestamps.pop(0)

            if len(timestamps) >= self._max_requests:
                return False, 0

            timestamps.append(now)
            remaining = self._max_requests - len(timestamps)
            return True, remaining

    def reset(self, client_id: str | None = None) -> None:
        """Clear rate-limit state.

        If *client_id* is ``None``, clears **all** clients.
        """
        with self._lock:
            if client_id is None:
                self._timestamps.clear()
            else:
                self._timestamps.pop(client_id, None)

    @property
    def max_requests(self) -> int:
        return self._max_requests

    @property
    def window_seconds(self) -> int:
        return self._window_seconds
