from typing import Optional, List
from pydantic import BaseModel, Field

class DomainException(Exception):
    """Base class for all domain exceptions"""
    pass

class AuthenticationError(DomainException):
    """Raised when authentication fails (e.g. invalid credentials)"""
    pass

class AuthorizationError(DomainException):
    """Raised when user lacks permissions for an action"""
    pass

class ResourceNotFoundError(DomainException):
    """Raised when a requested resource is not found"""
    pass

class UserInactiveError(AuthenticationError):
    """Raised when an inactive user attempts to authenticate"""
    pass

class InvalidStatusTransitionError(DomainException):
    """Raised when an illegal incident status transition is requested"""
    pass

class IncidentNotFoundError(ResourceNotFoundError):
    """Raised when an incident is not found by ID"""
    pass


class ValidationErrorDetail(BaseModel):
    """Structured detail model for single field validation failure."""
    field: str = Field(description="Name of the invalid field or path")
    issue: str = Field(description="Validation error description")


class ErrorResponsePayload(BaseModel):
    """Standardized error payload returned in HTTP error responses."""
    error: str = Field(description="High-level error classification name")
    message: str = Field(description="Human-readable user-safe explanation")
    detail: Optional[str] = Field(default=None, description="Optional detailed error message")
    details: Optional[List[ValidationErrorDetail]] = Field(default=None, description="Optional list of field validation errors")


