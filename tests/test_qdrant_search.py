"""Smoke tests for QdrantMedicalSearch — verifies both real and fallback paths.

Fallback tests (TestQdrantMedicalSearchFallback) run unconditionally without
any Qdrant dependency.  Integration tests (TestQdrantMedicalSearchIntegration)
require both ``qdrant_client`` installed AND a live Qdrant instance; they are
skipped individually via a class-level fixture when either is unavailable.
"""

from __future__ import annotations

import pytest

from src.ocr.deduplication import QdrantMedicalSearch
from src.ocr.field_extractor import ArabicMedicalFieldExtractor


FIXTURE_CORPUS = [
    {
        "id": "doc-001",
        "raw_text": "اسم المريض: أحمد محمد حسين\nالتاريخ: 2026-01-15\nالتشخيص: ارتفاع ضغط الدم",
        "metadata": {
            "patient_name": "أحمد محمد حسين",
            "date": "2026-01-15",
            "diagnosis": "ارتفاع ضغط الدم",
        },
    },
    {
        "id": "doc-002",
        "raw_text": "اسم المريض: فاطمة علي سالم\nالتاريخ: 2026-01-16\nالتشخيص: التهاب المعدة الحاد",
        "metadata": {
            "patient_name": "فاطمة علي سالم",
            "date": "2026-01-16",
            "diagnosis": "التهاب المعدة الحاد",
        },
    },
    {
        "id": "doc-003",
        "raw_text": "اسم المريض: أحمد محمد حسين\nالتاريخ: 2026-01-15\nالتشخيص: ارتفاع ضغط الدم\nالأدوية: أموديبين 5 ملغ",
        "metadata": {
            "patient_name": "أحمد محمد حسين",
            "date": "2026-01-15",
            "diagnosis": "ارتفاع ضغط الدم",
            "medications": "أموديبين 5 ملغ",
        },
    },
]


class TestQdrantMedicalSearchFallback:
    """Tests that run WITHOUT a live Qdrant instance (local fuzzy fallback).

    These tests verify the local fuzzy-search fallback path.  They do NOT
    require ``qdrant_client`` to be installed — only ``rapidfuzz`` (already
    a core dependency of deduplication.py).
    """

    def test_fallback_backend_used_when_no_url(self):
        """When qdrant_url is None, upsert_records should report 'local' backend."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url=None,
            collection_name="test_smoke",
            extractor=extractor,
        )
        info = search.upsert_records(FIXTURE_CORPUS)
        assert info["backend"] == "local", (
            f"Expected 'local' but got {info['backend']!r}"
        )

    def test_fallback_search_returns_results(self):
        """Local fallback search should still return ranked results."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url=None,
            collection_name="test_smoke_search",
            extractor=extractor,
        )
        search.upsert_records(FIXTURE_CORPUS)
        hits = search.search("ارتفاع ضغط الدم أحمد", top_k=3)
        assert len(hits) >= 1, "Fallback search should return at least one result"
        # doc-001 (index 0) and doc-003 (index 2) both mention the query terms
        hit_ids = {h["id"] for h in hits}
        assert "0" in hit_ids or "2" in hit_ids, (
            f"Expected relevant doc index in {hit_ids}"
        )

    def test_fallback_search_empty_query(self):
        """Empty query should return empty results, not crash."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url=None,
            collection_name="test_smoke_empty",
            extractor=extractor,
        )
        search.upsert_records(FIXTURE_CORPUS)
        hits = search.search("", top_k=3)
        assert isinstance(hits, list)
        assert len(hits) == 0

    def test_upsert_returns_count(self):
        """upsert_records should report the number of indexed records."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url=None,
            collection_name="test_smoke_count",
            extractor=extractor,
        )
        info = search.upsert_records(FIXTURE_CORPUS)
        assert info.get("indexed", 0) == 3


class TestQdrantMedicalSearchIntegration:
    """Tests that require qdrant_client installed AND a live Qdrant instance.

    Each test is individually skipped when the dependency or server is
    unavailable — the fallback test class above is never affected.
    """

    @pytest.fixture(autouse=True)
    def _require_qdrant(self):
        """Skip individual tests when qdrant_client is missing or server is unreachable."""
        try:
            import qdrant_client as qc
        except ImportError:
            pytest.skip("qdrant_client not installed")
        try:
            client = qc.QdrantClient(host="localhost", port=6333, timeout=2)
            client.get_collections()
            client.close()
        except Exception:
            pytest.skip("No Qdrant instance reachable at localhost:6333")

    def test_roundtrip_with_live_qdrant(self):
        """Full roundtrip: upsert -> search -> verify ranking."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url="http://localhost:6333",
            collection_name="test_integration_smoke",
            extractor=extractor,
        )
        info = search.upsert_records(FIXTURE_CORPUS)
        assert info["backend"] == "qdrant", f"Expected qdrant backend, got {info['backend']!r}"

        hits = search.search("ارتفاع ضغط الدم أحمد", top_k=3)
        assert len(hits) >= 1
        assert hits[0]["score"] > 0.0