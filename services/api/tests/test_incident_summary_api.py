import os
import sys
import pytest
from fastapi.testclient import TestClient

API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

os.environ["JWT_SECRET_KEY"] = "test-secret-key-12345"

from main import app


from infrastructure.database import get_db
from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository
from scripts.seed_incidents import seed_incidents_from_csv

def test_summary_api_endpoint(tmp_path):
    db_file = tmp_path / "test_api_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)

    csv_file = tmp_path / "sample_incidents.csv"
    csv_content = """id,date,category,status,satisfaction_index
1,2023-10-01,warehouse,closed,4.5
2,2023-10-02,reverse_logistics,open,
3,2023-10-02,last_mile,closed,5.0
4,2023-10-03,customer_experience,closed,1.2
5,2023-10-03,warehouse,open,
6,2023-10-04,invalid_category,open,
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    # Seed initial test data
    seed_res = seed_incidents_from_csv(str(csv_file))
    assert seed_res["inserted_count"] == 5

    # Test API endpoint
    client = TestClient(app)
    response = client.get("/api/incidents/summary")

    assert response.status_code == 200
    data = response.json()

    assert data["total_incidents"] == 5
    assert data["by_status"]["resolved"] == 3 # 'closed' mapped to 'resolved'
    assert data["by_status"]["open"] == 2
    assert data["by_category"]["warehouse"] == 2
    assert data["by_category"]["reverse_logistics"] == 1
    assert data["by_category"]["last_mile"] == 1
    assert data["by_category"]["customer_experience"] == 1

def test_create_incident_api_endpoint(tmp_path):
    db_file = tmp_path / "test_api_create_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)

    client = TestClient(app)
    payload = {
        "title": "Damaged pallet in Warehouse A",
        "description": "Forklift collision damaged bottom pallet",
        "category": "warehouse",
        "status": "open",
        "origin": "internal",
        "branch": "los_angeles"
    }

    response = client.post("/api/incidents", json=payload)
    assert response.status_code == 201
    res_data = response.json()

    assert res_data["id"].startswith("inc_")
    assert res_data["title"] == payload["title"]
    assert res_data["branch"] == "los_angeles"
