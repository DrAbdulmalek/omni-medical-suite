"""Simple TTL-based cache for external API responses.

Caches drug metadata, terminology lookups, and literature metadata.
Does NOT cache patient-specific data.
"""
from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """In-memory TTL cache with size limit.

    Thread-safe for single-threaded use (providers are called sequentially).
    For multi-threaded use, wrap calls with a lock.
    """

    def __init__(self, max_entries: int = 1000, default_ttl: float = 86400):
        self._store: dict[str, tuple[float, Any]] = {}
        self._max_entries = max_entries
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        if ttl is None:
            ttl = self._default_ttl
        if len(self._store) >= self._max_entries:
            # Evict oldest entry
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
        self._store[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
