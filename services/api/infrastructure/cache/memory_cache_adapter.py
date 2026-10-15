"""In-memory cache adapter implementing CachePort.

Provides a thread-safe, TTL-based caching adapter for application and domain services.
"""

from typing import Any, Optional
from domain.common.ports import CachePort
from infrastructure.cache import ResponseCache, response_cache


class MemoryCacheAdapter(CachePort):
    """Concrete cache adapter implementation backed by thread-safe ResponseCache."""

    def __init__(self, backend: Optional[ResponseCache] = None) -> None:
        """Initialize the adapter with an optional ResponseCache backend.

        Args:
            backend: Optional ResponseCache instance. Defaults to shared response_cache.
        """
        self._backend: ResponseCache = backend if backend is not None else response_cache

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value if present and not expired.

        Args:
            key: Unique composite cache key identifier.

        Returns:
            The cached value if present and valid, otherwise None.
        """
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Store a value in cache with a defined Time-To-Live (TTL).

        Args:
            key: Unique composite cache key identifier.
            value: Serializable payload or domain entity projection.
            ttl_seconds: Cache duration in seconds (defaults to 60s).
        """
        self._backend.set(key, value, ttl_seconds)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache.

        Args:
            key: Cache key to invalidate.

        Returns:
            True if the key was found and removed, False otherwise.
        """
        return self._backend.invalidate(key)

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all cache entries whose keys start with the given prefix.

        Args:
            prefix: Key namespace prefix (e.g. 'suppliers:', 'incident_summary:').

        Returns:
            The number of cache entries invalidated.
        """
        return self._backend.invalidate_prefix(prefix)

    def clear(self) -> None:
        """Purge all entries from the cache."""
        self._backend.clear()

    def size(self) -> int:
        """Return the count of active (unexpired) cache entries.

        Returns:
            Number of unexpired items in cache.
        """
        return self._backend.size()


# Singleton instance for dependency injection across application services
memory_cache_adapter = MemoryCacheAdapter()

__all__ = ["MemoryCacheAdapter", "memory_cache_adapter"]
