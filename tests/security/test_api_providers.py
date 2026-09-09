"""Tests for P0 public API providers.

Tests are designed to run WITHOUT external internet access — all HTTP
responses are mocked. Optional live tests are marked separately.

Coverage:
  - Normal responses (with valid data)
  - Empty results
  - Invalid JSON / unparseable responses
  - Timeouts
  - HTTP errors (4xx, 5xx)
  - Rate limits (429)
  - Cache behavior (hit/miss/TTL)
  - Security: no secrets in logs, response size limit, schema validation
"""
from __future__ import annotations

import json
import time
import urllib.error
from unittest import mock
from io import BytesIO

import pytest

from packages.api.base import (
    BaseProvider,
    ProviderError,
    ProviderResponse,
    ProviderResponseError,
    ProviderTimeout,
    ProviderRateLimitError,
    ProviderConfigurationError,
)
from packages.api.cache import TTLCache
from packages.api.medical.openfda_provider import OpenFDAProvider
from packages.api.medical.rxnorm_provider import RxNormProvider
from packages.api.literature.pubmed_provider import PubMedProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockHTTPResponse:
    """Mock urllib HTTP response."""
    def __init__(self, status: int, body: bytes, headers: dict | None = None):
        self.status = status
        self.code = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size: int = -1):
        if size > 0:
            return self._body[:size]
        return self._body


def make_mock_urlopen(status: int, body: dict | bytes, headers: dict | None = None):
    """Create a mock urlopen that returns the given response."""
    if isinstance(body, dict):
        body_bytes = json.dumps(body).encode("utf-8")
    else:
        body_bytes = body
    response = MockHTTPResponse(status, body_bytes, headers)

    def mock_urlopen(req, timeout=None):
        if status >= 400:
            raise urllib.error.HTTPError(
                req.full_url if hasattr(req, "full_url") else str(req),
                status,
                "Error",
                {"Content-Length": str(len(body_bytes))},
                BytesIO(body_bytes),
            )
        return response

    return mock_urlopen


def make_timeout_urlopen():
    """Create a mock urlopen that raises TimeoutError."""
    def mock_urlopen(req, timeout=None):
        raise TimeoutError("timed out")
    return mock_urlopen


# ---------------------------------------------------------------------------
# OpenFDAProvider Tests
# ---------------------------------------------------------------------------

