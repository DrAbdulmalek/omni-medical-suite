"""
Unit tests for Circuit Breaker module.
Tests: state transitions, failure counting, recovery, metrics, registry.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from services.api.ocr.circuit_breaker import (
    CircuitBreaker, CircuitBreakerRegistry, CircuitBreakerConfig,
    CircuitBreakerError, CircuitState
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.delete = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    return redis


@pytest.fixture
def circuit_breaker(mock_redis):
    """Create a circuit breaker with test config."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=5,
        half_open_max_calls=2,
        success_threshold=2
    )
    return CircuitBreaker("test_engine", mock_redis, config)


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 2

    def test_engine_specific_config(self):
        """Test per-engine configuration overrides."""
        mistral = CircuitBreakerConfig.default_for_engine("mistral")
        assert mistral.failure_threshold == 3
        assert mistral.recovery_timeout == 60

        easyocr = CircuitBreakerConfig.default_for_engine("easyocr")
        assert easyocr.failure_threshold == 10
        assert easyocr.recovery_timeout == 15

        unknown = CircuitBreakerConfig.default_for_engine("unknown")
        assert unknown.failure_threshold == 5  # Default


class TestCircuitBreakerState:
    """Test circuit breaker state management."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, circuit_breaker, mock_redis):
        """Test initial state is CLOSED."""
        mock_redis.get.return_value = None

        state = await circuit_breaker.get_state()

        assert state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_state_open(self, circuit_breaker, mock_redis):
        """Test OPEN state detection."""
        mock_redis.get.return_value = "open"

        state = await circuit_breaker.get_state()

        assert state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_force_open(self, circuit_breaker, mock_redis):
        """Test manual circuit opening."""
        await circuit_breaker.force_open()

        mock_redis.set.assert_called()
        assert mock_redis.set.call_args[0][1] == "open"

    @pytest.mark.asyncio
    async def test_force_close(self, circuit_breaker, mock_redis):
        """Test manual circuit closing."""
        await circuit_breaker.force_close()

        mock_redis.set.assert_called()
        assert mock_redis.set.call_args[0][1] == "closed"
        mock_redis.delete.assert_called_once()


class TestCircuitBreakerCall:
    """Test circuit breaker call protection."""

    @pytest.mark.asyncio
    async def test_successful_call(self, circuit_breaker, mock_redis):
        """Test successful call passes through."""
        mock_redis.get.return_value = None  # CLOSED state

        async def success_func():
            return {"result": "success"}

        result = await circuit_breaker.call(success_func)

        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_call_failure_count(self, circuit_breaker, mock_redis):
        """Test failure increments counter."""
        mock_redis.get.return_value = None  # CLOSED state
        mock_redis.incr.return_value = 1

        async def fail_func():
            raise ConnectionError("API down")

        with pytest.raises(ConnectionError):
            await circuit_breaker.call(fail_func)

        mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, circuit_breaker, mock_redis):
        """Test circuit opens after failure threshold."""
        mock_redis.get.side_effect = [
            None,       # Initial state check
            None,       # Last failure check (first fail)
            None,       # State check (second fail)
            None,       # Last failure check
            None,       # State check (third fail)
            None,       # Last failure check
        ]
        mock_redis.incr.side_effect = [1, 2, 3]  # Failure count

        async def fail_func():
            raise ConnectionError("API down")

        # First two failures - circuit still closed
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(fail_func)
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(fail_func)

        # Third failure - circuit should open
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(fail_func)

        # Check state was set to OPEN
        set_calls = [call for call in mock_redis.set.call_args_list 
                     if call[0][0] == "circuit_breaker:test_engine:state"]
        assert any(call[0][1] == "open" for call in set_calls)

    @pytest.mark.asyncio
    async def test_open_circuit_blocks_calls(self, circuit_breaker, mock_redis):
        """Test OPEN circuit blocks all calls."""
        mock_redis.get.side_effect = [
            "open",     # State is OPEN
            str(int(time.time())),  # Recent last failure
        ]

        async def any_func():
            return "should not execute"

        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.call(any_func)

        assert exc_info.value.engine_name == "test_engine"
        assert exc_info.value.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_transition(self, circuit_breaker, mock_redis):
        """Test transition to HALF_OPEN after recovery timeout."""
        old_time = int(time.time()) - 10  # 10 seconds ago
        mock_redis.get.side_effect = [
            "open",              # State is OPEN
            str(old_time),       # Last failure was 10s ago (> 5s timeout)
        ]

        async def any_func():
            return "success"

        # Should transition to HALF_OPEN and execute
        result = await circuit_breaker.call(any_func)

        assert result == "success"
        # State should be set to half_open
        mock_redis.set.assert_any_call(
            "circuit_breaker:test_engine:state", 
            "half_open"
        )

    @pytest.mark.asyncio
    async def test_half_open_limits_calls(self, circuit_breaker, mock_redis):
        """Test HALF_OPEN limits test calls."""
        mock_redis.get.side_effect = [
            "half_open",    # State
            "2",            # Already made 2 calls (max is 2)
        ]

        async def any_func():
            return "success"

        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.call(any_func)

        assert exc_info.value.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_success_closes_circuit(self, circuit_breaker, mock_redis):
        """Test success in HALF_OPEN closes circuit."""
        mock_redis.get.side_effect = [
            "half_open",    # State
            "1",            # 1 call made
        ]
        mock_redis.incr.return_value = 2  # 2nd success

        async def success_func():
            return "success"

        result = await circuit_breaker.call(success_func)

        assert result == "success"
        # Should close circuit after success_threshold successes
        mock_redis.set.assert_any_call(
            "circuit_breaker:test_engine:state",
            "closed"
        )

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, circuit_breaker, mock_redis):
        """Test failure in HALF_OPEN immediately reopens circuit."""
        mock_redis.get.return_value = "half_open"

        async def fail_func():
            raise ConnectionError("Still down")

        with pytest.raises(ConnectionError):
            await circuit_breaker.call(fail_func)

        mock_redis.set.assert_any_call(
            "circuit_breaker:test_engine:state",
            "open"
        )


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, circuit_breaker, mock_redis):
        """Test metrics retrieval."""
        mock_redis.get.side_effect = [
            "open",         # State
            "5",            # Failures
            str(int(time.time()) - 30),  # Last failure 30s ago
            "1",            # Half-open calls
        ]

        metrics = await circuit_breaker.get_metrics()

        assert metrics["engine"] == "test_engine"
        assert metrics["state"] == "open"
        assert metrics["failures_count"] == 5
        assert metrics["failure_threshold"] == 3
        assert metrics["half_open_calls"] == 1


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""

    @pytest.mark.asyncio
    async def test_init_registry(self, mock_redis):
        """Test registry initialization."""
        await CircuitBreakerRegistry.init(mock_redis)

        assert CircuitBreakerRegistry._redis is not None
        assert "mistral" in CircuitBreakerRegistry._breakers
        assert "openai" in CircuitBreakerRegistry._breakers

    @pytest.mark.asyncio
    async def test_get_breaker(self, mock_redis):
        """Test retrieving circuit breaker."""
        await CircuitBreakerRegistry.init(mock_redis)

        cb = CircuitBreakerRegistry.get("mistral")

        assert isinstance(cb, CircuitBreaker)
        assert cb.engine_name == "mistral"

    def test_get_without_init(self):
        """Test getting breaker without initialization fails."""
        CircuitBreakerRegistry._redis = None
        CircuitBreakerRegistry._breakers = {}

        with pytest.raises(RuntimeError):
            CircuitBreakerRegistry.get("mistral")

    @pytest.mark.asyncio
    async def test_get_all_metrics(self, mock_redis):
        """Test retrieving all metrics."""
        await CircuitBreakerRegistry.init(mock_redis)
        mock_redis.get.side_effect = ["closed", "0", None, "0"]

        metrics = await CircuitBreakerRegistry.get_all_metrics()

        assert "mistral" in metrics
        assert "openai" in metrics

    @pytest.mark.asyncio
    async def test_reset_all(self, mock_redis):
        """Test resetting all breakers."""
        await CircuitBreakerRegistry.init(mock_redis)

        await CircuitBreakerRegistry.reset_all()

        # Should call force_close on all breakers
        assert mock_redis.set.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
