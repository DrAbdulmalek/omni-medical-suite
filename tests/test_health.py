"""Tests for health check endpoints."""
import pytest


class TestHealthCheck:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_contains_version(self, client):
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert "uptime_seconds" in data

    def test_health_has_api_component(self, client):
        response = client.get("/health")
        data = response.json()
        assert "components" in data
        assert "api" in data["components"]

    def test_readiness_contains_components(self, client):
        response = client.get("/health/ready")
        data = response.json()
        assert "components" in data
        assert isinstance(data["components"], dict)