class TestOpenFDAProvider:

    def test_normal_response(self, tmp_path):
        """Normal drug label search returns structured data."""
        provider = OpenFDAProvider()
        mock_response = {
            "meta": {"results": {"total": 1}},
            "results": [{
                "openfda": {
                    "generic_name": ["acetaminophen"],
                    "brand_name": ["TYLENOL"],
                },
                "purpose": ["Pain reliever"],
            }],
        }
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.search_drug("tylenol")
        assert response.source == "openfda"
        assert response.data["meta"]["results"]["total"] == 1
        assert response.data["results"][0]["openfda"]["generic_name"] == ["acetaminophen"]

    def test_empty_result(self, tmp_path):
        """Empty search result returns empty results list."""
        provider = OpenFDAProvider()
        mock_response = {"meta": {"results": {"total": 0}}, "results": []}
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.search_drug("nonexistentdrug")
        assert response.data["results"] == []

    def test_invalid_response(self):
        """Invalid JSON raises ProviderResponseError."""
        provider = OpenFDAProvider()
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, b"not json")):
            with pytest.raises(ProviderResponseError):
                provider.search_drug("test")

    def test_timeout(self):
        """Timeout raises ProviderTimeout (after retries exhausted)."""
        provider = OpenFDAProvider(max_retries=0)
        with mock.patch("urllib.request.urlopen", make_timeout_urlopen()):
            with pytest.raises(ProviderTimeout):
                provider.search_drug("test")

    def test_http_error(self):
        """HTTP 500 raises ProviderError."""
        provider = OpenFDAProvider(max_retries=0)
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(500, {"error": "server"})):
            with pytest.raises(ProviderError):
                provider.search_drug("test")

    def test_rate_limit(self):
        """HTTP 429 raises ProviderRateLimitError."""
        provider = OpenFDAProvider(max_retries=0)
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(429, {"error": "rate"})):
            with pytest.raises(ProviderRateLimitError):
                provider.search_drug("test")

    def test_normalize_drug_name_found(self):
        """normalize_drug_name returns generic name when found."""
        provider = OpenFDAProvider()
        mock_response = {
            "results": [{
                "openfda": {
                    "generic_name": ["acetaminophen"],
                    "brand_name": ["TYLENOL"],
                },
            }],
        }
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.normalize_drug_name("Tylenol")
        assert response.data["normalized_name"] == "acetaminophen"
        assert response.data["brand_names"] == ["TYLENOL"]

    def test_normalize_drug_name_not_found(self):
        """normalize_drug_name returns input when not found."""
        provider = OpenFDAProvider()
        mock_response = {"meta": {"results": {"total": 0}}, "results": []}
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.normalize_drug_name("nonexistent")
        assert response.data["normalized_name"] == "nonexistent"

    def test_cache_hit(self):
        """Second call to same endpoint returns cached result."""
        provider = OpenFDAProvider()
        mock_response = {
            "meta": {"results": {"total": 1}},
            "results": [{"openfda": {"generic_name": ["aspirin"]}}],
        }
        urlopen_mock = make_mock_urlopen(200, mock_response)
        with mock.patch("urllib.request.urlopen", urlopen_mock) as m:
            # First call — should hit API
            r1 = provider.search_drug("aspirin")
            assert r1.cached is False
            # Second call — should hit cache
            r2 = provider.search_drug("aspirin")
            assert r2.cached is True

    def test_404_returns_empty(self):
        """HTTP 404 returns empty result, not an error."""
        provider = OpenFDAProvider(max_retries=0)
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(404, {"error": "not found"})):
            response = provider.search_drug("nonexistent")
        assert response.data["results"] == []


# ---------------------------------------------------------------------------
# RxNormProvider Tests
# ---------------------------------------------------------------------------

class TestRxNormProvider:

    def test_normal_response(self):
        """Normal RxCUI lookup returns drug concept."""
        provider = RxNormProvider()
        mock_response = {
            "idGroup": {
                "rxnormId": ["83367"],
            },
        }
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.normalize_drug_name("atorvastatin")
        assert response.data["rxcui"] == "83367"
        assert response.data["normalized"] is True

    def test_empty_result(self):
        """No match returns rxcui=None."""
        provider = RxNormProvider()
        mock_response = {"idGroup": {}}
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.normalize_drug_name("nonexistent")
        assert response.data["rxcui"] is None
        assert response.data["normalized"] is False

    def test_timeout(self):
        """Timeout raises ProviderTimeout."""
        provider = RxNormProvider(max_retries=0)
        with mock.patch("urllib.request.urlopen", make_timeout_urlopen()):
            with pytest.raises(ProviderTimeout):
                provider.normalize_drug_name("test")

    def test_invalid_response(self):
        """Invalid JSON raises ProviderResponseError."""
        provider = RxNormProvider()
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, b"not json")):
            with pytest.raises(ProviderResponseError):
                provider.normalize_drug_name("test")

    def test_get_drug_info_validates_rxcui(self):
        """get_drug_info rejects non-alphanumeric RxCUI."""
        provider = RxNormProvider()
        with pytest.raises(ProviderResponseError):
            provider.get_drug_info("../../../etc/passwd")

    def test_cache_hit(self):
        """Second call returns cached result."""
        provider = RxNormProvider()
        mock_response = {"idGroup": {"rxnormId": ["83367"]}}
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            r1 = provider.normalize_drug_name("atorvastatin")
            assert r1.cached is False
            r2 = provider.normalize_drug_name("atorvastatin")
            assert r2.cached is True


# ---------------------------------------------------------------------------
# PubMedProvider Tests
# ---------------------------------------------------------------------------

