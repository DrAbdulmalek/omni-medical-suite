"""Tests for API endpoints."""
import pytest


class TestHealthEndpoints:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_readiness_check(self, client):
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data


class TestDocumentEndpoints:
    def test_list_documents_empty(self, client):
        response = client.get("/api/v1/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_document_not_found(self, client):
        response = client.get("/api/v1/documents/99999")
        assert response.status_code == 404

    def test_get_ocr_result_not_found(self, client):
        response = client.get("/api/v1/ocr/result/99999")
        assert response.status_code == 404
