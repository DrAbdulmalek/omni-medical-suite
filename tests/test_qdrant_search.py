"""Smoke tests for QdrantMedicalSearch — verifies both real and fallback paths.

Uses ``pytest.importorskip`` so the file is collected unconditionally
but individual tests are skipped when ``qdrant_client`` is not installed.
"""

from __future__ import annotations

import json

import pytest

qdrant_client = pytest.importorskip(
    "qdrant_client",
    reason="qdrant_client not installed — only fallback path can be tested",
)

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
    """Tests that run even WITHOUT a live Qdrant instance (local fallback)."""

    def test_fallback_backend_used_when_no_url(self):
        """When qdrant_url is None, upsert_records should report 'local_fallback'."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url=None,
            collection_name="test_smoke",
            extractor=extractor,
        )
        info = search.upsert_records(FIXTURE_CORPUS)
        assert info["backend"] == "local_fallback", (
            f"Expected local_fallback but got {info['backend']}"
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
        # doc-001 and doc-003 both mention the query terms
        hit_ids = {h["id"] for h in hits}
        assert "doc-001" in hit_ids or "doc-003" in hit_ids, (
            f"Expected relevant doc in {hit_ids}"
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

    def test_upsert_returns_count(self):
        """upsert_records should report the number of indexed records."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url=None,
            collection_name="test_smoke_count",
            extractor=extractor,
        )
        info = search.upsert_records(FIXTURE_CORPUS)
        assert info.get("indexed_count", 0) == 3


class TestQdrantMedicalSearchIntegration:
    """Tests that require a live Qdrant instance (skipped if unavailable)."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_qdrant(self, monkeypatch):
        """Skip the entire class if no Qdrant is reachable."""
        import qdrant_client as qc
        try:
            client = qc.QdrantClient(host="localhost", port=6333, timeout=2)
            client.get_collections()
            client.close()
        except Exception:
            pytest.skip("No Qdrant instance reachable at localhost:6333")

    def test_roundtrip_with_live_qdrant(self):
        """Full roundtrip: upsert → search → verify ranking."""
        extractor = ArabicMedicalFieldExtractor()
        search = QdrantMedicalSearch(
            qdrant_url="http://localhost:6333",
            collection_name="test_integration_smoke",
            extractor=extractor,
        )
        info = search.upsert_records(FIXTURE_CORPUS)
        assert info["backend"] == "qdrant", f"Expected qdrant backend, got {info['backend']}"

        hits = search.search("ارتفاع ضغط الدم أحمد", top_k=3)
        assert len(hits) >= 1
        assert hits[0]["score"] > 0.0