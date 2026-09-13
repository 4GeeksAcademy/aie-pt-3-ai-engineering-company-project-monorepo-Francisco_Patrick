import os
import sys
import pytest
from fastapi.testclient import TestClient

MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, MONOREPO_ROOT)

API_DIR = os.path.join(MONOREPO_ROOT, 'services', 'api')
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

os.environ["JWT_SECRET_KEY"] = "test-secret-key-12345"

from main import app

def test_validation_error_format_no_stack_trace():
    client = TestClient(app)
    # Post invalid payload with missing description and invalid category
    invalid_payload = {
        "title": "Short title",
        "category": "invalid_category",
        "status": "open"
    }

    response = client.post("/api/incidents", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()

    assert data["error"] == "Validation Error"
    assert "One or more fields failed validation" in data["message"]
    assert "details" in data
    assert isinstance(data["details"], list)
    # Ensure no raw python traceback strings exist in response body
    assert "Traceback (most recent call last)" not in response.text

def test_not_found_error_format_no_stack_trace():
    client = TestClient(app)
    response = client.get("/api/incidents/non_existent_route")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data or "error" in data
    assert "Traceback" not in response.text

