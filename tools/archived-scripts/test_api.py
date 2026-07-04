"""OmniMedical Suite v2.0 — API Integration Tests"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health and monitoring endpoints."""

    def test_health_check(self, client):
        """Test comprehensive health check."""
        response = client.get("/api/health")
        assert response.status_code in [200, 503]  # 503 if dependencies down

        data = response.json()
        assert "api" in data
        assert "overall" in data

    def test_readiness_probe(self, client):
        """Test Kubernetes readiness probe."""
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_liveness_probe(self, client):
        """Test Kubernetes liveness probe."""
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics exposure."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "omnimedical" in response.text


class TestDocumentEndpoints:
    """Test document processing endpoints."""

    def test_upload_no_file(self, client, auth_headers):
        """Test upload without file returns error."""
        response = client.post("/api/documents/upload", headers=auth_headers)
        assert response.status_code == 422  # Validation error

    def test_upload_invalid_type(self, client, auth_headers, create_test_image):
        """Test upload with invalid file type."""
        # Create a text file pretending to be an image
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = client.post(
            "/api/documents/upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 415  # Unsupported media type

    def test_get_stats(self, client, auth_headers):
        """Test processing stats endpoint."""
        response = client.get("/api/documents/stats", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "total_documents" in data
        assert "avg_confidence" in data

    def test_get_document_not_found(self, client, auth_headers):
        """Test getting non-existent document."""
        response = client.get("/api/documents/nonexistent-id", headers=auth_headers)
        assert response.status_code == 501  # Not yet implemented


class TestCorrectionEndpoints:
    """Test correction management endpoints."""

    def test_create_correction(self, client, auth_headers):
        """Test creating a manual correction."""
        payload = {
            "original": "فخد",
            "corrected": "عظم الفخذ",
            "language": "ar",
            "context_before": "كسر في",
            "context_after": "الأيمن",
            "confidence_before": 0.65,
            "confidence_after": 0.92
        }
        response = client.post("/api/corrections/", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["original"] == "فخد"
        assert data["corrected"] == "عظم الفخذ"
        assert data["status"] == "pending"

    def test_create_correction_invalid(self, client, auth_headers):
        """Test creating correction with invalid data."""
        payload = {
            "original": "",  # Empty — should fail
            "corrected": "test"
        }
        response = client.post("/api/corrections/", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_get_stats(self, client, auth_headers):
        """Test correction stats endpoint."""
        response = client.get("/api/corrections/stats", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "promoted" in data
        assert "avg_gain" in data

    def test_run_promotion(self, client, auth_headers):
        """Test manual promotion trigger."""
        response = client.post("/api/corrections/run-promotion", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "promoted_count" in data


class TestSearchEndpoints:
    """Test vector search endpoints."""

    def test_semantic_search_empty(self, client, auth_headers):
        """Test search with empty query."""
        payload = {"query": "", "limit": 5}
        response = client.post("/api/search/semantic", json=payload, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_semantic_search_basic(self, client, auth_headers):
        """Test basic semantic search."""
        payload = {"query": "كسر في عظم الفخذ", "limit": 5}
        response = client.post("/api/search/semantic", json=payload, headers=auth_headers)
        assert response.status_code == 200

        results = response.json()
        assert isinstance(results, list)
