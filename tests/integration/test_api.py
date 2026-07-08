"""
Integration tests for the API layer.

Tests the FastAPI endpoints end-to-end (requires full app setup).
Run: pytest tests/integration/test_api.py -m integration
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


@pytest.mark.integration
class TestAPIEndpoints:
    """Test API endpoint availability and basic responses."""

    def test_health_endpoint(self):
        """Test that /health endpoint returns 200."""
        try:
            from fastapi.testclient import TestClient
            from app.main import app
        except ImportError:
            pytest.skip("FastAPI app not importable")

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200

    def test_docs_endpoint_available(self):
        """Test that /docs endpoint returns 200."""
        try:
            from fastapi.testclient import TestClient
            from app.main import app
        except ImportError:
            pytest.skip("FastAPI app not importable")

        with TestClient(app) as client:
            response = client.get("/docs")
            assert response.status_code == 200