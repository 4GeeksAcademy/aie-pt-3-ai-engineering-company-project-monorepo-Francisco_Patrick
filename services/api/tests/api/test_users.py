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
    assert response.status_code == 422 # Pydantic validation error for min_length=8

def test_list_users_unauthorized():
    response = client.get("/users")
    # This route requires admin user token, so it should be unauthorized without one
    assert response.status_code == 401
