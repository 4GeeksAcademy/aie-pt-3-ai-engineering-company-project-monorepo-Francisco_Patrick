"""Backward compatibility alias for domain exceptions.

All domain exceptions are canonicalized in domain.common.exceptions.
"""

from domain.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    DomainException,
    DuplicateEntityError,
    EntityNotFoundError,
    ErrorResponsePayload,
    IncidentNotFoundError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    ResourceNotFoundError,
    UserInactiveError,
    ValidationErrorDetail,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "BusinessRuleViolationError",
    "DomainException",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "ErrorResponsePayload",
    "IncidentNotFoundError",
    "InsufficientStockError",
    "InvalidStatusTransitionError",
    "ResourceNotFoundError",
    "UserInactiveError",
    "ValidationErrorDetail",
]
