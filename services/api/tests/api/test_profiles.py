import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_profile_unauthorized():
    response = client.get("/profiles/me")
    assert response.status_code == 401
