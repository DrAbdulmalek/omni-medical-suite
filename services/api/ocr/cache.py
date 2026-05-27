"""OCR result caching layer using Redis + content hashing.

Ensures the same file content is never processed twice, regardless of filename.
Uses BLAKE2b hashing for content identification and stores results with a 30-day TTL.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from redis import Redis

logger = logging.getLogger(__name__)


class OCRCache:
    """Redis-backed cache for OCR results, keyed by file content hash.

    Parameters
    ----------
    redis_url:
        Redis connection URL (default: ``redis://localhost:6379/0``).
    ttl_seconds:
        Time-to-live for cached entries (default: 30 days).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        ttl_seconds: int = 60 * 60 * 24 * 30,  # 30 days
    ) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, file_content: bytes, ocr_engine: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached OCR result for the given file content and engine.

        Returns ``None`` on cache miss.
        """
        file_hash = self._compute_hash(file_content)
        key = f"ocr:{ocr_engine}:{file_hash}"
        try:
            cached = self.redis.get(key)
        except Exception as exc:
            logger.warning("OCRCache.get() failed: %s", exc)
            return None

        if cached is None:
            logger.debug("OCRCache miss for key=%s", key)
            return None

        logger.debug("OCRCache hit for key=%s", key)
        return json.loads(cached)

    def set(
        self,
        file_content: bytes,
        ocr_engine: str,
        result: Dict[str, Any],
    ) -> None:
        """Store an OCR result in the cache."""
        file_hash = self._compute_hash(file_content)
        key = f"ocr:{ocr_engine}:{file_hash}"
        try:
            self.redis.setex(key, self.ttl_seconds, json.dumps(result, ensure_ascii=False))
            logger.debug("OCRCache set for key=%s (ttl=%ds)", key, self.ttl_seconds)
        except Exception as exc:
            logger.warning("OCRCache.set() failed: %s", exc)

    def invalidate(self, file_content: bytes, ocr_engine: str | None = None) -> int:
        """Remove cached entries for a given file hash.

        If *ocr_engine* is ``None``, all engines for the file hash are removed.

        Returns the number of keys deleted.
        """
        file_hash = self._compute_hash(file_content)
        pattern = f"ocr:*:{file_hash}" if ocr_engine is None else f"ocr:{ocr_engine}:{file_hash}"
        keys = self.redis.keys(pattern)
        if keys:
            return self.redis.delete(*keys)
        return 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(file_content: bytes, digest_size: int = 32) -> str:
        """Compute a BLAKE2b hash of the file content."""
        return hashlib.blake2b(file_content, digest_size=digest_size).hexdigest()
