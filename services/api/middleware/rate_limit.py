"""
Per-User Rate Limiter with Redis Sliding Window
Replaces simple endpoint-level rate limiting with tiered, per-user limits.
Supports burst allowance, penalty boxes, and admin override.
"""

import time
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis


class Tier(Enum):
    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    UNLIMITED = "unlimited"


@dataclass
class RateLimitConfig:
    """Rate limit configuration per tier."""
    requests: int
    window: int  # seconds
    burst: int   # extra requests allowed in burst

    @classmethod
    def defaults(cls) -> Dict[Tier, "RateLimitConfig"]:
        return {
            Tier.FREE: cls(requests=10, window=60, burst=2),
            Tier.STANDARD: cls(requests=100, window=60, burst=10),
            Tier.PREMIUM: cls(requests=500, window=60, burst=50),
            Tier.ENTERPRISE: cls(requests=2000, window=60, burst=200),
            Tier.UNLIMITED: cls(requests=999999, window=60, burst=0),
        }


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(
        self,
        user_id: str,
        tier: str,
        limit: int,
        window: int,
        retry_after: int,
        current: int
    ):
        self.user_id = user_id
        self.tier = tier
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        self.current = current
        super().__init__(
            f"Rate limit exceeded for user {user_id} (tier: {tier}). "
            f"Limit: {limit}/{window}s. Retry after {retry_after}s."
        )


