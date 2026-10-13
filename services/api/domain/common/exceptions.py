"""TrackFlow shared domain exceptions and standardized error response models.

Defines base and domain-specific exception hierarchies for the pure domain core,
ensuring zero framework (FastAPI/SQLModel/TinyDB) dependencies.
"""

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class DomainException(Exception):
    """Base class for all TrackFlow domain exceptions."""

    def __init__(self, message: str = "A domain rule violation occurred.") -> None:
        """Initialize domain exception with human-readable message.

        Args:
            message: Descriptive domain error message.
        """
        self.message = message
        super().__init__(message)


class AuthenticationError(DomainException):
    """Raised when authentication fails (e.g. invalid credentials or expired token)."""

    def __init__(self, message: str = "Authentication failed.") -> None:
        """Initialize authentication error."""
        super().__init__(message)


class AuthorizationError(DomainException):
    """Raised when a user lacks permissions for the requested operation."""

    def __init__(self, message: str = "Not authorized to perform this operation.") -> None:
        """Initialize authorization error."""
        super().__init__(message)


class ResourceNotFoundError(DomainException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Requested resource was not found.") -> None:
        """Initialize resource not found error."""
        super().__init__(message)


class EntityNotFoundError(ResourceNotFoundError):
    """Raised when a domain entity cannot be retrieved by its identifier."""

    def __init__(
        self,
        message: Optional[str] = None,
        entity_name: str = "Entity",
        entity_id: Optional[Any] = None,
    ) -> None:
        """Initialize entity not found error with optional entity metadata.

        Args:
            message: Optional explicit message override.
            entity_name: Name of the domain entity (e.g. 'Supplier', 'SKU').
            entity_id: Identifier value searched for.
        """
        self.entity_name = entity_name
        self.entity_id = entity_id
        if message is None:
            if entity_id is not None:
                message = f"{entity_name} with identifier '{entity_id}' was not found."
            else:
                message = f"{entity_name} was not found."
        super().__init__(message)


class IncidentNotFoundError(EntityNotFoundError):
    """Raised when an incident is not found by ID."""

    def __init__(
        self,
        message: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> None:
        """Initialize incident not found error.

        Args:
            message: Optional explicit message override.
            incident_id: ID of the missing incident.
        """
        if message is None:
            if incident_id is not None:
                message = f"Incident with ID '{incident_id}' was not found."
            else:
                message = "Incident was not found."
        super().__init__(message=message, entity_name="Incident", entity_id=incident_id)


class UserInactiveError(AuthenticationError):
    """Raised when an inactive user attempts to authenticate."""

    def __init__(self, message: str = "User account is inactive.") -> None:
        """Initialize inactive user error."""
        super().__init__(message)


class BusinessRuleViolationError(DomainException):
    """Raised when an operation violates a core domain business rule or invariant."""

    def __init__(self, message: str = "Business rule violation.") -> None:
        """Initialize business rule violation error."""
        super().__init__(message)


class InvalidStatusTransitionError(BusinessRuleViolationError):
    """Raised when an illegal incident or entity status transition is requested."""

    def __init__(
        self,
        message: Optional[str] = None,
        current_status: Optional[str] = None,
        new_status: Optional[str] = None,
    ) -> None:
        """Initialize invalid status transition error.

        Args:
            message: Optional explicit message override.
            current_status: Origin status of the entity.
            new_status: Target status rejected by transition rules.
        """
        self.current_status = current_status
        self.new_status = new_status
        if message is None:
            if current_status and new_status:
                message = f"Invalid status transition from '{current_status}' to '{new_status}'."
            else:
                message = "Illegal status transition."
        super().__init__(message)


class InsufficientStockError(BusinessRuleViolationError):
    """Raised when an outbound stock exit quantity exceeds current available inventory."""

    def __init__(
        self,
        message: Optional[str] = None,
        sku_id: Optional[int] = None,
        available: Optional[int] = None,
        requested: Optional[int] = None,
    ) -> None:
        """Initialize insufficient stock error.

        Args:
            message: Optional explicit message override.
            sku_id: Identifier of the SKU experiencing a shortage.
            available: Current calculated stock quantity.
            requested: Requested outbound exit quantity.
        """
        self.sku_id = sku_id
        self.available = available
        self.requested = requested
        if message is None:
            if sku_id is not None and available is not None and requested is not None:
                message = (
                    f"Insufficient stock for SKU {sku_id}: requested {requested}, "
                    f"available {available}."
                )
            else:
                message = "Insufficient stock available for requested quantity."
        super().__init__(message)


class DuplicateEntityError(BusinessRuleViolationError):
    """Raised when an entity with unique identity already exists."""

    def __init__(
        self,
        message: Optional[str] = None,
        entity_name: str = "Entity",
        field: Optional[str] = None,
        value: Optional[Any] = None,
    ) -> None:
        """Initialize duplicate entity error.

        Args:
            message: Optional explicit message override.
            entity_name: Name of the domain entity.
            field: Field name enforcing uniqueness (e.g. 'email', 'sku').
            value: Value that clashed.
        """
        self.entity_name = entity_name
        self.field = field
        self.value = value
        if message is None:
            if field and value is not None:
                message = f"{entity_name} with {field}='{value}' already exists."
            else:
                message = f"{entity_name} already exists."
        super().__init__(message)


class ValidationErrorDetail(BaseModel):
    """Structured detail model for single field validation failure."""

    field: str = Field(description="Name of the invalid field or path")
    issue: str = Field(description="Validation error description")


class ErrorResponsePayload(BaseModel):
    """Standardized error payload returned in HTTP error responses."""

    error: str = Field(description="High-level error classification name")
    message: str = Field(description="Human-readable user-safe explanation")
    detail: Optional[str] = Field(default=None, description="Optional detailed error message")
    details: Optional[List[ValidationErrorDetail]] = Field(
        default=None, description="Optional list of field validation errors"
    )