class TestPubMedProvider:

    def test_normal_response(self):
        """Normal search returns PMIDs."""
        provider = PubMedProvider()
        mock_response = {
            "esearchresult": {
                "count": "725254",
                "idlist": ["42711210"],
            },
        }
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.search("hypertension")
        assert response.data["esearchresult"]["count"] == "725254"
        assert "42711210" in response.data["esearchresult"]["idlist"]

    def test_empty_result(self):
        """Empty search returns empty idlist."""
        provider = PubMedProvider()
        mock_response = {"esearchresult": {"count": "0", "idlist": []}}
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            response = provider.search("nonexistentterm12345")
        assert response.data["esearchresult"]["idlist"] == []

    def test_timeout(self):
        """Timeout raises ProviderTimeout."""
        provider = PubMedProvider(max_retries=0)
        with mock.patch("urllib.request.urlopen", make_timeout_urlopen()):
            with pytest.raises(ProviderTimeout):
                provider.search("test")

    def test_invalid_response(self):
        """Invalid JSON raises ProviderResponseError."""
        provider = PubMedProvider()
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, b"not json")):
            with pytest.raises(ProviderResponseError):
                provider.search("test")

    def test_get_summary_validates_pmid(self):
        """get_summary rejects non-numeric PMID."""
        provider = PubMedProvider()
        with pytest.raises(ProviderResponseError):
            provider.get_summary("abc123")

    def test_get_abstract_validates_pmid(self):
        """get_abstract rejects non-numeric PMID."""
        provider = PubMedProvider()
        with pytest.raises(ProviderResponseError):
            provider.get_abstract("'; DROP TABLE")


# ---------------------------------------------------------------------------
# Security Tests
# ---------------------------------------------------------------------------

class TestProviderSecurity:

    def test_no_secret_in_logs(self, caplog):
        """API keys must not appear in log messages."""
        import logging
        provider = OpenFDAProvider(api_key="SECRET_KEY_12345")
        mock_response = {"meta": {"results": {"total": 0}}, "results": []}
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, mock_response)):
            with caplog.at_level(logging.INFO):
                provider.search_drug("test")
        # Check no log message contains the secret
        for record in caplog.records:
            assert "SECRET_KEY_12345" not in record.getMessage()

    def test_response_schema_validation(self):
        """Provider validates response is a dict."""
        provider = RxNormProvider()
        # Response that's a JSON list, not dict
        with mock.patch("urllib.request.urlopen", make_mock_urlopen(200, b"[1, 2, 3]")):
            with pytest.raises(ProviderResponseError):
                provider.normalize_drug_name("test")

    def test_timeout_enforced(self):
        """Provider uses configured timeout value."""
        provider = OpenFDAProvider(timeout=5)
        assert provider._timeout == 5

    def test_fixed_base_url(self):
        """Base URL is fixed — not user-supplied."""
        assert OpenFDAProvider.BASE_URL == "https://api.fda.gov"
        assert RxNormProvider.BASE_URL == "https://rxnav.nlm.nih.gov/REST"
        assert PubMedProvider.BASE_URL == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def test_disabled_provider_raises(self):
        """Disabled provider raises ProviderConfigurationError."""
        provider = OpenFDAProvider(enabled=False)
        with pytest.raises(ProviderConfigurationError):
            provider.search_drug("test")


# ---------------------------------------------------------------------------
# Cache Tests
# ---------------------------------------------------------------------------

class TestTTLCache:

    def test_set_and_get(self):
        cache = TTLCache(default_ttl=60)
        cache.set("key", {"value": 1})
        assert cache.get("key") == {"value": 1}

    def test_miss_returns_none(self):
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        cache = TTLCache(default_ttl=0.1)  # 100ms
        cache.set("key", "value")
        time.sleep(0.15)
        assert cache.get("key") is None

    def test_clear(self):
        cache = TTLCache()
        cache.set("key", "value")
        cache.clear()
        assert cache.get("key") is None

    def test_contains(self):
        cache = TTLCache()
        cache.set("key", "value")
        assert "key" in cache
        assert "other" not in cache

    def test_max_entries_eviction(self):
        cache = TTLCache(max_entries=2, default_ttl=60)
        cache.set("k1", 1)
        cache.set("k2", 2)
        cache.set("k3", 3)  # should evict k1
        assert cache.get("k1") is None
        assert cache.get("k2") == 2
        assert cache.get("k3") == 3
