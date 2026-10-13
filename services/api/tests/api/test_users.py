import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_user_short_password():
    response = client.post(
        "/users",
        json={
            "email": "test@example.com",
            "password": "short"
        }
    )
    assert response.status_code == 400 # Pydantic validation error returns 400 with custom handler

def test_list_users_unauthorized():
    response = client.get("/users")
    # This route requires admin user token, so it should be unauthorized without one
    assert response.status_code == 401

def test_list_users_admin(client: TestClient, test_users):
    admin_token = test_users["admin_token"]
    response = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    for u in data:
        assert "id" in u
        assert "email" in u
        assert "role" in u
        assert "is_active" in u
        assert "hashed_password" not in u

def test_get_user_admin(client: TestClient, test_users):
    admin_token = test_users["admin_token"]
    target_user = test_users["active"]
    response = client.get(f"/users/{target_user.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == target_user.id
    assert data["email"] == target_user.email
    assert "hashed_password" not in data

def test_update_user_admin(client: TestClient, test_users):
    admin_token = test_users["admin_token"]
    target_user = test_users["active"]
    response = client.put(
        f"/users/{target_user.id}",
        json={"role": "manager"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == target_user.id
    assert data["role"] == "manager"
    assert "hashed_password" not in data
