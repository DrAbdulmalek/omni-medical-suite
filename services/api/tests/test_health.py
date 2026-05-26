"""Tests for health check endpoints."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import httpx


class TestHealthLiveEndpoint:
    """Test /health/live endpoint."""

    @pytest.mark.asyncio
    async def test_live_returns_200(self):
        """Liveness probe should return 200 with simple response."""
        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.uptime_seconds = 10.0
                mock_settings.APP_NAME = "OmniMedicalSuite"
                mock_settings.APP_VERSION = "2.0.0"

                response = await client.get("/health/live")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_live_response_contains_status(self):
        """Liveness response should contain a status field."""
        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.uptime_seconds = 10.0
                mock_settings.APP_NAME = "OmniMedicalSuite"
                mock_settings.APP_VERSION = "2.0.0"

                response = await client.get("/health/live")
                data = response.json()
                assert "status" in data


class TestHealthReadyEndpoint:
    """Test /health/ready endpoint."""

    @pytest.mark.asyncio
    async def test_ready_endpoint_exists(self):
        """Readiness endpoint should be registered and return a valid status."""
        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.uptime_seconds = 10.0
                mock_settings.APP_NAME = "OmniMedicalSuite"
                mock_settings.APP_VERSION = "2.0.0"

                response = await client.get("/health/ready")
                # Should not be 404 (endpoint exists)
                assert response.status_code != 404
                data = response.json()
                assert "status" in data
