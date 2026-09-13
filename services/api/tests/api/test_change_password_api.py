from fastapi.testclient import TestClient


def test_change_password_happy_path(client: TestClient, test_users):
    """
    Happy Path: Authenticated user providing correct current password successfully updates password.
    """
    token = test_users["active_token"]
    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": test_users["active_raw_password"],
            "new_password": "BrandNewPassword123!"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password successfully changed."

    # Verify user can log in with new password
    login_response = client.post(
        "/auth/login",
        data={
            "username": test_users["active"].email,
            "password": "BrandNewPassword123!"
        }
    )
    assert login_response.status_code == 200


def test_change_password_incorrect_current_password_returns_400(client: TestClient, test_users):
    """
    Edge Case: Authenticated user providing wrong current password returns HTTP 400 Bad Request.
    """
    token = test_users["active_token"]
    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongCurrentPassword123!",
            "new_password": "BrandNewPassword123!"
        }
    )

    assert response.status_code == 400
    assert "Incorrect current password" in response.json()["detail"]


def test_change_password_unauthenticated_returns_401(client: TestClient):
    """
    Failure Mode: Unauthenticated request returns HTTP 401 Unauthorized.
    """
    response = client.post(
        "/auth/change-password",
        json={
            "current_password": "Password123!",
            "new_password": "BrandNewPassword123!"
        }
    )

    assert response.status_code == 401
