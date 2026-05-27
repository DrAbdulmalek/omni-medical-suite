"""
OCR Result Cache Module
Prevents re-processing the same file by storing SHA-256 fingerprints in Redis.
Supports TTL, cache invalidation, and multi-tenant isolation.
"""

import hashlib
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

import redis.asyncio as redis


@dataclass
class CacheEntry:
    """Represents a cached OCR result."""
    file_hash: str
    engine_config: str
    result: Dict[str, Any]
    confidence: float
    created_at: float
    accessed_at: float
    access_count: int
    tenant_id: Optional[str] = None


class OCRCache:
    """
    Redis-backed OCR result cache with multi-tenant support.

    Features:
    - SHA-256 fingerprinting for deduplication
    - Configurable TTL (default: 24 hours)
    - LRU-style access tracking
    - Per-tenant isolation
    - Cache statistics and health metrics
    """

    DEFAULT_TTL = 86400  # 24 hours
    MAX_ENTRIES_PER_TENANT = 10000

    def __init__(self, redis_client: redis.Redis, ttl: int = DEFAULT_TTL):
        self.redis = redis_client
        self.ttl = ttl
        self._initialized = False

    @classmethod
    async def init(cls, redis_client: redis.Redis, ttl: int = DEFAULT_TTL) -> "OCRCache":
        """Async factory method for initialization."""
        cache = cls(redis_client, ttl)
        cache._initialized = True
        return cache

    def _make_key(self, file_hash: str, engine_config: str, tenant_id: Optional[str] = None) -> str:
        """Generate Redis key with optional tenant isolation."""
        tenant = tenant_id or "default"
        return f"ocr_cache:{tenant}:{file_hash}:{engine_config}"

    def _make_stats_key(self, tenant_id: Optional[str] = None) -> str:
        """Key for per-tenant statistics."""
        tenant = tenant_id or "default"
        return f"ocr_cache_stats:{tenant}"

    async def _scan_keys(self, pattern: str, count: int = 100) -> List[str]:
        """Non-blocking alternative to redis.keys() using SCAN.

        Uses SCAN instead of KEYS to avoid blocking the Redis server
        in production environments with large datasets.
        """
        return [k async for k in self.redis.scan_iter(pattern, count=count)]

    async def get(
        self,
        file_hash: str,
        engine_config: str,
        tenant_id: Optional[str] = None
    ) -> Optional[CacheEntry]:
        """
        Retrieve cached OCR result.

        Args:
            file_hash: SHA-256 fingerprint of the file
            engine_config: Serialized engine configuration string
            tenant_id: Optional tenant for multi-tenant isolation

        Returns:
            CacheEntry if found, None otherwise
        """
        key = self._make_key(file_hash, engine_config, tenant_id)
        data = await self.redis.get(key)

        if not data:
            await self._increment_stat("misses", tenant_id)
            return None

        # Update access metadata
        entry = json.loads(data)
        entry["accessed_at"] = time.time()
        entry["access_count"] = entry.get("access_count", 0) + 1

        # Refresh TTL on access (LRU behavior)
        await self.redis.setex(key, self.ttl, json.dumps(entry))
        await self._increment_stat("hits", tenant_id)

        return CacheEntry(**entry)

    async def set(
        self,
        file_hash: str,
        engine_config: str,
        result: Dict[str, Any],
        confidence: float,
        tenant_id: Optional[str] = None
    ) -> None:
        """
        Store OCR result in cache.

        Args:
            file_hash: SHA-256 fingerprint
            engine_config: Serialized engine configuration
            result: OCR processing result dict
            confidence: Overall confidence score
            tenant_id: Optional tenant isolation
        """
        key = self._make_key(file_hash, engine_config, tenant_id)

        entry = CacheEntry(
            file_hash=file_hash,
            engine_config=engine_config,
            result=result,
            confidence=confidence,
            created_at=time.time(),
            accessed_at=time.time(),
            access_count=1,
            tenant_id=tenant_id
        )

        # Enforce per-tenant limit
        await self._enforce_limit(tenant_id)

        await self.redis.setex(key, self.ttl, json.dumps(asdict(entry)))
        await self._increment_stat("stores", tenant_id)

    async def invalidate(
        self,
        file_hash: Optional[str] = None,
        tenant_id: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            file_hash: Specific file to invalidate, or None for all
            tenant_id: Tenant scope, or None for all tenants
            pattern: Redis pattern for bulk invalidation

        Returns:
            Number of entries invalidated
        """
        if pattern:
            keys = await self._scan_keys(pattern)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)

        if file_hash and tenant_id:
            # Delete specific file across all engine configs for tenant
            pattern_key = f"ocr_cache:{tenant_id}:{file_hash}:*"
            keys = await self._scan_keys(pattern_key)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)

        if tenant_id:
            # Delete all entries for tenant
            pattern_key = f"ocr_cache:{tenant_id}:*"
            keys = await self._scan_keys(pattern_key)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)

        # Delete all (use with caution!)
        keys = await self._scan_keys("ocr_cache:*")
        if keys:
            await self.redis.delete(*keys)
        return len(keys)

    async def get_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get cache statistics for a tenant."""
        key = self._make_stats_key(tenant_id)
        stats = await self.redis.hgetall(key)

        hits = int(stats.get("hits", 0))
        misses = int(stats.get("misses", 0))
        stores = int(stats.get("stores", 0))
        total = hits + misses

        hit_rate = hits / total if total > 0 else 0.0

        # Count current entries using non-blocking SCAN
        pattern = f"ocr_cache:{tenant_id or 'default'}:*"
        entries = len(await self._scan_keys(pattern))

        return {
            "tenant_id": tenant_id or "default",
            "hits": hits,
            "misses": misses,
            "stores": stores,
            "hit_rate": round(hit_rate, 4),
            "total_requests": total,
            "current_entries": entries,
            "ttl_seconds": self.ttl
        }

    async def _increment_stat(self, stat_name: str, tenant_id: Optional[str] = None) -> None:
        """Increment a statistics counter."""
        key = self._make_stats_key(tenant_id)
        await self.redis.hincrby(key, stat_name, 1)

    async def _enforce_limit(self, tenant_id: Optional[str] = None) -> None:
        """Enforce maximum entries per tenant using LRU eviction.

        NOTE: scan_iter does not guarantee ordering, so the "oldest entries"
        eviction here is approximate. For production use with strict ordering
        requirements, consider maintaining a Redis sorted set (ZSET) keyed by
        created_at alongside the cache entries, and use ZRANGE to select the
        oldest entries for eviction.
        """
        pattern = f"ocr_cache:{tenant_id or 'default'}:*"
        keys = await self._scan_keys(pattern)

        if len(keys) >= self.MAX_ENTRIES_PER_TENANT:
            # Get oldest entries by created_at and delete them
            # Simplified: delete 10% oldest
            # NOTE: keys from scan_iter are NOT ordered by creation time.
            # This evicts an arbitrary 10% rather than strictly the oldest.
            to_delete = int(self.MAX_ENTRIES_PER_TENANT * 0.1)
            for key in keys[:to_delete]:
                await self.redis.delete(key)

    @staticmethod
    def compute_file_hash(file_content: bytes) -> str:
        """Compute SHA-256 fingerprint for file content."""
        return hashlib.sha256(file_content).hexdigest()[:32]

    @staticmethod
    def serialize_engine_config(
        engine_order: List[str],
        language: str,
        preprocessing: Optional[List[str]] = None
    ) -> str:
        """Serialize engine configuration for cache key generation."""
        config = {
            "engines": sorted(engine_order),
            "lang": language,
            "pre": sorted(preprocessing or [])
        }
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
