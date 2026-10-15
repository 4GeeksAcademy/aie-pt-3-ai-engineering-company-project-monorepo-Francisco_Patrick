"""Authentication and user management application Data Transfer Objects (DTOs)."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ProfileBaseDTO(BaseModel):
    """User profile mutable payload."""

    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class UserCreateDTO(BaseModel):
    """Registration request payload."""

    email: str = Field(..., min_length=3, description="User email address")
    password: str = Field(..., min_length=8, description="Plaintext password (>= 8 chars)")
    profile: Optional[ProfileBaseDTO] = None


class UserUpdateDTO(BaseModel):
    """User modification request payload."""

    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[Literal["user", "admin", "manager"]] = None
    is_active: Optional[bool] = None


class UserResponseDTO(BaseModel):
    """Sanitized public projection for user account entity (zero password hash leaks)."""

    id: str
    email: str
    role: Literal["user", "admin", "manager"]
    is_active: bool
    created_at: str


class TokenDTO(BaseModel):
    """Bearer access token payload."""

    access_token: str
    token_type: str = "bearer"


class PasswordResetRequestDTO(BaseModel):
    """Forgot password request payload."""

    email: str


class PasswordResetConfirmDTO(BaseModel):
    """Confirm password reset payload."""

    token: str
    new_password: str = Field(..., min_length=8)


class PasswordChangeDTO(BaseModel):
    """Authenticated change password payload."""

    current_password: str
    new_password: str = Field(..., min_length=8)


__all__ = [
    "PasswordChangeDTO",
    "PasswordResetConfirmDTO",
    "PasswordResetRequestDTO",
    "ProfileBaseDTO",
    "TokenDTO",
    "UserCreateDTO",
    "UserResponseDTO",
    "UserUpdateDTO",
]
