import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_login_invalid_credentials():
    response = client.post(
        "/auth/login",
        data={"username": "nonexistent@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]

def test_get_current_user_unauthorized():
    response = client.get("/auth/me")
    assert response.status_code == 401
