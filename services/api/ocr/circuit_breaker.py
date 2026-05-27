"""Circuit Breaker pattern for external OCR engines (e.g., Mistral API).

Uses ``pybreaker`` to prevent cascading failures when external services
become unresponsive.  Also integrates ``tenacity`` for exponential-backoff
retries before opening the circuit.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx
import pybreaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Circuit Breaker instances
# ---------------------------------------------------------------------------

# 5 failures within 60 seconds -> open circuit for 30 seconds
mistral_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    name="mistral_ocr",
)

# Separate breaker for other external APIs
generic_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    name="generic_ocr_api",
)


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def _retry_async(
    stop_after_attempt: int = 3,
    wait_min: float = 2.0,
    wait_max: float = 10.0,
):
    """Return a tenacity retry decorator for async HTTP calls."""
    from tenacity import retry, stop_after_attempt, wait_exponential

    return retry(
        stop=stop_after_attempt(stop_after_attempt),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# External API callers with circuit-breaker protection
# ---------------------------------------------------------------------------

async def call_mistral_ocr(
    file_bytes: bytes,
    api_url: str = "https://api.mistral.ai/v1/ocr",
    api_key: str | None = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Call Mistral OCR API with circuit-breaker protection and retries.

    Raises ``pybreaker.CircuitBreakerError`` when the circuit is open.
    """
    headers: Dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    @_retry_async()
    @mistral_breaker
    async def _call() -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                api_url,
                headers=headers,
                files={"file": ("document", file_bytes)},
            )
            response.raise_for_status()
            return response.json()

    return await _call()


async def call_generic_ocr_api(
    api_url: str,
    file_bytes: bytes,
    headers: Dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Call any generic OCR API with circuit-breaker protection."""
    req_headers = headers or {}

    @_retry_async()
    @generic_breaker
    async def _call() -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                api_url,
                headers=req_headers,
                files={"file": ("document", file_bytes)},
            )
            response.raise_for_status()
            return response.json()

    return await _call()


# ---------------------------------------------------------------------------
# Health-check endpoint helper
# ---------------------------------------------------------------------------

def get_breaker_status() -> Dict[str, Dict[str, Any]]:
    """Return the current state of all circuit breakers.

    Useful for ``/health/circuit-breakers`` monitoring endpoints.
    """
    return {
        "mistral_ocr": {
            "state": mistral_breaker.current_state,
            "failure_count": mistral_breaker.fail_counter,
        },
        "generic_ocr_api": {
            "state": generic_breaker.current_state,
            "failure_count": generic_breaker.fail_counter,
        },
    }
