import os
import sys
import pytest
from pydantic import ValidationError

MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, MONOREPO_ROOT)

API_DIR = os.path.join(MONOREPO_ROOT, 'services', 'api')
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from domain.schemas.incident_schema import IncidentCreateSchema
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin
from application.services.incident_service import IncidentService
from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository
from tinydb import TinyDB

def test_valid_incident_schema():
    valid_data = {
        "title": "Lost package",
        "description": "Package #1234 lost in transit",
        "category": "last_mile",
        "status": "open",
        "origin": "customer",
        "branch": "central"
    }
    schema = IncidentCreateSchema(**valid_data)
    assert schema.title == "Lost package"
    assert schema.category == IncidentCategory.LAST_MILE
    assert schema.status == IncidentStatus.OPEN
    assert schema.origin == IncidentOrigin.CUSTOMER
    assert schema.branch == "central"

def test_invalid_category_raises_error():
    invalid_data = {
        "title": "Damaged goods",
        "description": "Box arrived broken",
        "category": "unknown_category",
        "status": "open",
        "origin": "customer",
        "branch": "central"
    }
    with pytest.raises(ValidationError) as excinfo:
        IncidentCreateSchema(**invalid_data)
    assert "category" in str(excinfo.value)

def test_invalid_status_raises_error():
    invalid_data = {
        "title": "Damaged goods",
        "description": "Box arrived broken",
        "category": "warehouse",
        "status": "invalid_status",
        "origin": "customer",
        "branch": "central"
    }
    with pytest.raises(ValidationError) as excinfo:
        IncidentCreateSchema(**invalid_data)
    assert "status" in str(excinfo.value)

def test_empty_title_raises_validation_error():
    invalid_data = {
        "title": "   ",
        "description": "Valid description",
        "category": "warehouse",
        "status": "open",
        "origin": "internal",
        "branch": "central"
    }
    with pytest.raises(ValidationError):
        IncidentCreateSchema(**invalid_data)

def test_incident_service_creation(tmp_path):
    db_file = tmp_path / "test_db.json"
    db = TinyDB(str(db_file))
    repo = TinyDBIncidentRepository(db)
    service = IncidentService(repo)

    schema = IncidentCreateSchema(
        title="Delayed Return Processing",
        description="Customer return waiting over 48h",
        category=IncidentCategory.REVERSE_LOGISTICS,
        status=IncidentStatus.IN_PROGRESS,
        origin=IncidentOrigin.BRANCH,
        branch="zaragoza"
    )

    created = service.create_incident(schema)
    assert created.id.startswith("inc_")
    assert created.title == "Delayed Return Processing"
    assert created.branch == "zaragoza"

    summary = service.get_summary()
    assert summary["total_incidents"] == 1
    assert summary["by_category"]["reverse_logistics"] == 1
    assert summary["by_status"]["in_progress"] == 1
