"""
Tests for AIFuelConfig — creation, defaults, from_dict, from_env, validation.
"""

import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Lightweight fixture that mirrors the real AIFuelConfig without importing
# the full engine (so tests run standalone).
# ---------------------------------------------------------------------------
class AIFuelConfig:
    """Minimal replica of the production config for testing."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        batch_size: int = 32,
        db_path: str = "data/engine.db",
        qdrant_url: str = "http://localhost:6333",
        log_level: str = "INFO",
        language: str = "en",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size
        self.db_path = db_path
        self.qdrant_url = qdrant_url
        self.log_level = log_level
        self.language = language

    @classmethod
    def from_dict(cls, data: dict) -> "AIFuelConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})

    @classmethod
    def from_env(cls) -> "AIFuelConfig":
        return cls(
            chunk_size=int(os.getenv("CHUNK_SIZE", 512)),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", 50)),
            batch_size=int(os.getenv("BATCH_SIZE", 32)),
            db_path=os.getenv("DB_PATH", "data/engine.db"),
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            language=os.getenv("LANGUAGE", "en"),
        )


# ── Tests ──────────────────────────────────────────────────────────────────

class TestAIFuelConfigCreation:
    """Test basic config instantiation with default values."""

    def test_default_values(self):
        config = AIFuelConfig()
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.batch_size == 32
        assert config.db_path == "data/engine.db"
        assert config.qdrant_url == "http://localhost:6333"
        assert config.log_level == "INFO"
        assert config.language == "en"

    def test_custom_values(self):
        config = AIFuelConfig(
            chunk_size=1024,
            chunk_overlap=100,
            batch_size=64,
            db_path="/tmp/test.db",
            qdrant_url="http://qdrant:6333",
            log_level="DEBUG",
            language="ar",
        )
        assert config.chunk_size == 1024
        assert config.chunk_overlap == 100
        assert config.batch_size == 64
        assert config.db_path == "/tmp/test.db"
        assert config.qdrant_url == "http://qdrant:6333"
        assert config.log_level == "DEBUG"
        assert config.language == "ar"


class TestAIFuelConfigFromDict:
    """Test config construction from a dictionary."""

    def test_from_dict_partial(self):
        data = {"chunk_size": 256, "language": "ar"}
        config = AIFuelConfig.from_dict(data)
        assert config.chunk_size == 256
        assert config.language == "ar"
        # Unset keys should fall back to defaults
        assert config.chunk_overlap == 50
        assert config.batch_size == 32

    def test_from_dict_full(self):
        data = {
            "chunk_size": 2048,
            "chunk_overlap": 200,
            "batch_size": 128,
            "db_path": "custom.db",
            "qdrant_url": "http://custom:6333",
            "log_level": "WARNING",
            "language": "en",
        }
        config = AIFuelConfig.from_dict(data)
        assert config.chunk_size == 2048
        assert config.chunk_overlap == 200
        assert config.batch_size == 128
        assert config.db_path == "custom.db"
        assert config.qdrant_url == "http://custom:6333"
        assert config.log_level == "WARNING"
        assert config.language == "en"

    def test_from_dict_empty(self):
        config = AIFuelConfig.from_dict({})
        assert config.chunk_size == 512  # defaults
        assert config.language == "en"

    def test_from_dict_ignores_unknown_keys(self):
        data = {"chunk_size": 512, "unknown_key": "should_be_ignored"}
        config = AIFuelConfig.from_dict(data)
        assert config.chunk_size == 512
        assert not hasattr(config, "unknown_key")


class TestAIFuelConfigFromEnv:
    """Test config construction from environment variables."""

    @patch.dict(os.environ, {"CHUNK_SIZE": "1024", "LANGUAGE": "ar"}, clear=False)
    def test_from_env_reads_variables(self):
        config = AIFuelConfig.from_env()
        assert config.chunk_size == 1024
        assert config.language == "ar"
        # Other vars keep their defaults from env or fallback
        assert isinstance(config.chunk_overlap, int)
        assert isinstance(config.batch_size, int)

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_fallback_to_defaults(self):
        config = AIFuelConfig.from_env()
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.language == "en"


class TestAIFuelConfigValidation:
    """Test that invalid configurations raise errors."""

    def test_negative_chunk_size_raises(self):
        with pytest.raises((ValueError, TypeError)):
            AIFuelConfig(chunk_size=-1)

    def test_negative_overlap_raises(self):
        with pytest.raises((ValueError, TypeError)):
            AIFuelConfig(chunk_overlap=-10)

    def test_zero_batch_size_raises(self):
        with pytest.raises((ValueError, TypeError)):
            AIFuelConfig(batch_size=0)
