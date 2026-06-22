"""
Circuit Breaker for External OCR Engines
Protects the system from cascading failures when external APIs (Mistral, etc.) are down.
Implements the standard circuit breaker pattern: CLOSED → OPEN → HALF-OPEN.
"""

import asyncio
import time
from enum import Enum
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field

import redis.asyncio as redis


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: int = 30          # Seconds before half-open
    half_open_max_calls: int = 3        # Test calls in half-open
    success_threshold: int = 2          # Successes to close

    # Per-engine overrides
    @classmethod
    def default_for_engine(cls, engine_name: str) -> "CircuitBreakerConfig":
        configs = {
            "mistral": cls(failure_threshold=3, recovery_timeout=60),
            "openai": cls(failure_threshold=5, recovery_timeout=30),
            "anthropic": cls(failure_threshold=5, recovery_timeout=30),
            "easyocr": cls(failure_threshold=10, recovery_timeout=15),
            "trocr": cls(failure_threshold=8, recovery_timeout=20),
        }
        return configs.get(engine_name, cls())


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    def __init__(self, engine_name: str, retry_after: int, state: CircuitState):
        self.engine_name = engine_name
        self.retry_after = retry_after
        self.state = state
        super().__init__(
            f"Circuit breaker for '{engine_name}' is {state.value}. "
            f"Retry after {retry_after}s."
        )


