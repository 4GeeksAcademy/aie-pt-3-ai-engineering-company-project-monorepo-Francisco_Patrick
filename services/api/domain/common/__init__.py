"""TrackFlow shared domain package."""

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
from domain.common.ports import CachePort, NotificationPort

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "BusinessRuleViolationError",
    "CachePort",
    "DomainException",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "ErrorResponsePayload",
    "IncidentNotFoundError",
    "InsufficientStockError",
    "InvalidStatusTransitionError",
    "NotificationPort",
    "ResourceNotFoundError",
    "UserInactiveError",
    "ValidationErrorDetail",
]

