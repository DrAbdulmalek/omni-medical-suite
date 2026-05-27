"""
Unit tests for Per-User Rate Limiter.
Tests: tier limits, sliding window, burst, penalty box, admin override.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from services.api.middleware.rate_limit import (
    UserRateLimiter, RateLimitConfig, Tier, RateLimitExceeded
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.set = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.zcard = AsyncMock(return_value=0)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrange = AsyncMock(return_value=[])
    redis.delete = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    redis.hset = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    return redis


@pytest.fixture
def limiter(mock_redis):
    """Create a rate limiter instance."""
    return UserRateLimiter(mock_redis)


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_default_configs(self):
        """Test default tier configurations."""
        configs = RateLimitConfig.defaults()

        assert Tier.FREE in configs
        assert Tier.STANDARD in configs
        assert Tier.PREMIUM in configs
        assert Tier.ENTERPRISE in configs
        assert Tier.UNLIMITED in configs

        # Verify specific values
        assert configs[Tier.FREE].requests == 10
        assert configs[Tier.STANDARD].requests == 100
        assert configs[Tier.PREMIUM].requests == 500
        assert configs[Tier.ENTERPRISE].requests == 2000

    def test_burst_values(self):
        """Test burst allowances."""
        configs = RateLimitConfig.defaults()

        assert configs[Tier.FREE].burst == 2
        assert configs[Tier.STANDARD].burst == 10
        assert configs[Tier.PREMIUM].burst == 50


class TestRateLimitCheck:
    """Test rate limit checking."""

    @pytest.mark.asyncio
    async def test_allowed_request(self, limiter, mock_redis):
        """Test request within limit is allowed."""
        mock_redis.zcard.return_value = 5  # 5 requests so far

        allowed, headers = await limiter.check_and_record("user_123", "standard")

        assert allowed is True
        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "105"  # 100 + 10 burst - 5 - 1

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, limiter, mock_redis):
        """Test request over limit raises exception."""
        mock_redis.zcard.return_value = 110  # Over standard limit + burst

        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.check_and_record("user_123", "standard")

        assert exc_info.value.user_id == "user_123"
        assert exc_info.value.tier == "standard"
        assert exc_info.value.limit == 100

    @pytest.mark.asyncio
    async def test_free_tier_limit(self, limiter, mock_redis):
        """Test free tier low limit."""
        mock_redis.zcard.return_value = 12  # Over free limit + burst

        with pytest.raises(RateLimitExceeded):
            await limiter.check_and_record("user_free", "free")

    @pytest.mark.asyncio
    async def test_unlimited_tier(self, limiter, mock_redis):
        """Test unlimited tier never blocks."""
        mock_redis.zcard.return_value = 999999

        allowed, headers = await limiter.check_and_record("admin", "unlimited")

        assert allowed is True

    @pytest.mark.asyncio
    async def test_request_cost(self, limiter, mock_redis):
        """Test requests with higher cost."""
        mock_redis.zcard.return_value = 50

        allowed, headers = await limiter.check_and_record(
            "user_123", "standard", cost=5
        )

        assert allowed is True
        # Should add 5 entries
        assert mock_redis.zadd.call_count == 5

    @pytest.mark.asyncio
    async def test_sliding_window(self, limiter, mock_redis):
        """Test sliding window removes old entries."""
        current_time = int(time.time())

        await limiter.check_and_record("user_123", "standard")

        # Should remove entries older than window
        mock_redis.zremrangebyscore.assert_called_once()
        call_args = mock_redis.zremrangebyscore.call_args
        assert call_args[0][1] == 0  # min score
        assert call_args[0][2] <= current_time  # max score (current - window)


class TestPenaltyBox:
    """Test penalty box functionality."""

    @pytest.mark.asyncio
    async def test_penalty_box_blocks(self, limiter, mock_redis):
        """Test penalty box blocks all requests."""
        future_time = int(time.time()) + 300
        mock_redis.get.return_value = str(future_time)

        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.check_and_record("abuser", "standard")

        assert exc_info.value.limit == 0
        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_penalty_after_repeated_violations(self, limiter, mock_redis):
        """Test penalty applied after threshold violations."""
        mock_redis.zcard.return_value = 999  # Always over limit
        mock_redis.incr.side_effect = [1, 2, 3, 4, 5]  # Violation count

        # Make requests until penalty threshold
        for _ in range(5):
            try:
                await limiter.check_and_record("abuser", "standard")
            except RateLimitExceeded:
                pass

        # After 5 violations, penalty box should be applied
        mock_redis.setex.assert_called()


class TestRateLimitStatus:
    """Test rate limit status retrieval."""

    @pytest.mark.asyncio
    async def test_get_status(self, limiter, mock_redis):
        """Test getting current rate limit status."""
        mock_redis.zcard.return_value = 25
        mock_redis.get.return_value = None  # No penalty

        status = await limiter.get_status("user_123", "standard")

        assert status["user_id"] == "user_123"
        assert status["tier"] == "standard"
        assert status["limit"] == 100
        assert status["burst"] == 10
        assert status["used"] == 25
        assert status["remaining"] == 85  # 100 + 10 - 25
        assert status["in_penalty_box"] is False

    @pytest.mark.asyncio
    async def test_status_with_penalty(self, limiter, mock_redis):
        """Test status when in penalty box."""
        mock_redis.zcard.return_value = 50
        mock_redis.get.return_value = str(int(time.time()) + 120)  # 2 min penalty

        status = await limiter.get_status("user_123", "standard")

        assert status["in_penalty_box"] is True
        assert status["penalty_remaining_seconds"] > 0


class TestAdminFunctions:
    """Test admin override functions."""

    @pytest.mark.asyncio
    async def test_reset_user(self, limiter, mock_redis):
        """Test resetting user counters."""
        mock_redis.keys.return_value = [
            "rate_limit:user_123:60",
            "rate_limit:user_123:120"
        ]

        await limiter.reset_user("user_123")

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_admin_override(self, limiter, mock_redis):
        """Test admin override for specific user."""
        await limiter.admin_override(
            "vip_user",
            custom_limit=1000,
            custom_window=60,
            bypass=False
        )

        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        assert call_args[1]["mapping"]["limit"] == "1000"

    @pytest.mark.asyncio
    async def test_admin_bypass(self, limiter, mock_redis):
        """Test admin bypass completely disables rate limiting."""
        await limiter.admin_override("admin_user", bypass=True)

        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        assert call_args[1]["mapping"]["bypass"] == "True"


class TestRateLimitHeaders:
    """Test rate limit response headers."""

    @pytest.mark.asyncio
    async def test_headers_format(self, limiter, mock_redis):
        """Test headers contain all required fields."""
        mock_redis.zcard.return_value = 30

        allowed, headers = await limiter.check_and_record("user_123", "premium")

        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Burst" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert "X-RateLimit-Tier" in headers
        assert headers["X-RateLimit-Tier"] == "premium"

    @pytest.mark.asyncio
    async def test_remaining_calculation(self, limiter, mock_redis):
        """Test remaining requests calculation."""
        mock_redis.zcard.return_value = 450  # 450 used

        allowed, headers = await limiter.check_and_record("user_123", "premium")

        # Premium: 500 + 50 burst = 550 total, 450 used, 1 current = 99 remaining
        assert headers["X-RateLimit-Remaining"] == "99"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
