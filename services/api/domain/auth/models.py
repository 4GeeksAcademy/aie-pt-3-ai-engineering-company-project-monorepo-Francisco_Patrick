"""Authentication, User, Profile, Token, and Audit Log domain models.

Pure business entities for TrackFlow auth domain with zero framework or database dependencies.
"""

from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """User account domain entity."""

    id: str = Field(..., description="Unique UUID string identifying user")
    email: str = Field(..., description="Unique email address")
    hashed_password: str = Field(..., description="Bcrypt hash of user password")
    role: Literal["user", "admin", "manager"] = Field(default="user", description="Authorization role")
    is_active: bool = Field(default=True, description="Account active status")
    created_at: str = Field(..., description="Creation ISO timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last updated ISO timestamp")


class Profile(BaseModel):
    """User profile domain entity."""

    id: Optional[str] = Field(default=None, description="Unique profile identifier")
    user_id: str = Field(..., description="Referenced user ID foreign key")
    name: Optional[str] = Field(default=None, description="User full display name")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    address: Optional[str] = Field(default=None, description="Physical shipping/billing address")
    updated_at: Optional[str] = Field(default=None, description="Last updated ISO timestamp")


class PasswordResetToken(BaseModel):
    """One-time password reset token value object."""

    id: str = Field(..., description="Unique token record ID")
    user_id: str = Field(..., description="Target user ID")
    token_hash: str = Field(..., description="SHA-256 hash of random token")
    expires_at: str = Field(..., description="Expiration ISO timestamp")
    used_at: Optional[str] = Field(default=None, description="Timestamp when consumed")
    created_at: str = Field(..., description="Creation ISO timestamp")

    @property
    def is_used(self) -> bool:
        """True if the token was already consumed."""
        return self.used_at is not None


class AuditLog(BaseModel):
    """Security audit log record."""

    id: str = Field(..., description="Unique audit event ID")
    event_type: str = Field(..., description="Classification taxonomy (e.g. forgot_password_request_success)")
    user_id: Optional[str] = Field(default=None, description="User ID if authenticated")
    ip_address: str = Field(default="127.0.0.1", description="Client IP address")
    details: Optional[str] = Field(default=None, description="Safe masked event details")
    timestamp: str = Field(..., description="Event capture ISO timestamp")


__all__ = ["AuditLog", "PasswordResetToken", "Profile", "User"]