class CircuitBreaker:
    """
    Per-engine circuit breaker with Redis-backed state.

    Usage:
        cb = CircuitBreakerRegistry.get("mistral")
        try:
            result = await cb.call(mistral_ocr_func, image_bytes)
        except CircuitBreakerError:
            # Fallback to next engine
            pass
    """

    def __init__(
        self,
        engine_name: str,
        redis_client: redis.Redis,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.engine_name = engine_name
        self.redis = redis_client
        self.config = config or CircuitBreakerConfig.default_for_engine(engine_name)
        self._key_prefix = f"circuit_breaker:{engine_name}"

    def _state_key(self) -> str:
        return f"{self._key_prefix}:state"

    def _failures_key(self) -> str:
        return f"{self._key_prefix}:failures"

    def _last_failure_key(self) -> str:
        return f"{self._key_prefix}:last_failure"

    def _half_open_calls_key(self) -> str:
        return f"{self._key_prefix}:half_open_calls"

    def _successes_key(self) -> str:
        return f"{self._key_prefix}:successes"

    async def get_state(self) -> CircuitState:
        """Get current circuit state from Redis."""
        state_str = await self.redis.get(self._state_key())
        if not state_str:
            return CircuitState.CLOSED
        return CircuitState(state_str)

    async def _set_state(self, state: CircuitState) -> None:
        await self.redis.set(self._state_key(), state.value)

    async def call(
        self,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to call (e.g., OCR engine API call)
            *args, **kwargs: Arguments for the function

        Returns:
            Result from func

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Exception: Original exception if call fails
        """
        state = await self.get_state()

        if state == CircuitState.OPEN:
            last_failure = await self.redis.get(self._last_failure_key())
            if last_failure:
                elapsed = time.time() - float(last_failure)
                if elapsed < self.config.recovery_timeout:
                    raise CircuitBreakerError(
                        self.engine_name,
                        int(self.config.recovery_timeout - elapsed),
                        state
                    )
                else:
                    # Transition to HALF_OPEN
                    await self._set_state(CircuitState.HALF_OPEN)
                    await self.redis.set(self._half_open_calls_key(), 0)
                    state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerError(
                    self.engine_name,
                    self.config.recovery_timeout,
                    state
                )

        if state == CircuitState.HALF_OPEN:
            calls = int(await self.redis.get(self._half_open_calls_key()) or 0)
            if calls >= self.config.half_open_max_calls:
                raise CircuitBreakerError(
                    self.engine_name,
                    self.config.recovery_timeout,
                    state
                )
            await self.redis.incr(self._half_open_calls_key())

        # Execute the call
        try:
            result = await func(*args, **kwargs)
            await self._on_success(state)
            return result
        except Exception as e:
            await self._on_failure(state)
            raise

    async def _on_success(self, state: CircuitState) -> None:
        """Handle successful call."""
        if state == CircuitState.HALF_OPEN:
            successes = await self.redis.incr(self._successes_key())
            if successes >= self.config.success_threshold:
                # Close the circuit
                await self._set_state(CircuitState.CLOSED)
                await self.redis.delete(
                    self._failures_key(),
                    self._last_failure_key(),
                    self._half_open_calls_key(),
                    self._successes_key()
                )
        else:
            # Reset failure count on success in CLOSED state
            await self.redis.delete(self._failures_key())

    async def _on_failure(self, state: CircuitState) -> None:
        """Handle failed call."""
        failures = await self.redis.incr(self._failures_key())
        await self.redis.set(self._last_failure_key(), time.time())

        if state == CircuitState.HALF_OPEN:
            # Back to OPEN immediately
            await self._set_state(CircuitState.OPEN)
        elif failures >= self.config.failure_threshold:
            await self._set_state(CircuitState.OPEN)

    async def force_open(self) -> None:
        """Manually open the circuit (for maintenance)."""
        await self._set_state(CircuitState.OPEN)
        await self.redis.set(self._last_failure_key(), time.time())

    async def force_close(self) -> None:
        """Manually close the circuit."""
        await self._set_state(CircuitState.CLOSED)
        await self.redis.delete(
            self._failures_key(),
            self._last_failure_key(),
            self._half_open_calls_key(),
            self._successes_key()
        )

    async def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        state = await self.get_state()
        failures = int(await self.redis.get(self._failures_key()) or 0)
        last_failure = await self.redis.get(self._last_failure_key())
        half_open_calls = int(await self.redis.get(self._half_open_calls_key()) or 0)

        last_failure_time = None
        if last_failure:
            last_failure_time = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(float(last_failure))
            )

        return {
            "engine": self.engine_name,
            "state": state.value,
            "failures_count": failures,
            "failure_threshold": self.config.failure_threshold,
            "last_failure": last_failure_time,
            "half_open_calls": half_open_calls,
            "recovery_timeout": self.config.recovery_timeout,
            "success_threshold": self.config.success_threshold
        }


class CircuitBreakerRegistry:
    """
    Central registry for all circuit breakers.

    Usage:
        await CircuitBreakerRegistry.init(redis_client)
        cb = CircuitBreakerRegistry.get("mistral")
        result = await cb.call(mistral_api.process, image)
    """

    _breakers: Dict[str, CircuitBreaker] = {}
    _redis: Optional[redis.Redis] = None

    @classmethod
    async def init(cls, redis_client: redis.Redis) -> None:
        """Initialize registry with Redis connection."""
        cls._redis = redis_client
        # Pre-register known engines
        engines = ["mistral", "openai", "anthropic", "easyocr", "trocr"]
        for engine in engines:
            cls._breakers[engine] = CircuitBreaker(engine, redis_client)

    @classmethod
    def get(cls, engine_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for an engine."""
        if engine_name not in cls._breakers:
            if not cls._redis:
                raise RuntimeError("CircuitBreakerRegistry not initialized. Call init() first.")
            cls._breakers[engine_name] = CircuitBreaker(engine_name, cls._redis)
        return cls._breakers[engine_name]

    @classmethod
    async def get_all_metrics(cls) -> Dict[str, Any]:
        """Get metrics for all registered circuit breakers."""
        metrics = {}
        for name, cb in cls._breakers.items():
            metrics[name] = await cb.get_metrics()
        return metrics

    @classmethod
    async def reset_all(cls) -> None:
        """Reset all circuit breakers to CLOSED state."""
        for cb in cls._breakers.values():
            await cb.force_close()
