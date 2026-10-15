"""Unit tests for shared domain exceptions and error response models."""

import pytest
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


def test_domain_exception_base_hierarchy() -> None:
    """Verify that domain exceptions inherit properly from DomainException."""
    exc = DomainException("Base domain failure")
    assert str(exc) == "Base domain failure"
    assert exc.message == "Base domain failure"
    assert isinstance(exc, Exception)


def test_authentication_and_authorization_exceptions() -> None:
    """Verify authentication, user inactive, and authorization exception semantics."""
    auth_err = AuthenticationError("Invalid login")
    assert isinstance(auth_err, DomainException)
    assert str(auth_err) == "Invalid login"

    inactive_err = UserInactiveError()
    assert isinstance(inactive_err, AuthenticationError)
    assert str(inactive_err) == "User account is inactive."

    perm_err = AuthorizationError()
    assert isinstance(perm_err, DomainException)
    assert str(perm_err) == "Not authorized to perform this operation."


def test_entity_not_found_exceptions() -> None:
    """Verify EntityNotFoundError and IncidentNotFoundError formatting and inheritance."""
    res_err = ResourceNotFoundError("Missing resource")
    assert isinstance(res_err, DomainException)

    entity_err = EntityNotFoundError(entity_name="Supplier", entity_id=42)
    assert isinstance(entity_err, ResourceNotFoundError)
    assert entity_err.entity_name == "Supplier"
    assert entity_err.entity_id == 42
    assert "Supplier with identifier '42' was not found." in str(entity_err)

    incident_err = IncidentNotFoundError(incident_id="inc_999")
    assert isinstance(incident_err, EntityNotFoundError)
    assert incident_err.entity_id == "inc_999"
    assert "Incident with ID 'inc_999' was not found." in str(incident_err)


def test_business_rule_and_inventory_exceptions() -> None:
    """Verify BusinessRuleViolationError, InvalidStatusTransitionError, and InsufficientStockError."""
    rule_err = BusinessRuleViolationError("Constraint failed")
    assert isinstance(rule_err, DomainException)

    trans_err = InvalidStatusTransitionError(current_status="resolved", new_status="open")
    assert isinstance(trans_err, BusinessRuleViolationError)
    assert "Invalid status transition from 'resolved' to 'open'." in str(trans_err)

    stock_err = InsufficientStockError(sku_id=101, available=5, requested=12)
    assert isinstance(stock_err, BusinessRuleViolationError)
    assert "Insufficient stock for SKU 101: requested 12, available 5." in str(stock_err)

    dup_err = DuplicateEntityError(entity_name="SKU", field="sku_code", value="SKU-001")
    assert isinstance(dup_err, BusinessRuleViolationError)
    assert "SKU with sku_code='SKU-001' already exists." in str(dup_err)


def test_error_response_payload_models() -> None:
    """Verify Pydantic models for structured error responses and validation details."""
    detail = ValidationErrorDetail(field="cost_per_kg", issue="Must be greater than 0")
    assert detail.field == "cost_per_kg"
    assert detail.issue == "Must be greater than 0"

    payload = ErrorResponsePayload(
        error="ValidationError",
        message="Invalid request body",
        detail="One or more fields failed validation",
        details=[detail],
    )
    assert payload.error == "ValidationError"
    assert payload.details is not None
    assert len(payload.details) == 1
    assert payload.details[0].field == "cost_per_kg"
