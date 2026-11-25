"""Unit test verifying error handlers return sanitized messages without raw str(e) traces."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from core.exceptions import register_exception_handlers


def test_unhandled_exception_returns_sanitized_500() -> None:
    """Verify unhandled Exception does not leak raw exception message or database details."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/trigger-crash")
    def trigger_crash() -> None:
        # Simulate unexpected DB error with internal connection strings
        raise RuntimeError("OperationalError: FATAL: password authentication failed for user 'postgres' at host aws-1.pooler.supabase.com:6543")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/trigger-crash")

    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "Server Error"
    assert "An unexpected error occurred" in data["message"]
    # Ensure sensitive database details and passwords are NOT leaked
    assert "OperationalError" not in str(data)
    assert "postgres" not in str(data)
    assert "supabase.com" not in str(data)


def test_http_exception_returns_clean_payload() -> None:
    """Verify HTTPException details are properly structured."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/trigger-404")
    def trigger_404() -> None:
        raise HTTPException(status_code=404, detail="Order not found")

    client = TestClient(app)
    response = client.get("/trigger-404")

    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "HTTP Error"
    assert data["message"] == "Order not found"
