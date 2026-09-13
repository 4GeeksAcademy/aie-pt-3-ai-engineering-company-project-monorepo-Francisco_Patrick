from fastapi.testclient import TestClient


def test_get_current_user_happy_path(client: TestClient, test_users):
    """
    Happy Path: Request with valid bearer token returns current user profile payload.
    """
    token = test_users["active_token"]
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_users["active"].id
    assert data["email"] == test_users["active"].email
    assert data["is_active"] is True


def test_get_current_user_expired_token_returns_401(client: TestClient, test_users):
    """
    Edge Case: Request with expired bearer token returns HTTP 401 Unauthorized.
    """
    expired_token = test_users["expired_token"]
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


def test_get_current_user_missing_token_returns_401(client: TestClient):
    """
    Failure Mode: Request without Authorization header returns HTTP 401 Unauthorized.
    """
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]
