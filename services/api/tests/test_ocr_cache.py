"""
Unit tests for OCR Cache module.
Tests: caching, TTL, multi-tenant isolation, LRU eviction, hash generation.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from services.api.ocr.cache import OCRCache, CacheEntry


@pytest.fixture
async def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.zcard = AsyncMock(return_value=0)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrange = AsyncMock(return_value=[])
    redis.keys = AsyncMock(return_value=[])
    redis.delete = AsyncMock(return_value=1)
    redis.incr = AsyncMock(return_value=1)
    redis.hincrby = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.close = AsyncMock()
    return redis


@pytest.fixture
async def cache(mock_redis):
    """Create an OCR cache instance."""
    return await OCRCache.init(mock_redis, ttl=3600)


class TestOCRCache:
    """Test suite for OCR Cache."""

    @pytest.mark.asyncio
    async def test_compute_file_hash(self):
        """Test SHA-256 fingerprint generation."""
        content = b"test medical document content"
        hash1 = OCRCache.compute_file_hash(content)
        hash2 = OCRCache.compute_file_hash(content)

        assert len(hash1) == 32
        assert hash1 == hash2  # Deterministic

        # Different content = different hash
        different = OCRCache.compute_file_hash(b"different content")
        assert hash1 != different

    @pytest.mark.asyncio
    async def test_serialize_engine_config(self):
        """Test engine config serialization."""
        config1 = OCRCache.serialize_engine_config(
            ["mixed_engine", "tesseract"], "ar"
        )
        config2 = OCRCache.serialize_engine_config(
            ["tesseract", "mixed_engine"], "ar"  # Same, different order
        )
        config3 = OCRCache.serialize_engine_config(
            ["mixed_engine", "tesseract"], "en"  # Different language
        )

        assert config1 == config2  # Order-independent
        assert config1 != config3  # Language matters
        assert len(config1) == 16

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache, mock_redis):
        """Test cache miss returns None."""
        mock_redis.get.return_value = None

        result = await cache.get("hash123", "config456")

        assert result is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit(self, cache, mock_redis):
        """Test cache hit returns CacheEntry."""
        entry_data = {
            "file_hash": "hash123",
            "engine_config": "config456",
            "result": {"text": "test"},
            "confidence": 0.95,
            "created_at": 1000.0,
            "accessed_at": 1000.0,
            "access_count": 1,
            "tenant_id": None
        }
        mock_redis.get.return_value = json.dumps(entry_data)

        result = await cache.get("hash123", "config456")

        assert result is not None
        assert isinstance(result, CacheEntry)

    @pytest.mark.asyncio
    async def test_cache_set(self, cache, mock_redis):
        """Test storing result in cache."""
        result = {"text": "medical text", "confidence": 0.94}

        await cache.set("hash123", "config456", result, 0.94)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == 3600  # TTL

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, cache, mock_redis):
        """Test tenant isolation."""
        mock_redis.get.side_effect = [
            None,  # tenant1 miss
            json.dumps({"result": "tenant2_data"})  # tenant2 hit
        ]

        result1 = await cache.get("hash123", "config456", tenant_id="tenant1")
        result2 = await cache.get("hash123", "config456", tenant_id="tenant2")

        assert result1 is None
        assert result2 is not None

    @pytest.mark.asyncio
    async def test_invalidate_by_file_hash(self, cache, mock_redis):
        """Test invalidating specific file."""
        mock_redis.keys.return_value = ["ocr_cache:default:hash123:config1"]

        count = await cache.invalidate(file_hash="hash123", tenant_id="default")

        assert count == 1
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache, mock_redis):
        """Test bulk invalidation."""
        mock_redis.keys.return_value = [
            "ocr_cache:default:h1:c1",
            "ocr_cache:default:h2:c2"
        ]

        count = await cache.invalidate()

        assert count == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, cache, mock_redis):
        """Test cache statistics."""
        mock_redis.hgetall.return_value = {
            "hits": "100",
            "misses": "20",
            "stores": "120"
        }
        mock_redis.keys.return_value = ["key1", "key2"]

        stats = await cache.get_stats()

        assert stats["hits"] == 100
        assert stats["misses"] == 20
        assert stats["hit_rate"] == 0.8333  # 100/120
        assert stats["current_entries"] == 2

    @pytest.mark.asyncio
    async def test_lru_access_tracking(self, cache, mock_redis):
        """Test access count increments on cache hit."""
        entry = {
            "file_hash": "h",
            "engine_config": "c",
            "result": {},
            "confidence": 0.9,
            "created_at": 1000.0,
            "accessed_at": 1000.0,
            "access_count": 5,
            "tenant_id": None
        }
        mock_redis.get.return_value = json.dumps(entry)

        await cache.get("h", "c")

        # Should update access metadata
        mock_redis.setex.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
