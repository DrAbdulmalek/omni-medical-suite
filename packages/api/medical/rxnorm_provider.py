"""RxNorm provider — drug terminology normalization.

API docs: https://rxnav.nlm.nih.gov/
Base URL: https://rxnav.nlm.nih.gov/REST
Auth: None required
Privacy: Drug name queries only — no patient data sent.
"""
from __future__ import annotations

import json
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

# 24h TTL for drug terminology (relatively stable)
_RXNORM_CACHE_TTL = 86400


class RxNormProvider(BaseProvider):
    """Provider for NLM RxNorm drug terminology API.

    Primary use cases:
      - normalize_drug_name(name) — brand→generic, get RxCUI
      - get_drug_info(rxcui) — full drug concept info
      - find_related_drugs(rxcui) — related drug concepts

    No auth required. No patient data sent — drug name queries only.
    """

    BASE_URL = "https://rxnav.nlm.nih.gov/REST"
    PROVIDER_NAME = "rxnorm"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._cache: TTLCache = TTLCache(
            max_entries=500,
            default_ttl=_RXNORM_CACHE_TTL,
        )

    def _build_url(self, path: str, params: dict[str, str] | None = None) -> str:
        """Build URL with query params. Fixed base URL (SSRF-safe)."""
        url = f"{self.BASE_URL}{path}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
        return url

    def _fetch(self, operation: str, **kwargs: Any) -> ProviderResponse:
        import time

        url = kwargs.get("url", "")
        if not url:
            raise ProviderResponseError(
                f"{self.provider_name}: missing URL for operation {operation}",
                provider=self.provider_name,
            )

        # Check cache
        cached = self._cache.get(url)
        if cached is not None:
            return ProviderResponse(
                data=cached,
                source=self.provider_name,
                cached=True,
                latency_ms=0.0,
            )

        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > self._max_response_bytes:
                    raise ProviderResponseError(
                        f"{self.provider_name}: response too large ({content_length} bytes)",
                        provider=self.provider_name,
                    )
                body = resp.read(self._max_response_bytes)
                latency_ms = (time.monotonic() - start) * 1000

                try:
                    data = json.loads(body.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    raise ProviderResponseError(
                        f"{self.provider_name}: invalid JSON response",
                        provider=self.provider_name,
                    ) from e

                if not isinstance(data, dict):
                    raise ProviderResponseError(
                        f"{self.provider_name}: response is not a JSON object",
                        provider=self.provider_name,
                    )

                self._cache.set(url, data)

                return ProviderResponse(
                    data=data,
                    source=self.provider_name,
                    cached=False,
                    latency_ms=latency_ms,
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise ProviderRateLimitError(
                    f"{self.provider_name}: rate limited",
                    provider=self.provider_name,
                ) from e
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

    def normalize_drug_name(self, drug_name: str) -> ProviderResponse:
        """Resolve a drug name to its RxCUI and normalized concept.

        Args:
            drug_name: Brand or generic drug name — NOT patient data.

        Returns:
            ProviderResponse with 'rxcui', 'name', 'synonym' if found.
            Falls back to input name if no match.
        """
        url = self._build_url(
            "/rxcui.json",
            {"name": drug_name},
        )
        response = self.call("normalize_drug_name", url=url, query=drug_name)
        id_group = response.data.get("idGroup", {})
        rxnorm_ids = id_group.get("rxnormId", [])
        if rxnorm_ids:
            rxcui = rxnorm_ids[0]
            return ProviderResponse(
                data={
                    "rxcui": rxcui,
                    "name": drug_name,
                    "normalized": True,
                },
                source=self.provider_name,
                cached=response.cached,
                latency_ms=response.latency_ms,
            )
        # No match — return input as-is
        return ProviderResponse(
            data={"rxcui": None, "name": drug_name, "normalized": False},
            source=self.provider_name,
            cached=response.cached,
            latency_ms=response.latency_ms,
        )

    def get_drug_info(self, rxcui: str) -> ProviderResponse:
        """Get full drug concept information by RxCUI.

        Args:
            rxcui: RxNorm Concept Unique Identifier.

        Returns:
            ProviderResponse with related concepts and properties.
        """
        # Validate RxCUI is numeric (prevent path injection)
        if not rxcui.isalnum():
            raise ProviderResponseError(
                f"{self.provider_name}: invalid RxCUI format",
                provider=self.provider_name,
            )
        url = self._build_url(f"/rxcui/{rxcui}/allProperties.json", {"prop": "all"})
        return self.call("get_drug_info", url=url, query=rxcui)

    def find_related_drugs(self, rxcui: str) -> ProviderResponse:
        """Find related drug concepts (same ingredient, strength, form).

        Args:
            rxcui: RxNorm Concept Unique Identifier.

        Returns:
            ProviderResponse with related drug concepts.
        """
        if not rxcui.isalnum():
            raise ProviderResponseError(
                f"{self.provider_name}: invalid RxCUI format",
                provider=self.provider_name,
            )
        url = self._build_url(f"/rxcui/{rxcui}/allrelated.json", {})
        return self.call("find_related_drugs", url=url, query=rxcui)
