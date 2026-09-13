import os
import sys
import tempfile
import pytest
from tinydb import TinyDB

MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, MONOREPO_ROOT)

API_DIR = os.path.join(MONOREPO_ROOT, 'services', 'api')
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from domain.incident_model import Incident
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin
from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository
from scripts.seed_incidents import seed_incidents_from_csv

def test_incident_transformation_and_repo(tmp_path):
    db_file = tmp_path / "test_db.json"
    db = TinyDB(str(db_file))
    repo = TinyDBIncidentRepository(db)

    incident = Incident(
        title="Test Title",
        description="Test Description",
        category=IncidentCategory.WAREHOUSE,
        status=IncidentStatus.OPEN,
        origin=IncidentOrigin.CUSTOMER,
        branch="central",
        legacy_id="101"
    )

    repo.save(incident)
    assert len(repo.find_all()) == 1

    found = repo.find_by_legacy_id("101")
    assert found is not None
    assert found.title == "Test Title"

def test_seed_incidents_idempotency(tmp_path):
    csv_file = tmp_path / "test_incidents.csv"
    csv_content = """id,date,category,status,satisfaction_index
1,2023-10-01,warehouse,closed,4.5
2,2023-10-02,reverse_logistics,open,
3,2023-10-02,invalid_category,open,
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    db_file = tmp_path / "test_db.json"
    os.environ["TINYDB_PATH"] = str(db_file)

    # First seeding run
    res1 = seed_incidents_from_csv(str(csv_file))
    assert res1["inserted_count"] == 2
    assert res1["invalid_count"] == 1
    assert res1["skipped_duplicate_count"] == 0

    # Second seeding run (idempotent)
    res2 = seed_incidents_from_csv(str(csv_file))
    assert res2["inserted_count"] == 0
    assert res2["skipped_duplicate_count"] == 2
    assert res2["invalid_count"] == 1
