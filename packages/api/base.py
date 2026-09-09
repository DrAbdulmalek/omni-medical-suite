"""Base provider contract for external API integrations.

All external API providers inherit from BaseProvider and use the
ProviderResponse / ProviderError exception hierarchy.

Security invariants:
  - External responses are UNTRUSTED DATA — always validated via schema.
  - No secrets in logs, error messages, or exception strings.
  - Fixed base URLs — no user-supplied URL injection (SSRF prevention).
  - Bounded timeouts on every request (default 30s).
  - Bounded retries with exponential backoff (max 3, max 10s wait).
  - Response size limit (default 10MB) to prevent memory exhaustion.
  - No arbitrary code execution from API responses.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# --- Constants ---

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 1.0  # seconds; exponential: 1, 2, 4
DEFAULT_BACKOFF_MAX = 10.0  # seconds
DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10MB


# --- Exceptions ---

class ProviderError(Exception):
    """Base exception for all provider errors."""
    def __init__(self, message: str, *, provider: str = "", status: int = 0):
        super().__init__(message)
        self.provider = provider
        self.status = status


class ProviderTimeout(ProviderError):
    """Request timed out."""


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded (HTTP 429)."""
    def __init__(self, message: str, *, retry_after: float | None = None, provider: str = ""):
        super().__init__(message, provider=provider, status=429)
        self.retry_after = retry_after


class ProviderConfigurationError(ProviderError):
    """Provider is misconfigured (missing required config, invalid URL, etc.)."""


class ProviderResponseError(ProviderError):
    """API response failed schema validation or was unparseable."""


# --- Response container ---

@dataclass
class ProviderResponse:
    """Structured response from an external API provider."""
    data: dict[str, Any]
    source: str = ""
    cached: bool = False
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Base provider ---

class BaseProvider:
    """Abstract base for all external API providers.

    Subclasses must implement ``_fetch()`` and define ``BASE_URL``.

    Security:
      - ``BASE_URL`` is a class attribute (fixed, not user-supplied).
      - ``_fetch()`` must use HTTPS and validate responses.
      - No secrets are logged.
    """

    BASE_URL: str = ""
    PROVIDER_NAME: str = ""
    DEFAULT_TIMEOUT: int = DEFAULT_TIMEOUT_SECONDS

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        enabled: bool = True,
    ):
        if not self.BASE_URL:
            raise ProviderConfigurationError(
                f"{self.__class__.__name__}: BASE_URL must be set",
                provider=self.PROVIDER_NAME,
            )
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_response_bytes = max_response_bytes
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def provider_name(self) -> str:
        return self.PROVIDER_NAME or self.__class__.__name__

    def _sanitize_query_for_log(self, query: str) -> str:
        """Sanitize query for logging — truncate and strip control chars."""
        if not query:
            return ""
        # Truncate to 100 chars; no patient data expected (terminology only)
        return query[:100].replace("\n", " ").replace("\r", " ")

    def _log_operation(
        self,
        operation: str,
        latency_ms: float,
        status: str = "ok",
        error: str = "",
        query: str = "",
    ) -> None:
        """Log API operation without leaking secrets or patient data."""
        logger.info(
            "provider=%s op=%s status=%s latency_ms=%.0f query=%s error=%s",
            self.provider_name,
            operation,
            status,
            latency_ms,
            self._sanitize_query_for_log(query),
            error[:80] if error else "",
        )

    def _fetch(self, operation: str, **kwargs: Any) -> ProviderResponse:
        """Perform an HTTP request to the provider API.

        Subclasses must implement this method. The method must:
          - Use HTTPS (enforced by BASE_URL starting with https://)
          - Enforce timeout
          - Enforce response size limit
          - Validate response schema
          - Not log secrets
          - Return ProviderResponse

        Raises:
            ProviderTimeout: if request times out.
            ProviderRateLimitError: if HTTP 429.
            ProviderResponseError: if response fails validation.
            ProviderError: for other HTTP errors.
        """
        raise NotImplementedError

    def call(self, operation: str, **kwargs: Any) -> ProviderResponse:
        """Public entry point with retry logic.

        Falls back to ProviderError after exhausting retries.
        Does NOT silently swallow errors — caller must handle or fallback.
        """
        if not self._enabled:
            raise ProviderConfigurationError(
                f"{self.provider_name}: provider is disabled",
                provider=self.provider_name,
            )

        last_error: ProviderError | None = None
        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            try:
                response = self._fetch(operation, **kwargs)
                latency_ms = (time.monotonic() - start) * 1000
                self._log_operation(
                    operation=operation,
                    latency_ms=latency_ms,
                    status="ok",
                    query=str(kwargs.get("query", "")),
                )
                return response
            except ProviderRateLimitError as e:
                latency_ms = (time.monotonic() - start) * 1000
                self._log_operation(
                    operation=operation,
                    latency_ms=latency_ms,
                    status="rate_limited",
                    error=str(e),
                    query=str(kwargs.get("query", "")),
                )
                last_error = e
                if attempt < self._max_retries:
                    wait = e.retry_after if e.retry_after else min(
                        DEFAULT_BACKOFF_BASE * (2 ** attempt),
                        DEFAULT_BACKOFF_MAX,
                    )
                    time.sleep(wait)
            except ProviderTimeout as e:
                latency_ms = (time.monotonic() - start) * 1000
                self._log_operation(
                    operation=operation,
                    latency_ms=latency_ms,
                    status="timeout",
                    error=str(e),
                    query=str(kwargs.get("query", "")),
                )
                last_error = e
                if attempt < self._max_retries:
                    wait = min(
                        DEFAULT_BACKOFF_BASE * (2 ** attempt),
                        DEFAULT_BACKOFF_MAX,
                    )
                    time.sleep(wait)
            except ProviderError as e:
                latency_ms = (time.monotonic() - start) * 1000
                self._log_operation(
                    operation=operation,
                    latency_ms=latency_ms,
                    status="error",
                    error=str(e),
                    query=str(kwargs.get("query", "")),
                )
                last_error = e
                # Non-retryable errors (4xx except 429) — don't retry
                if e.status and 400 <= e.status < 500 and e.status != 429:
                    break
                if attempt < self._max_retries:
                    wait = min(
                        DEFAULT_BACKOFF_BASE * (2 ** attempt),
                        DEFAULT_BACKOFF_MAX,
                    )
                    time.sleep(wait)

        raise last_error or ProviderError(
            f"{self.provider_name}: exhausted retries",
            provider=self.provider_name,
        )
