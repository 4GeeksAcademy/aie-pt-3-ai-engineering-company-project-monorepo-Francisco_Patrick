"""Authentication, User, Profile, and Security driven port interfaces.

Defines the abstract contracts between application services and infrastructure adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from domain.auth.models import PasswordResetToken, Profile, User


class UserRepositoryPort(ABC):
    """Driven port interface for User entity persistence operations."""

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve a user by unique identifier."""
        ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by email address."""
        ...

    @abstractmethod
    def save(self, user: User) -> User:
        """Persist a new or modified user entity."""
        ...

    @abstractmethod
    def list_all(self) -> List[User]:
        """List all registered users."""
        ...

    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """Delete a user entity by identifier."""
        ...

    # Backward compatibility signatures for existing legacy callers
    def create(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy helper for dict-based user creation."""
        user = User(**user_data)
        saved = self.save(user)
        return saved.model_dump()

    def get_all(self) -> List[Dict[str, Any]]:
        """Legacy helper for dict-based list."""
        return [u.model_dump() for u in self.list_all()]

    def update(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Legacy helper for dict-based user update."""
        existing = self.get_by_id(user_id)
        if not existing:
            return None
        data = existing.model_dump()
        data.update(update_data)
        updated = self.save(User(**data))
        return updated.model_dump()


class ProfileRepositoryPort(ABC):
    """Driven port interface for User Profile persistence operations."""

    @abstractmethod
    def get_by_user_id(self, user_id: str) -> Optional[Profile]:
        """Retrieve a profile associated with user_id."""
        ...

    @abstractmethod
    def save(self, profile: Profile) -> Profile:
        """Persist a new or modified profile entity."""
        ...

    @abstractmethod
    def delete_by_user_id(self, user_id: str) -> bool:
        """Delete profile associated with user_id."""
        ...

    # Backward compatibility signatures for existing legacy callers
    def create(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy helper for dict-based profile creation."""
        profile = Profile(**profile_data)
        saved = self.save(profile)
        return saved.model_dump()

    def update(self, profile_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Legacy helper for dict-based profile update."""
        # Find by profile_id or update directly
        ...

    def delete(self, profile_id: str) -> bool:
        """Legacy helper for dict-based profile deletion."""
        ...


class SecurityPort(ABC):
    """Driven port interface for password hashing, verification, and JWT tokens."""

    @abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against hashed password."""
        ...

    @abstractmethod
    def hash_password(self, plain_password: str) -> str:
        """Hash a plain password."""
        ...

    def get_password_hash(self, password: str) -> str:
        """Alias for hash_password."""
        return self.hash_password(password)

    @abstractmethod
    def create_access_token(self, subject: str, expires_delta_minutes: Optional[int] = None) -> str:
        """Generate a signed JWT access token for subject (user_id)."""
        ...

    @abstractmethod
    def decode_access_token(self, token: str) -> str:
        """Decode and validate JWT access token, returning subject user ID."""
        ...


class PasswordResetTokenRepositoryPort(ABC):
    """Driven port interface for single-use password reset tokens."""

    @abstractmethod
    def create_token(self, user_id: str, raw_token: str, expires_in_minutes: int = 30) -> Dict[str, Any]:
        """Create and persist a hashed reset token for user_id."""
        ...

    @abstractmethod
    def get_valid_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        """Retrieve valid unexpired and unused token record."""
        ...

    @abstractmethod
    def mark_used(self, token_id: str) -> bool:
        """Mark token record as consumed."""
        ...

    @abstractmethod
    def invalidate_user_tokens(self, user_id: str) -> int:
        """Invalidate all pending tokens for user_id."""
        ...


class AuditLogRepositoryPort(ABC):
    """Driven port interface for recording security audit events."""

    @abstractmethod
    def log_event(
        self,
        event_type: str,
        user_id: Optional[str],
        ip_address: str,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append an immutable security audit event."""
        ...


__all__ = [
    "AuditLogRepositoryPort",
    "PasswordResetTokenRepositoryPort",
    "ProfileRepositoryPort",
    "SecurityPort",
    "UserRepositoryPort",
]
