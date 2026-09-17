from fastapi.testclient import TestClient


def test_forgot_password_happy_path_registered_email(client: TestClient, test_users):
    """
    Happy Path: Requesting password reset for registered email returns HTTP 200 generic message.
    """
    response = client.post(
        "/auth/forgot-password",
        json={"email": test_users["active"].email}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "If that email is registered, you will receive a reset link shortly."


def test_forgot_password_anti_enumeration_unregistered_email(client: TestClient):
    """
    Edge Case (Anti-Enumeration): Requesting password reset for unregistered email returns HTTP 200 generic message.
    """
    response = client.post(
        "/auth/forgot-password",
        json={"email": "nonexistent_account@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "If that email is registered, you will receive a reset link shortly."


def test_forgot_password_rate_limiting_returns_generic_message(client: TestClient, test_users):
    """
    Edge Case (Rate Limiting): Submitting multiple rapid requests returns generic success message.
    """
    email = test_users["active"].email
    for _ in range(5):
        response = client.post(
            "/auth/forgot-password",
            json={"email": email}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "If that email is registered, you will receive a reset link shortly."


def test_reset_password_happy_path_and_single_use_edge_case(client: TestClient, test_users, monkeypatch):
    """
    Happy Path & Edge Case: Reset password with valid token succeeds, and re-using the token returns HTTP 400.
    """
    fixed_token = "api_test_fixed_raw_reset_token"
    import secrets
    monkeypatch.setattr(secrets, "token_urlsafe", lambda n=32: fixed_token)

    # 1. Request reset to generate a token in DB
    client.post(
        "/auth/forgot-password",
        json={"email": test_users["active"].email}
    )

    # 2. Submit valid reset password payload using fixed token
    reset_response = client.post(
        "/auth/reset-password",
        json={
            "token": fixed_token,
            "new_password": "NewResetPassword123!"
        }
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["message"] == "Password successfully updated."

    # 3. Verify user can log in with new password
    login_response = client.post(
        "/auth/login",
        data={
            "username": test_users["active"].email,
            "password": "NewResetPassword123!"
        }
    )
    assert login_response.status_code == 200

    # 4. Re-using the same token returns HTTP 400 Bad Request
    reuse_response = client.post(
        "/auth/reset-password",
        json={
            "token": fixed_token,
            "new_password": "AnotherPassword123!"
        }
    )
    assert reuse_response.status_code == 400
    assert "Invalid, expired, or already used reset token" in reuse_response.json()["detail"]


def test_reset_password_invalid_token_returns_400(client: TestClient):
    """
    Failure Mode: Submitting a non-existent or invalid reset token returns HTTP 400 Bad Request.
    """
    response = client.post(
        "/auth/reset-password",
        json={
            "token": "invalid_fake_token_12345",
            "new_password": "NewPassword123!"
        }
    )

    assert response.status_code == 400
    assert "Invalid, expired, or already used reset token" in response.json()["detail"]
