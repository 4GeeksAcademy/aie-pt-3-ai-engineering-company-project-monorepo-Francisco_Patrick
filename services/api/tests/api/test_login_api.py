from fastapi.testclient import TestClient


def test_login_happy_path_returns_access_token(client: TestClient, test_users):
    """
    Happy Path: Submitting valid credentials returns HTTP 200 with a bearer JWT access token.
    """
    response = client.post(
        "/auth/login",
        data={
            "username": test_users["active"].email,
            "password": test_users["active_raw_password"]
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_inactive_user_returns_403_forbidden(client: TestClient, test_users):
    """
    Edge Case: Login attempt for an inactive user account returns HTTP 403 Forbidden.
    """
    response = client.post(
        "/auth/login",
        data={
            "username": test_users["inactive"].email,
            "password": test_users["inactive_raw_password"]
        }
    )

    assert response.status_code == 403
    assert "User account is inactive" in response.json()["detail"]


def test_login_invalid_credentials_returns_401_unauthorized(client: TestClient, test_users):
    """
    Failure Mode: Wrong password or unregistered email returns HTTP 401 Unauthorized with WWW-Authenticate header.
    """
    response = client.post(
        "/auth/login",
        data={
            "username": test_users["active"].email,
            "password": "WrongPassword123!"
        }
    )

    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_empty_fields_returns_400_validation_error(client: TestClient):
    """
    Edge Case: Missing or empty credentials payload returns HTTP 400 validation error.
    """
    response = client.post(
        "/auth/login",
        data={"username": "", "password": ""}
    )

    assert response.status_code == 400
    assert "Validation Error" in response.json()["error"]
