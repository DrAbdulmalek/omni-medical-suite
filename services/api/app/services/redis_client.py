"""Optional async Redis client with graceful degradation.

Redis is treated as an **optional** dependency.  If the server is unavailable
or the ``redis`` package cannot be imported, every public function returns a
safe default (``None`` / ``False``) so that the rest of the application can
continue operating without interruption.

Usage
-----

>>> from app.services.redis_client import get_redis, init_redis, close_redis
>>> await init_redis()
>>> redis = get_redis()
>>> if redis:
...     await redis.setex("key", "value", ttl=60)
"""

from __future__ import annotations

import logging
import time
from typing import Any

__all__ = [
    "get_redis",
    "init_redis",
    "close_redis",
    "RedisClient",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import guard – redis may not be installed in minimal environments
# ---------------------------------------------------------------------------
_redis_module: Any = None
_available = False

try:
    import redis.asyncio as _redis_asyncio  # type: ignore[import-untyped]

    _redis_module = _redis_asyncio
    _available = True
except Exception:  # pragma: no cover – ImportError, etc.
    logger.warning(
        "redis package is not installed – caching features will be disabled."
    )

# ---------------------------------------------------------------------------
# Module-level client singleton
# ---------------------------------------------------------------------------
_client: Any = None  # redis.asyncio.Redis | None


async def init_redis(url: str | None = None) -> None:
    """Create and connect the Redis client.

    Parameters
    ----------
    url:
        Redis URL.  When ``None`` the value from settings is used.
    """
    global _client  # noqa: PLW0603

    if not _available:
        logger.info("Redis client not initialised – package unavailable.")
        return

    if _client is not None:
        logger.debug("Redis client already initialised.")
        return

    if url is None:
        from app.core.config import settings  # noqa: WPS433

        url = settings.REDIS_URL

    try:
        _client = _redis_module.Redis.from_url(url, decode_responses=True)
        await _client.ping()
        logger.info("Connected to Redis at %s", url)
    except Exception as exc:
        logger.warning("Failed to connect to Redis (%s): %s", url, exc)
        _client = None


def get_redis() -> Any:
    """Return the connected Redis client or ``None`` if unavailable."""
    return _client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _client  # noqa: PLW0603
    if _client is None:
        return
    try:
        await _client.aclose()
        logger.info("Redis connection closed.")
    except Exception as exc:
        logger.warning("Error closing Redis connection: %s", exc)
    finally:
        _client = None


# ---------------------------------------------------------------------------
# High-level wrapper class
# ---------------------------------------------------------------------------
class RedisClient:
    """Thin async wrapper around ``redis.asyncio.Redis``.

    Every method silently degrades when Redis is unavailable – it never
    raises a connection error, making it safe to call from any code-path.
    """

    @staticmethod
    async def setex(key: str, value: str, ttl: int) -> bool:
        """Set *key* to *value* with an expiration of *ttl* seconds.

        Returns ``True`` on success, ``False`` if Redis is unavailable.
        """
        if _client is None:
            return False
        try:
            await _client.setex(key, ttl, value)
            return True
        except Exception as exc:
            logger.debug("Redis SETEX error for key '%s': %s", key, exc)
            return False

    @staticmethod
    async def get(key: str) -> str | None:
        """Return the value of *key* or ``None`` on miss / Redis failure."""
        if _client is None:
            return None
        try:
            return await _client.get(key)
        except Exception as exc:
            logger.debug("Redis GET error for key '%s': %s", key, exc)
            return None

    @staticmethod
    async def delete(key: str) -> bool:
        """Delete *key*.  Returns ``True`` if the key was removed."""
        if _client is None:
            return False
        try:
            count = await _client.delete(key)
            return count > 0
        except Exception as exc:
            logger.debug("Redis DELETE error for key '%s': %s", key, exc)
            return False

    @staticmethod
    async def health_check() -> bool:
        """Return ``True`` if the Redis server is responsive."""
        if _client is None:
            return False
        try:
            start = time.monotonic()
            await _client.ping()
            latency_ms = (time.monotonic() - start) * 1000
            logger.debug("Redis health check OK (%.1f ms)", latency_ms)
            return True
        except Exception as exc:
            logger.debug("Redis health check failed: %s", exc)
            return False

    @staticmethod
    async def exists(key: str) -> bool:
        """Check whether *key* exists."""
        if _client is None:
            return False
        try:
            return bool(await _client.exists(key))
        except Exception:
            return False

    @staticmethod
    async def incr(key: str) -> int | None:
        """Atomically increment *key*.  Returns new value or ``None``."""
        if _client is None:
            return None
        try:
            return await _client.incr(key)
        except Exception:
            return None

    @staticmethod
    async def expire(key: str, ttl: int) -> bool:
        """Set a TTL on *key*.  Returns ``True`` on success."""
        if _client is None:
            return False
        try:
            return bool(await _client.expire(key, ttl))
        except Exception:
            return False
