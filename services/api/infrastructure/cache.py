import time
import threading
from typing import Any, Optional, Dict, Tuple, List


class ResponseCache:
    """Thread-safe in-memory cache with Time-To-Live (TTL) expiration and prefix-based invalidation.

    Designed for caching high-cost, high-frequency, stable FastAPI response payloads.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Tuple[Any, float, float]] = {}  # key -> (value, expires_at_monotonic, created_at_epoch)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value if present and not expired.

        Args:
            key: Unique composite cache key identifier.

        Returns:
            The cached value if present and unexpired, otherwise None.
        """
        now = time.monotonic()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            val, expires_at, _ = entry
            if now > expires_at:
                # Expired - purge immediately
                del self._cache[key]
                return None
            return val

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store a value in cache with a defined Time-To-Live (TTL).

        Args:
            key: Unique composite cache key identifier.
            value: JSON-serializable or DTO response payload to store.
            ttl_seconds: Cache duration in seconds.
        """
        now_monotonic = time.monotonic()
        now_epoch = time.time()
        expires_at = now_monotonic + max(1, ttl_seconds)
        with self._lock:
            self._cache[key] = (value, expires_at, now_epoch)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache.

        Args:
            key: Cache key to invalidate.

        Returns:
            True if the key was found and removed, False otherwise.
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all cache entries whose keys start with the given prefix.

        Args:
            prefix: Key prefix string (e.g. 'suppliers:', 'incident_summary:').

        Returns:
            The number of cache entries invalidated.
        """
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
            # Clean up any expired keys while measuring size
            expired_keys = [k for k, (_, exp, _) in self._cache.items() if now > exp]
            for k in expired_keys:
                del self._cache[k]
            return len(self._cache)


# Global singleton instance for use across API route handlers
response_cache = ResponseCache()
