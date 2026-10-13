"""Unit tests for global domain-to-HTTP exception handlers in core/exceptions.py."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.exceptions import register_exception_handlers
from domain.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    DomainException,
    DuplicateEntityError,
    EntityNotFoundError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    ResourceNotFoundError,
    UserInactiveError,
)


def create_test_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/error/entity-not-found")
    def trigger_entity_not_found():
        raise EntityNotFoundError(entity_name="Supplier", entity_id=42)

    @test_app.get("/error/resource-not-found")
    def trigger_resource_not_found():
        raise ResourceNotFoundError("Specific resource was not located")

    @test_app.get("/error/status-transition")
    def trigger_status_transition():
        raise InvalidStatusTransitionError(current_status="resolved", new_status="open")

    @test_app.get("/error/insufficient-stock")
    def trigger_insufficient_stock():
        raise InsufficientStockError(sku_id=10, available=5, requested=20)

    @test_app.get("/error/duplicate-entity")
    def trigger_duplicate_entity():
        raise DuplicateEntityError(entity_name="User", field="email", value="test@test.com")

    @test_app.get("/error/auth-error")
    def trigger_auth_error():
        raise AuthenticationError("Invalid Bearer token")

    @test_app.get("/error/user-inactive")
    def trigger_user_inactive():
        raise UserInactiveError("User account disabled")

    @test_app.get("/error/authorization")
    def trigger_authorization():
        raise AuthorizationError("Forbidden access to resource")

    @test_app.get("/error/business-rule")
    def trigger_business_rule():
        raise BusinessRuleViolationError("Cannot complete operation under policy")

    @test_app.get("/error/generic-domain")
    def trigger_generic_domain():
        raise DomainException("Unspecified domain rule violation")

    @test_app.get("/error/generic-unhandled")
    def trigger_generic_unhandled():
        raise RuntimeError("Internal database connection dropped: secret_db_pw")

    return test_app


def test_entity_not_found_handling() -> None:
    client = TestClient(create_test_app())
    res = client.get("/error/entity-not-found")
    assert res.status_code == 404
    data = res.json()
    assert data["error"] == "Not Found"
    assert "Supplier with identifier '42' was not found." in data["message"]


def test_invalid_status_transition_handling() -> None:
    client = TestClient(create_test_app())
    res = client.get("/error/status-transition")
    assert res.status_code == 400
    data = res.json()
    assert data["error"] == "Invalid Status Transition"
    assert "from 'resolved' to 'open'" in data["message"]


def test_insufficient_stock_handling() -> None:
    client = TestClient(create_test_app())
    res = client.get("/error/insufficient-stock")
    assert res.status_code == 400
    data = res.json()
    assert data["error"] == "Insufficient Stock"
    assert "requested 20, available 5" in data["message"]


def test_duplicate_entity_handling() -> None:
    client = TestClient(create_test_app())
    res = client.get("/error/duplicate-entity")
    assert res.status_code == 409
    data = res.json()
    assert data["error"] == "Conflict"
    assert "already exists" in data["message"]


def test_authentication_error_handling() -> None:
    client = TestClient(create_test_app())
    res = client.get("/error/auth-error")
    assert res.status_code == 401
    assert "Bearer" in res.headers.get("WWW-Authenticate", "")
    data = res.json()
    assert data["error"] == "Unauthorized"


def test_authorization_error_handling() -> None:
    client = TestClient(create_test_app())
    res = client.get("/error/authorization")
    assert res.status_code == 403
    data = res.json()
    assert data["error"] == "Forbidden"


def test_generic_exception_sanitization_no_leak() -> None:
    client = TestClient(create_test_app(), raise_server_exceptions=False)
    res = client.get("/error/generic-unhandled")
    assert res.status_code == 500
    data = res.json()
    assert data["error"] == "Server Error"
    # Ensure sensitive runtime info and tracebacks are never leaked
    assert "secret_db_pw" not in res.text
    assert "Traceback" not in res.text
