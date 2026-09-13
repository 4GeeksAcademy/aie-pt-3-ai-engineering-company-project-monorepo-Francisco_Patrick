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

def test_empty_database_summary(tmp_path):
    """GET /api/incidents/summary on empty DB returns 0 totals and zeroed maps without crashing."""
    db_file = tmp_path / "empty_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    response = client.get("/api/incidents/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_incidents"] == 0
    assert data["by_status"]["open"] == 0
    assert data["by_status"]["in_progress"] == 0
    assert data["by_status"]["resolved"] == 0
    assert data["by_status"]["discarded"] == 0
    assert data["by_category"]["warehouse"] == 0
    assert data["by_category"]["reverse_logistics"] == 0
    assert data["by_origin"]["customer"] == 0

def test_incident_detail_not_found(tmp_path):
    """GET /api/incidents/{id} returns HTTP 404 when ID does not exist."""
    db_file = tmp_path / "404_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    response = client.get("/api/incidents/non-existent-id-999")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data.get("detail", "").lower() or "not found" in data.get("message", "").lower()

def test_incident_detail_found(tmp_path):
    """GET /api/incidents/{id} returns full incident details when found."""
    db_file = tmp_path / "detail_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    create_res = client.post("/api/incidents", json={
        "title": "Warehouse Scanner Outage",
        "description": "Main barcode scanner unresponsive in north aisle",
        "category": "warehouse",
        "status": "open",
        "origin": "customer",
        "branch": "north_branch"
    })
    assert create_res.status_code == 201
    created = create_res.json()
    incident_id = created["id"]

    get_res = client.get(f"/api/incidents/{incident_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == incident_id
    assert detail["title"] == "Warehouse Scanner Outage"
    assert detail["branch"] == "north_branch"

def test_incident_list_filtering(tmp_path):
    """GET /api/incidents correctly filters by status, category, origin, and branch."""
    db_file = tmp_path / "filter_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    inc1 = client.post("/api/incidents", json={
        "title": "Incident One",
        "description": "Warehouse stock delay",
        "category": "warehouse",
        "status": "open",
        "origin": "customer",
        "branch": "branch_a"
    }).json()

    inc2 = client.post("/api/incidents", json={
        "title": "Incident Two",
        "description": "Return package lost",
        "category": "reverse_logistics",
        "status": "in_progress",
        "origin": "internal",
        "branch": "branch_b"
    }).json()

    # Filter by category
    res = client.get("/api/incidents?category=warehouse")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == inc1["id"]

    # Filter by status
    res = client.get("/api/incidents?status=in_progress")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == inc2["id"]

    # Filter by branch
    res = client.get("/api/incidents?branch=branch_a")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == inc1["id"]

    # Filter by origin
    res = client.get("/api/incidents?origin=internal")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == inc2["id"]

    # Multi-attribute filter match
    res = client.get("/api/incidents?category=warehouse&status=open&branch=branch_a")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Multi-attribute filter mismatch
    res = client.get("/api/incidents?category=warehouse&status=in_progress")
    assert res.status_code == 200
    assert len(res.json()) == 0

def test_populated_database_summary(tmp_path):
    """GET /api/incidents/summary returns correct aggregated totals across 4 dimensions."""
    db_file = tmp_path / "summary_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    client.post("/api/incidents", json={
        "title": "Summary Test 1",
        "description": "Desc 1",
        "category": "warehouse",
        "status": "open",
        "origin": "customer",
        "branch": "branch_a"
    })
    client.post("/api/incidents", json={
        "title": "Summary Test 2",
        "description": "Desc 2",
        "category": "last_mile",
        "status": "in_progress",
        "origin": "customer",
        "branch": "branch_a"
    })

    res = client.get("/api/incidents/summary")
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_incidents"] == 2
    assert summary["by_status"]["open"] == 1
    assert summary["by_status"]["in_progress"] == 1
    assert summary["by_category"]["warehouse"] == 1
    assert summary["by_category"]["last_mile"] == 1
    assert summary["by_origin"]["customer"] == 2
    assert summary["by_branch"]["branch_a"] == 2