class UserRateLimiter:
    """
    Per-user rate limiter with Redis sliding window.

    Features:
    - Tier-based limits (free/standard/premium/enterprise/unlimited)
    - Sliding window (not fixed window) for fairness
    - Burst allowance for traffic spikes
    - Penalty box for repeated abuse
    - Admin override capability

    Usage:
        limiter = UserRateLimiter(redis_client)
        try:
            await limiter.check_and_record(user_id, tier)
        except RateLimitExceeded as e:
            # Return 429 response
            pass
    """

    PENALTY_THRESHOLD = 5      # Violations before penalty
    PENALTY_DURATION = 300     # 5 minutes penalty box

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.configs = RateLimitConfig.defaults()

    def _key(self, user_id: str, window: int) -> str:
        """Redis key for sliding window counter."""
        return f"rate_limit:{user_id}:{window}"

    def _penalty_key(self, user_id: str) -> str:
        """Redis key for penalty box tracking."""
        return f"rate_limit_penalty:{user_id}"

    def _violations_key(self, user_id: str) -> str:
        """Redis key for violation counter."""
        return f"rate_limit_violations:{user_id}"

    async def _scan_keys(self, pattern: str, count: int = 100) -> List[str]:
        """Non-blocking alternative to redis.keys() using SCAN.

        Uses SCAN instead of KEYS to avoid blocking the Redis server
        in production environments with large datasets.
        """
        return [k async for k in self.redis.scan_iter(pattern, count=count)]

    async def check_and_record(
        self,
        user_id: str,
        tier: str = "standard",
        cost: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit and record the request.

        Args:
            user_id: Unique user identifier
            tier: User subscription tier
            cost: Request cost (default 1, heavy operations may cost more)

        Returns:
            Tuple of (allowed: bool, headers: dict)

        Raises:
            RateLimitExceeded: If limit exceeded
        """
        # Check penalty box
        penalty = await self._check_penalty(user_id)
        if penalty:
            raise RateLimitExceeded(
                user_id=user_id,
                tier=tier,
                limit=0,
                window=self.PENALTY_DURATION,
                retry_after=penalty,
                current=999
            )

        # Get tier config
        tier_enum = Tier(tier) if tier in [t.value for t in Tier] else Tier.STANDARD
        config = self.configs.get(tier_enum, self.configs[Tier.STANDARD])

        now = time.time()
        window_start = int(now) - config.window
        key = self._key(user_id, config.window)

        # Remove old entries outside window
        await self.redis.zremrangebyscore(key, 0, window_start)

        # Count current requests in window
        current = await self.redis.zcard(key)

        # Check limit (including burst)
        effective_limit = config.requests + config.burst
        if current + cost > effective_limit:
            # Record violation
            violations = await self.redis.incr(self._violations_key(user_id))
            await self.redis.expire(self._violations_key(user_id), 3600)

            # Check if penalty box needed
            if violations >= self.PENALTY_THRESHOLD:
                await self._apply_penalty(user_id)

            # Calculate retry after
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1] + config.window - now)
            else:
                retry_after = config.window

            raise RateLimitExceeded(
                user_id=user_id,
                tier=tier,
                limit=config.requests,
                window=config.window,
                retry_after=max(1, retry_after),
                current=current
            )

        # Record request
        for _ in range(cost):
            await self.redis.zadd(key, {f"{now}:{_}": now})
        await self.redis.expire(key, config.window)

        # Calculate headers
        remaining = max(0, effective_limit - current - cost)
        reset_time = int(now) + config.window

        headers = {
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Burst": str(config.burst),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Tier": tier,
        }

        return True, headers

    async def _check_penalty(self, user_id: str) -> int:
        """Check if user is in penalty box. Returns seconds remaining or 0."""
        penalty_until = await self.redis.get(self._penalty_key(user_id))
        if not penalty_until:
            return 0
        remaining = int(penalty_until) - int(time.time())
        return max(0, remaining)

    async def _apply_penalty(self, user_id: str) -> None:
        """Put user in penalty box."""
        until = int(time.time()) + self.PENALTY_DURATION
        await self.redis.setex(
            self._penalty_key(user_id),
            self.PENALTY_DURATION,
            until
        )

    async def get_status(self, user_id: str, tier: str = "standard") -> Dict[str, Any]:
        """Get current rate limit status for a user."""
        tier_enum = Tier(tier) if tier in [t.value for t in Tier] else Tier.STANDARD
        config = self.configs.get(tier_enum, self.configs[Tier.STANDARD])

        key = self._key(user_id, config.window)
        now = time.time()
        window_start = int(now) - config.window

        await self.redis.zremrangebyscore(key, 0, window_start)
        current = await self.redis.zcard(key)

        penalty = await self._check_penalty(user_id)
        violations = int(await self.redis.get(self._violations_key(user_id)) or 0)

        return {
            "user_id": user_id,
            "tier": tier,
            "limit": config.requests,
            "burst": config.burst,
            "used": current,
            "remaining": max(0, config.requests + config.burst - current),
            "window_seconds": config.window,
            "in_penalty_box": penalty > 0,
            "penalty_remaining_seconds": penalty,
            "violations_last_hour": violations,
        }

    async def reset_user(self, user_id: str) -> None:
        """Reset rate limit counters for a user (admin only).

        Uses SCAN instead of KEYS to avoid blocking Redis in production.
        """
        # Find and delete all keys for this user using non-blocking SCAN
        keys = await self._scan_keys(f"rate_limit:{user_id}:*")
        if keys:
            await self.redis.delete(*keys)
        await self.redis.delete(self._penalty_key(user_id))
        await self.redis.delete(self._violations_key(user_id))

    async def admin_override(
        self,
        user_id: str,
        custom_limit: Optional[int] = None,
        custom_window: Optional[int] = None,
        bypass: bool = False
    ) -> None:
        """
        Admin override for specific user.

        Args:
            user_id: Target user
            custom_limit: Override request limit
            custom_window: Override window duration
            bypass: If True, completely bypass rate limiting
        """
        override_key = f"rate_limit_override:{user_id}"
        data = {
            "bypass": bypass,
            "limit": custom_limit,
            "window": custom_window,
            "set_at": time.time()
        }
        await self.redis.hset(override_key, mapping={k: str(v) for k, v in data.items()})
        await self.redis.expire(override_key, 86400)  # 24h override
