"""Thread-safe in-memory cache for telemetry reports with 60-second TTL.

Conforms strictly to TrackFlow data-model.md and Constitution principles.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """Internal cache entry container holding serialized payload and expiration timestamp."""

    payload: Dict[str, Any]
    created_at: float
    expires_at: float


class TelemetryReportCache:
    """Thread-safe in-memory cache with 60-second TTL for telemetry reports.

    Utilizes threading.Lock to synchronize concurrent access across FastAPI worker threads.
    Implements lazy eviction on retrieval and LRU-style cleanup upon capacity saturation.
    """

    def __init__(self, default_ttl_seconds: float = 60.0, max_entries: int = 256) -> None:
        """Initialize the in-memory cache.

        Args:
            default_ttl_seconds: Cache entry time-to-live in seconds (defaults to 60.0).
            max_entries: Maximum number of entries allowed in memory before eviction.
        """
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._entries: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def generate_key(start_date: datetime, end_date: datetime) -> str:
        """Generate a deterministic cache key from UTC normalized reporting bounds.

        Args:
            start_date: Starting datetime boundary.
            end_date: Ending datetime boundary.

        Returns:
            Formatted cache key string: '{start_iso}_{end_iso}'.
        """
        start_utc = (
            start_date.replace(tzinfo=timezone.utc)
            if start_date.tzinfo is None
            else start_date.astimezone(timezone.utc)
        )
        end_utc = (
            end_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None
            else end_date.astimezone(timezone.utc)
        )
        return f"{start_utc.isoformat()}_{end_utc.isoformat()}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached payload if present and unexpired.

        Args:
            key: Cache key string.

        Returns:
            Cached payload dictionary, or None on cache miss or expiration.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None

            now = time.monotonic()
            if now >= entry.expires_at:
                # Lazy eviction on expiration
                del self._entries[key]
                return None

            return entry.payload

    def set(
        self,
        key: str,
        payload: Dict[str, Any],
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """Store or update a cached payload with TTL.

        Args:
            key: Deterministic cache key string.
            payload: JSON-serializable report payload dictionary.
            ttl_seconds: Optional custom TTL in seconds, defaulting to instance default (60.0s).
        """
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        now = time.monotonic()
        expires_at = now + ttl

        with self._lock:
            # If at or exceeding max capacity, purge expired entries first
            if len(self._entries) >= self._max_entries and key not in self._entries:
                self._purge_expired_locked(now)

                # If still at capacity, evict the oldest entry
                if len(self._entries) >= self._max_entries:
                    oldest_key = min(self._entries.keys(), key=lambda k: self._entries[k].created_at)
                    del self._entries[oldest_key]

            self._entries[key] = CacheEntry(
                payload=payload,
                created_at=now,
                expires_at=expires_at,
            )

    def invalidate(self, key: str) -> bool:
        """Evict a specific cache key.

        Args:
            key: Cache key string.

        Returns:
            True if key was present and removed, False otherwise.
        """
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._entries.clear()

    def cleanup_expired(self) -> int:
        """Explicitly purge all expired entries from cache.

        Returns:
            Count of expired entries evicted.
        """
        now = time.monotonic()
        with self._lock:
            return self._purge_expired_locked(now)

    def _purge_expired_locked(self, current_monotonic: float) -> int:
        """Internal helper to purge expired entries while lock is already held.

        Args:
            current_monotonic: Current monotonic time float.

        Returns:
            Count of evicted entries.
        """
        expired_keys = [
            k for k, entry in self._entries.items() if current_monotonic >= entry.expires_at
        ]
        for k in expired_keys:
            del self._entries[k]
        return len(expired_keys)

    def size(self) -> int:
        """Return the count of active (unexpired) entries currently stored.

        Returns:
            Number of active cache entries.
        """
        now = time.monotonic()
        with self._lock:
            self._purge_expired_locked(now)
            return len(self._entries)

    def __len__(self) -> int:
        """Return current active entries count."""
        return self.size()


__all__ = ["CacheEntry", "TelemetryReportCache"]
