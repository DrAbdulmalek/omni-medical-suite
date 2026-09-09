"""PubMed provider — biomedical literature search via NCBI E-utilities.

API docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
Base URL: https://eutils.ncbi.nlm.nih.gov/entrez/eutils
Auth: apiKey (optional — 3 req/sec without, 10/sec with)
Privacy: Search terms are medical terminology, NOT patient data.
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

# 7-day TTL for literature metadata (immutable)
_PUBMED_CACHE_TTL = 7 * 86400


class PubMedProvider(BaseProvider):
    """Provider for NCBI PubMed E-utilities API.

    Primary use cases:
      - search(term) — search PubMed for articles
      - get_summary(pmid) — get article metadata by PMID
      - get_abstract(pmid) — get article abstract

    No patient data sent — only medical terminology search terms.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    PROVIDER_NAME = "pubmed"

    def __init__(self, **kwargs: Any):
        api_key = kwargs.pop("api_key", None) or os.environ.get("NCBI_API_KEY", "")
        super().__init__(api_key=api_key, **kwargs)
        self._cache: TTLCache = TTLCache(
            max_entries=500,
            default_ttl=_PUBMED_CACHE_TTL,
        )

    def _build_url(self, endpoint: str, params: dict[str, str]) -> str:
        """Build URL with query params. Fixed base URL (SSRF-safe)."""
        if self._api_key:
            params = {**params, "api_key": self._api_key}
        query_string = urllib.parse.urlencode(params)
        return f"{self.BASE_URL}/{endpoint}?{query_string}"

    def _fetch(self, operation: str, **kwargs: Any) -> ProviderResponse:
        import time

        url = kwargs.get("url", "")
        if not url:
            raise ProviderResponseError(
                f"{self.provider_name}: missing URL for operation {operation}",
                provider=self.provider_name,
            )

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

    def search(self, term: str, limit: int = 5) -> ProviderResponse:
        """Search PubMed for articles matching a medical term.

        Args:
            term: Medical terminology search query — NOT patient data.
            limit: Max results (default 5).

        Returns:
            ProviderResponse with 'esearchresult' containing PMIDs.
        """
        url = self._build_url(
            "esearch.fcgi",
            {"db": "pubmed", "term": term, "retmode": "json", "retmax": str(limit)},
        )
        return self.call("search", url=url, query=term)

    def get_summary(self, pmid: str) -> ProviderResponse:
        """Get article summary metadata by PMID.

        Args:
            pmid: PubMed ID (numeric string).

        Returns:
            ProviderResponse with article title, authors, journal, date.
        """
        # Validate PMID is numeric (prevent injection)
        if not pmid.isdigit():
            raise ProviderResponseError(
                f"{self.provider_name}: invalid PMID format",
                provider=self.provider_name,
            )
        url = self._build_url(
            "esummary.fcgi",
            {"db": "pubmed", "id": pmid, "retmode": "json"},
        )
        return self.call("get_summary", url=url, query=pmid)

    def get_abstract(self, pmid: str) -> ProviderResponse:
        """Get article abstract by PMID.

        Args:
            pmid: PubMed ID (numeric string).

        Returns:
            ProviderResponse with abstract text (NOT full article — respect copyright).
        """
        if not pmid.isdigit():
            raise ProviderResponseError(
                f"{self.provider_name}: invalid PMID format",
                provider=self.provider_name,
            )
        url = self._build_url(
            "efetch.fcgi",
            {"db": "pubmed", "id": pmid, "retmode": "json"},
        )
        return self.call("get_abstract", url=url, query=pmid)
