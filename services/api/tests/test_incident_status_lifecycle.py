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
from domain.incident_model import Incident
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin
from domain.exceptions import InvalidStatusTransitionError

def test_valid_lifecycle_transitions(tmp_path):
    db_file = tmp_path / "test_lifecycle_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    # 1. Create incident (initial status: open)
    create_res = client.post("/api/incidents", json={
        "title": "Damaged pallet",
        "description": "Found broken pallet in aisle 3",
        "category": "warehouse",
        "status": "open",
        "origin": "internal",
        "branch": "los_angeles"
    })
    assert create_res.status_code == 201
    inc_id = create_res.json()["id"]

    # 2. Transition open -> in_progress (Valid)
    patch_res = client.patch(f"/api/incidents/{inc_id}/status", json={"status": "in_progress"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "in_progress"

    # 3. Transition in_progress -> resolved (Valid)
    patch_res2 = client.patch(f"/api/incidents/{inc_id}/status", json={"status": "resolved"})
    assert patch_res2.status_code == 200
    assert patch_res2.json()["status"] == "resolved"

def test_invalid_lifecycle_transition_direct_resolved(tmp_path):
    db_file = tmp_path / "test_invalid_trans_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    create_res = client.post("/api/incidents", json={
        "title": "Lost carton",
        "description": "Carton missing during dispatch",
        "category": "last_mile",
        "status": "open",
        "origin": "internal",
        "branch": "zaragoza"
    })
    inc_id = create_res.json()["id"]

    # Attempt open -> resolved directly (Invalid)
    patch_res = client.patch(f"/api/incidents/{inc_id}/status", json={"status": "resolved"})
    assert patch_res.status_code == 400
    data = patch_res.json()
    assert data["error"] == "Invalid Status Transition"
    assert "Cannot transition" in data["message"]

def test_terminal_state_cannot_be_modified(tmp_path):
    db_file = tmp_path / "test_terminal_state_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)
    client = TestClient(app)

    create_res = client.post("/api/incidents", json={
        "title": "Broken box",
        "description": "Box crushed",
        "category": "warehouse",
        "status": "open",
        "origin": "customer",
        "branch": "central"
    })
    inc_id = create_res.json()["id"]

    # Transition open -> discarded
    client.patch(f"/api/incidents/{inc_id}/status", json={"status": "discarded"})

    # Attempt discarded -> in_progress (Invalid: terminal state)
    patch_res = client.patch(f"/api/incidents/{inc_id}/status", json={"status": "in_progress"})
    assert patch_res.status_code == 400
    assert "terminal state" in patch_res.json()["message"]
