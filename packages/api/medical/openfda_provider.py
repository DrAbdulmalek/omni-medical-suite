"""openFDA provider — drug metadata, labels, adverse events.

API docs: https://open.fda.gov/
Base URL: https://api.fda.gov
Auth: apiKey (optional — 240 req/min without, 120K/day with)
Privacy: Drug name queries only — no patient data sent.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from packages.api.base import (
    BaseProvider,
    ProviderError,
    ProviderResponse,
    ProviderResponseError,
    ProviderTimeout,
    ProviderRateLimitError,
)
from packages.api.cache import TTLCache

# 7-day TTL for drug metadata (rarely changes)
_OPENFDA_CACHE_TTL = 7 * 86400


class OpenFDAProvider(BaseProvider):
    """Provider for openFDA drug metadata API.

    Primary use cases:
      - search_drug(query) — find drug by brand/generic name
      - get_drug_label(drug_name) — get FDA drug label
      - normalize_drug_name(drug_name) — resolve brand→generic

    All responses are cached for 7 days (drug metadata is stable).
    No patient data is sent — only drug name queries.
    """

    BASE_URL = "https://api.fda.gov"
    PROVIDER_NAME = "openfda"

    def __init__(self, **kwargs: Any):
        api_key = kwargs.pop("api_key", None) or os.environ.get("OPENFDA_API_KEY", "")
        super().__init__(api_key=api_key, **kwargs)
        self._cache: TTLCache = TTLCache(
            max_entries=500,
            default_ttl=_OPENFDA_CACHE_TTL,
        )

    def _build_url(self, endpoint: str, params: dict[str, str]) -> str:
        """Build URL with query params. No user-supplied URLs (SSRF-safe)."""
        if self._api_key:
            params = {**params, "api_key": self._api_key}
        query_string = urllib.parse.urlencode(params)
        return f"{self.BASE_URL}{endpoint}?{query_string}"

    def _fetch(self, operation: str, **kwargs: Any) -> ProviderResponse:
        import time

        url = kwargs.get("url", "")
        if not url:
            raise ProviderResponseError(
                f"{self.provider_name}: missing URL for operation {operation}",
                provider=self.provider_name,
            )

        # Check cache
        cache_key = url
        cached = self._cache.get(cache_key)
        if cached is not None:
            return ProviderResponse(
                data=cached,
                source=self.provider_name,
                cached=True,
                latency_ms=0.0,
            )

        # Make HTTP request (stdlib only — no external deps)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                # Enforce response size limit
                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > self._max_response_bytes:
                    raise ProviderResponseError(
                        f"{self.provider_name}: response too large ({content_length} bytes)",
                        provider=self.provider_name,
                    )
                body = resp.read(self._max_response_bytes)
                if len(body) >= self._max_response_bytes:
                    raise ProviderResponseError(
                        f"{self.provider_name}: response exceeded size limit",
                        provider=self.provider_name,
                    )
                latency_ms = (time.monotonic() - start) * 1000

                # Parse JSON
                try:
                    data = json.loads(body.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    raise ProviderResponseError(
                        f"{self.provider_name}: invalid JSON response",
                        provider=self.provider_name,
                    ) from e

                # Validate expected structure
                if not isinstance(data, dict):
                    raise ProviderResponseError(
                        f"{self.provider_name}: response is not a JSON object",
                        provider=self.provider_name,
                    )

                # Cache successful response
                self._cache.set(cache_key, data)

                return ProviderResponse(
                    data=data,
                    source=self.provider_name,
                    cached=False,
                    latency_ms=latency_ms,
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after_raw = e.headers.get("Retry-After", "")
                try:
                    retry_after = float(retry_after_raw) if retry_after_raw else None
                except ValueError:
                    retry_after = None
                raise ProviderRateLimitError(
                    f"{self.provider_name}: rate limited",
                    retry_after=retry_after,
                    provider=self.provider_name,
                ) from e
            elif e.code == 404:
                # Not found — return empty result, not an error
                return ProviderResponse(
                    data={"results": [], "meta": {"results": {"total": 0}}},
                    source=self.provider_name,
                    cached=False,
                    latency_ms=(time.monotonic() - start) * 1000,
                )
            else:
                raise ProviderError(
                    f"{self.provider_name}: HTTP {e.code}",
                    provider=self.provider_name,
                    status=e.code,
                ) from e
        except TimeoutError as e:
            raise ProviderTimeout(
                f"{self.provider_name}: request timed out",
                provider=self.provider_name,
            ) from e

    # --- Public API ---

    def search_drug(self, query: str, limit: int = 5) -> ProviderResponse:
        """Search for drugs by brand or generic name.

        Args:
            query: Drug name (brand or generic) — NOT patient data.
            limit: Max results (default 5).

        Returns:
            ProviderResponse with 'results' list of drug label records.
        """
        search_term = urllib.parse.quote(f'openfda.brand_name:"{query}"+openfda.generic_name:"{query}"')
        url = self._build_url(
            "/drug/label.json",
            {"search": search_term, "limit": str(limit)},
        )
        return self.call("search_drug", url=url, query=query)

    def get_drug_label(self, drug_name: str) -> ProviderResponse:
        """Get FDA drug label for a specific drug.

        Args:
            drug_name: Generic or brand name — NOT patient data.

        Returns:
            ProviderResponse with drug label information.
        """
        search_term = urllib.parse.quote(f'openfda.generic_name:"{drug_name}"+openfda.brand_name:"{drug_name}"')
        url = self._build_url(
            "/drug/label.json",
            {"search": search_term, "limit": "1"},
        )
        return self.call("get_drug_label", url=url, query=drug_name)

    def normalize_drug_name(self, drug_name: str) -> ProviderResponse:
        """Resolve a drug name to its normalized generic name.

        Uses openfda.generic_name from the first matching result.
        Falls back to the input name if no match found.

        Args:
            drug_name: Brand or generic drug name.

        Returns:
            ProviderResponse with 'normalized_name' and 'openfda' metadata.
        """
        response = self.get_drug_label(drug_name)
        results = response.data.get("results", [])
        if results:
            openfda = results[0].get("openfda", {})
            generic_names = openfda.get("generic_name", [])
            brand_names = openfda.get("brand_name", [])
            normalized = generic_names[0] if generic_names else drug_name
            return ProviderResponse(
                data={
                    "normalized_name": normalized,
                    "generic_names": generic_names,
                    "brand_names": brand_names,
                    "openfda": openfda,
                },
                source=self.provider_name,
                cached=response.cached,
                latency_ms=response.latency_ms,
            )
        # No match — return input as-is (fallback)
        return ProviderResponse(
            data={"normalized_name": drug_name, "generic_names": [], "brand_names": []},
            source=self.provider_name,
            cached=response.cached,
            latency_ms=response.latency_ms,
        )
