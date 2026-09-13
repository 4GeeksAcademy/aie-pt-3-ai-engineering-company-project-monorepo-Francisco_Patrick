from fastapi.testclient import TestClient


def test_register_user_happy_path(client: TestClient):
    """
    Happy Path: Submitting valid user registration details creates user & profile, returning HTTP 201 Created.
    """
    payload = {
        "email": "newsignup@example.com",
        "password": "SecurePassword123!",
        "profile": {
            "name": "New Signup",
            "phone": "+1234567890",
            "address": "123 Test St"
        }
    }

    response = client.post("/users", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newsignup@example.com"
    assert data["is_active"] is True
    assert "id" in data


def test_register_user_duplicate_email_returns_400(client: TestClient, test_users):
    """
    Edge Case: Attempting registration with an existing email returns HTTP 400 Bad Request.
    """
    payload = {
        "email": test_users["active"].email,
        "password": "Password123!",
        "profile": {"name": "Duplicate User"}
    }

    response = client.post("/users", json=payload)

    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_register_user_missing_required_fields_returns_400(client: TestClient):
    """
    Failure Mode: Submitting invalid/missing required fields returns HTTP 400 validation error.
    """
    payload = {
        "email": "invalid-email-format",
        "password": ""
    }

    response = client.post("/users", json=payload)

    assert response.status_code in (400, 422)
