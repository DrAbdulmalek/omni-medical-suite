"""Per-user rate limiting middleware for OmniMedical Suite API.

Uses ``slowapi`` with user-identity-based keys extracted from JWT tokens
or ``X-User-ID`` headers.  Different rate limits are applied based on
the user's subscription plan (free / pro / enterprise).
"""

from __future__ import annotations

import logging
from typing import Dict

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limiter instance
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])

# ---------------------------------------------------------------------------
# User-identity extraction
# ---------------------------------------------------------------------------

def get_user_key(request: Request) -> str:
    """Extract a unique user identifier from the request.

    Priority:
    1. ``X-User-ID`` header
    2. ``sub`` claim from JWT in ``Authorization`` header
    3. Fallback to remote address
    """
    # 1. Explicit header
    user_id = request.headers.get("X-User-ID")
    if user_id:
        return f"user:{user_id}"

    # 2. JWT extraction
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            # SECRET_KEY should be imported from settings in production
            from app.core.config import settings
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
            )
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            logger.debug("Failed to extract user from JWT token.")

    return f"ip:{get_remote_address(request)}"


# ---------------------------------------------------------------------------
# Plan-based rate limits
# ---------------------------------------------------------------------------

PLAN_LIMITS: Dict[str, str] = {
    "free": "10/minute",
    "pro": "500/minute",
    "enterprise": "5000/minute",
}

DEFAULT_PLAN_LIMIT = "10/minute"


def get_user_rate_limit(user_key: str) -> str:
    """Return the rate-limit string for a given user key.

    In production, the user's plan should be fetched from the database
    or a caching layer.  For now, free users get the default limit.
    """
    # TODO: Fetch user plan from DB/cache
    # user_plan = await get_user_plan(user_key)
    return DEFAULT_PLAN_LIMIT
