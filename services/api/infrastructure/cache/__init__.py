"""Infrastructure cache package.

Provides caching implementations including ResponseCache and CachePort adapters.
"""

from typing import Any, Dict, List, Optional, Tuple
import threading
import time


class ResponseCache:
    """Thread-safe in-memory cache with Time-To-Live (TTL) expiration and prefix-based invalidation.

    Designed for caching high-cost, high-frequency, stable FastAPI response payloads.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Tuple[Any, float, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value if present and not expired."""
        now = time.monotonic()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            val, expires_at, _ = entry
            if now > expires_at:
                del self._cache[key]
                return None
            return val

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store a value in cache with a defined Time-To-Live (TTL)."""
        now_monotonic = time.monotonic()
        now_epoch = time.time()
        expires_at = now_monotonic + max(1, ttl_seconds)
        with self._lock:
            self._cache[key] = (value, expires_at, now_epoch)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all cache entries whose keys start with the given prefix."""
        with self._lock:
            matching_keys: List[str] = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in matching_keys:
                del self._cache[k]
            return len(matching_keys)

    def clear(self) -> None:
        """Purge all entries from the cache."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Return the count of active (unexpired) cache entries."""
        now = time.monotonic()
        with self._lock:
            expired_keys = [k for k, (_, exp, _) in self._cache.items() if now > exp]
            for k in expired_keys:
                del self._cache[k]
            return len(self._cache)


# Global singleton instance for use across API route handlers
response_cache = ResponseCache()

from infrastructure.cache.memory_cache_adapter import (
    MemoryCacheAdapter,
    memory_cache_adapter,
)

__all__ = [
    "MemoryCacheAdapter",
    "ResponseCache",
    "memory_cache_adapter",
    "response_cache",
]

