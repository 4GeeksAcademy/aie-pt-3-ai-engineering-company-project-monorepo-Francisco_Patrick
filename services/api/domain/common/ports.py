"""Shared domain port interfaces for TrackFlow hexagonal architecture.

Defines abstract Driven Port contracts for common cross-cutting infrastructure services
(caching, notifications) ensuring zero dependencies on external frameworks or databases.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class CachePort(ABC):
    """Abstract driven port interface for caching operations."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value if present and not expired.

        Args:
            key: Unique composite cache key identifier.

        Returns:
            The cached value if present and valid, otherwise None.
        """
        ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Store a value in cache with a defined Time-To-Live (TTL).

        Args:
            key: Unique composite cache key identifier.
            value: Serializable payload or domain entity projection.
            ttl_seconds: Cache duration in seconds (defaults to 60s).
        """
        ...

    @abstractmethod
    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache.

        Args:
            key: Cache key to invalidate.

        Returns:
            True if the key was found and removed, False otherwise.
        """
        ...

    @abstractmethod
    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all cache entries whose keys start with the given prefix.

        Args:
            prefix: Key namespace prefix (e.g. 'suppliers:', 'incident_summary:').

        Returns:
            The number of cache entries invalidated.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Purge all entries from the cache."""
        ...


class NotificationPort(ABC):
    """Abstract driven port interface for external messaging and notifications."""

    @abstractmethod
    def send_password_reset(self, to_email: str, reset_link: str) -> bool:
        """Send a password reset notification email to a user.

        Args:
            to_email: Target recipient email address.
            reset_link: Full URI link containing one-time reset token.

        Returns:
            True if notification was accepted/sent successfully, False otherwise.
        """
        ...


__all__ = ["CachePort", "NotificationPort"]
