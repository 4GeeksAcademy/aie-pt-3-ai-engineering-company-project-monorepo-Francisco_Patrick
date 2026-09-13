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

def test_create_valid_incident(tmp_path):
    db_file = tmp_path / "test_create_valid.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    payload = {
        "title": "Broken scanner in warehouse",
        "description": "Scanner screen cracked during inventory check",
        "category": "warehouse",
        "status": "open",
        "origin": "internal",
        "branch": "zaragoza"
    }

    response = client.post("/api/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("inc_")
    assert data["title"] == payload["title"]
    assert data["category"] == "warehouse"

def test_create_incident_missing_required_field():
    client = TestClient(app)
    # Missing 'description' and 'category'
    invalid_payload = {
        "title": "Incomplete report",
        "branch": "los_angeles"
    }

    response = client.post("/api/incidents", json=invalid_payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "Validation Error"
    assert "details" in data
    assert any("description" in d["field"] for d in data["details"])

def test_create_incident_invalid_category_enum():
    client = TestClient(app)
    invalid_payload = {
        "title": "Invalid Category Test",
        "description": "Valid description",
        "category": "unknown_category_value",
        "status": "open",
        "origin": "customer",
        "branch": "central"
    }

    response = client.post("/api/incidents", json=invalid_payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "Validation Error"
    assert any("category" in d["field"] for d in data["details"])

def test_create_incident_blank_whitespace_field():
    client = TestClient(app)
    invalid_payload = {
        "title": "   ",
        "description": "Valid description",
        "category": "warehouse",
        "status": "open",
        "origin": "customer",
        "branch": "central"
    }

    response = client.post("/api/incidents", json=invalid_payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "Validation Error"
