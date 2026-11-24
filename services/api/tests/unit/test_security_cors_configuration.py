"""Unit test verifying CORS security configuration rejects unauthorized origins and credentials."""

import os
from fastapi.testclient import TestClient
import pytest
from main import create_app


def test_cors_rejects_arbitrary_attacker_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that an untrusted origin is NOT granted CORS access with credentials."""
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,https://app.trackflow.io",
    )
    app = create_app()
    client = TestClient(app)

    # Preflight OPTIONS request from attacker origin
    response = client.options(
        "/api/v1/security-audit",
        headers={
            "Origin": "https://evil-attacker.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # The Access-Control-Allow-Origin header must NOT reflect evil-attacker.com
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin != "https://evil-attacker.com"
    assert allow_origin != "*"


def test_cors_accepts_whitelisted_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that whitelisted origins are granted CORS access."""
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,https://app.trackflow.io",
    )
    app = create_app()
    client = TestClient(app)

    for origin in ("http://localhost:3000", "https://app.trackflow.io"):
        response = client.options(
            "/api/v1/security-audit",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"
