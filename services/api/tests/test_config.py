"""Tests for app.core.config module."""
import os
import pytest
from unittest.mock import patch


class TestSettings:
    """Test Pydantic Settings configuration."""

    def test_default_app_name(self, mock_settings):
        """Verify default application name."""
        assert mock_settings.APP_NAME == "OmniMedicalSuite"

    def test_default_version(self, mock_settings):
        """Verify default version string."""
        assert mock_settings.APP_VERSION == "2.0.0"

    def test_default_ocr_fusion_method(self, mock_settings):
        """Verify default OCR fusion method."""
        assert mock_settings.OCR_FUSION_METHOD == "weighted_vote"

    def test_default_confidence_threshold(self, mock_settings):
        """Verify default confidence threshold."""
        assert mock_settings.OCR_CONFIDENCE_THRESHOLD == 0.6

    def test_default_semantic_threshold(self, mock_settings):
        """Verify default semantic similarity threshold."""
        assert mock_settings.SEMANTIC_SIMILARITY_THRESHOLD == 0.85

    def test_default_rate_limits(self, mock_settings):
        """Verify default rate limiting parameters."""
        assert mock_settings.RATE_LIMIT_REQUESTS == 100
        assert mock_settings.RATE_LIMIT_WINDOW == 60

    def test_max_upload_size_bytes(self, mock_settings):
        """Verify upload size is correctly converted to bytes."""
        expected = 50 * 1024 * 1024
        assert mock_settings.max_upload_size_bytes == expected

    def test_ocr_engine_priority_list(self, mock_settings):
        """Verify OCR engine priority is a list of strings."""
        assert isinstance(mock_settings.OCR_ENGINE_PRIORITY, list)
        assert all(isinstance(e, str) for e in mock_settings.OCR_ENGINE_PRIORITY)
        assert "tesseract" in mock_settings.OCR_ENGINE_PRIORITY

    def test_cors_origins_list(self, mock_settings):
        """Verify CORS origins is a list."""
        assert isinstance(mock_settings.CORS_ORIGINS, list)
        assert "http://localhost:3000" in mock_settings.CORS_ORIGINS

    def test_has_mistral_false_when_no_key(self, mock_settings):
        """Verify Mistral availability is False when no key is set."""
        assert mock_settings.has_mistral is False

    def test_has_gemini_false_when_no_key(self, mock_settings):
        """Verify Gemini availability is False when no key is set."""
        assert mock_settings.has_gemini is False

    def test_database_url(self, mock_settings):
        """Verify database URL format."""
        assert "sqlite" in mock_settings.DATABASE_URL
        assert ".db" in mock_settings.DATABASE_URL

    def test_redis_url(self, mock_settings):
        """Verify Redis URL format."""
        assert mock_settings.REDIS_URL.startswith("redis://")

    def test_log_level(self, mock_settings):
        """Verify default log level."""
        assert mock_settings.LOG_LEVEL == "DEBUG"

    def test_dbscan_eps(self, mock_settings):
        """Verify DBSCAN epsilon parameter."""
        assert mock_settings.DBSCAN_EPS == 0.3
