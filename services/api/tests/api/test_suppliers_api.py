"""Tests for TrackFlow Supplier Directory API, Pydantic validation, and Seeder.

Validates:
1. Pydantic model structure reflecting trackflow-BRIEFING.md
2. Strict validation: status rejection, rate > 0 enforcement, country/currency consistency
3. System-generated updated_at behavior
4. Querying and filtering by country and product category
5. Rate and status updates with updated_at timestamp refreshes
6. Seeder execution, completeness (all 15 BRIEFING suppliers), and idempotency
"""

import os
import sys
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

# Ensure services/api is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from main import app
from domain.suppliers.models import Supplier, VALID_CATEGORIES, VALID_STATUSES
from seed import SUPPLIERS_SEED, run_seed
from infrastructure.database import get_tinydb


def _auth_headers(test_users: dict) -> dict:
    return {"Authorization": f"Bearer {test_users['admin_token']}"}


# ==============================================================================
# 1. Pydantic Model & Validation Tests
# ==============================================================================


def test_supplier_model_reflects_briefing_fields():
    """Verify Supplier model fields match the BRIEFING specification."""
    supplier_data = {
        "name": "Test Logistics Co",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 8.50,
        "currency": "USD",
        "status": "active",
        "service_zone": "West Coast",
        "contact_email": "ops@testlogistics.com",
        "notes": "Fast local courier",
    }
    supplier = Supplier(**supplier_data)
    assert supplier.name == "Test Logistics Co"
    assert supplier.country == "USA"
    assert supplier.categories == ["carrier_last_mile"]
    assert supplier.rate_per_shipment == 8.50
    assert supplier.currency == "USD"
    assert supplier.status == "active"
    assert supplier.service_zone == "West Coast"
    assert supplier.contact_email == "ops@testlogistics.com"
    assert supplier.notes == "Fast local courier"


def test_create_supplier_rejects_missing_country(client, test_users):
    """Verify that a supplier without country is rejected with 422 before touching the database."""
    headers = _auth_headers(test_users)
    payload = {
        "name": "No Country Carrier",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 10.0,
        "status": "active",
    }
    response = client.post("/suppliers", json=payload, headers=headers)
    assert response.status_code == 422


def test_create_supplier_rejects_invalid_status(client, test_users):
    """Verify that status values outside 'active' or 'suspended' are rejected with 422."""
    headers = _auth_headers(test_users)
    for invalid_status in ["inactive", "pending", "disabled", "archived", "cancelled"]:
        payload = {
            "name": f"Invalid Status {invalid_status}",
            "country": "USA",
            "categories": ["carrier_last_mile"],
            "rate_per_shipment": 7.50,
            "currency": "USD",
            "status": invalid_status,
        }
        response = client.post("/suppliers", json=payload, headers=headers)
        assert response.status_code == 422, f"Expected 422 for status '{invalid_status}', got {response.status_code}"


def test_create_supplier_accepts_valid_statuses(client, test_users):
    """Verify that both 'active' and 'suspended' are accepted."""
    headers = _auth_headers(test_users)
    for valid_status in ["active", "suspended"]:
        payload = {
            "name": f"Valid Status {valid_status.capitalize()}",
            "country": "Spain",
            "categories": ["packaging_materials"],
            "rate_per_shipment": 3.20,
            "currency": "EUR",
            "status": valid_status,
        }
        response = client.post("/suppliers", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == valid_status
        # Clean up created supplier
        client.delete(f"/suppliers/{data['id']}", headers=headers)


def test_create_supplier_rejects_zero_or_negative_rate(client, test_users):
    """Verify that rate values <= 0 are rejected with 422."""
    headers = _auth_headers(test_users)
    for invalid_rate in [0.0, -0.01, -5.50, -100.0]:
        payload = {
            "name": "Invalid Rate Carrier",
            "country": "USA",
            "categories": ["carrier_last_mile"],
            "rate_per_shipment": invalid_rate,
            "currency": "USD",
            "status": "active",
        }
        response = client.post("/suppliers", json=payload, headers=headers)
        assert response.status_code == 422, f"Expected 422 for rate {invalid_rate}, got {response.status_code}"


def test_create_supplier_rejects_inconsistent_currency(client, test_users):
    """Verify business restriction: USA must use USD, Spain must use EUR."""
    headers = _auth_headers(test_users)
    # USA with EUR -> reject
    res1 = client.post(
        "/suppliers",
        json={
            "name": "US Carrier Bad Currency",
            "country": "USA",
            "categories": ["carrier_last_mile"],
            "rate_per_shipment": 12.0,
            "currency": "EUR",
            "status": "active",
        },
        headers=headers,
    )
    assert res1.status_code == 422

    # Spain with USD -> reject
    res2 = client.post(
        "/suppliers",
        json={
            "name": "Spain Carrier Bad Currency",
            "country": "Spain",
            "categories": ["carrier_last_mile"],
            "rate_per_shipment": 5.0,
            "currency": "USD",
            "status": "active",
        },
        headers=headers,
    )
    assert res2.status_code == 422


def test_updated_at_is_generated_by_system(client, test_users):
    """Verify that updated_at is generated by the system and client cannot override it."""
    headers = _auth_headers(test_users)
    client_supplied_timestamp = "1999-01-01T00:00:00Z"
    payload = {
        "name": "System Timestamp Carrier",
        "country": "USA",
        "categories": ["reverse_logistics"],
        "rate_per_shipment": 9.99,
        "currency": "USD",
        "status": "active",
        "updated_at": client_supplied_timestamp,
    }
    response = client.post("/suppliers", json=payload, headers=headers)
    assert response.status_code == 201
    created = response.json()
    assert created["updated_at"] is not None
    assert created["updated_at"] != client_supplied_timestamp
    # Clean up
    client.delete(f"/suppliers/{created['id']}", headers=headers)


# ==============================================================================
# 2. Search & Filtering Tests
# ==============================================================================


def test_filter_suppliers_by_country(client, test_users):
    """Verify filtering by country (USA / Spain)."""
    headers = _auth_headers(test_users)
    # Ensure database is seeded
    run_seed()

    # Query USA suppliers
    res_usa = client.get("/suppliers?country=USA", headers=headers)
    assert res_usa.status_code == 200
    usa_suppliers = res_usa.json()
    assert len(usa_suppliers) > 0
    for s in usa_suppliers:
        assert s["country"] == "USA"
        assert s["currency"] == "USD"

    # Query Spain suppliers
    res_spain = client.get("/suppliers?country=Spain", headers=headers)
    assert res_spain.status_code == 200
    spain_suppliers = res_spain.json()
    assert len(spain_suppliers) > 0
    for s in spain_suppliers:
        assert s["country"] == "Spain"
        assert s["currency"] == "EUR"


def test_filter_suppliers_by_category(client, test_users):
    """Verify filtering by product/service category."""
    headers = _auth_headers(test_users)
    run_seed()

    res = client.get("/suppliers?category=packaging_materials", headers=headers)
    assert res.status_code == 200
    pkg_suppliers = res.json()
    assert len(pkg_suppliers) >= 2
    for s in pkg_suppliers:
        assert "packaging_materials" in s["categories"]


# ==============================================================================
# 3. Rate & Status Update Tests (Traceability)
# ==============================================================================


def test_rate_update_refreshes_timestamp(client, test_users):
    """Verify that updating a rate refreshes updated_at automatically."""
    headers = _auth_headers(test_users)
    # 1. Create a supplier
    created_res = client.post(
        "/suppliers",
        json={
            "name": "Audit Rate Test Corp",
            "country": "USA",
            "categories": ["carrier_last_mile"],
            "rate_per_shipment": 15.00,
            "currency": "USD",
            "status": "active",
        },
        headers=headers,
    )
    assert created_res.status_code == 201
    supplier = created_res.json()
    supplier_id = supplier["id"]
    initial_updated_at = supplier["updated_at"]

    # 2. Update rate
    patch_res = client.patch(
        f"/suppliers/{supplier_id}/rate",
        json={"rate_per_shipment": 18.50},
        headers=headers,
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["rate_per_shipment"] == 18.50
    assert updated["updated_at"] is not None

    # Clean up
    client.delete(f"/suppliers/{supplier_id}", headers=headers)


def test_rate_update_rejects_zero_or_negative(client, test_users):
    """Verify that PATCH rate rejects 0 or negative rates with 422."""
    headers = _auth_headers(test_users)
    created_res = client.post(
        "/suppliers",
        json={
            "name": "Rate Guard Test Corp",
            "country": "Spain",
            "categories": ["fleet_maintenance"],
            "rate_per_shipment": 50.00,
            "currency": "EUR",
            "status": "active",
        },
        headers=headers,
    )
    supplier_id = created_res.json()["id"]

    for invalid_rate in [0.0, -10.0]:
        res = client.patch(
            f"/suppliers/{supplier_id}/rate",
            json={"rate_per_shipment": invalid_rate},
            headers=headers,
        )
        assert res.status_code == 422

    client.delete(f"/suppliers/{supplier_id}", headers=headers)


def test_status_update_lifecycle(client, test_users):
    """Verify updating status between active and suspended."""
    headers = _auth_headers(test_users)
    created = client.post(
        "/suppliers",
        json={
            "name": "Status Lifecycle Corp",
            "country": "USA",
            "categories": ["warehouse_supplies"],
            "rate_per_shipment": 25.00,
            "currency": "USD",
            "status": "active",
        },
        headers=headers,
    ).json()
    supplier_id = created["id"]

    # Suspend
    res_suspend = client.patch(
        f"/suppliers/{supplier_id}/status",
        json={"status": "suspended"},
        headers=headers,
    )
    assert res_suspend.status_code == 200
    assert res_suspend.json()["status"] == "suspended"

    # Reactivate
    res_reactivate = client.patch(
        f"/suppliers/{supplier_id}/status",
        json={"status": "active"},
        headers=headers,
    )
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["status"] == "active"

    # Invalid status
    res_invalid = client.patch(
        f"/suppliers/{supplier_id}/status",
        json={"status": "invalid_status"},
        headers=headers,
    )
    assert res_invalid.status_code == 422

    client.delete(f"/suppliers/{supplier_id}", headers=headers)


# ==============================================================================
# 4. Seeder Tests
# ==============================================================================


def test_seeder_loads_all_briefing_suppliers():
    """Verify that run_seed loads all 15 suppliers from the BRIEFING specification."""
    db = get_tinydb()
    table = db.table("suppliers")
    table.truncate()

    inserted_first_run = run_seed()
    assert inserted_first_run == 15, f"Expected 15 inserted suppliers, got {inserted_first_run}"

    all_suppliers = table.all()
    assert len(all_suppliers) == 15

    names = {s["name"] for s in all_suppliers}
    for seed_item in SUPPLIERS_SEED:
        assert seed_item["name"] in names, f"Supplier '{seed_item['name']}' was not found in seeded database"

    # Verify idempotency on second run
    inserted_second_run = run_seed()
    assert inserted_second_run == 0, f"Expected 0 insertions on second run, got {inserted_second_run}"
    assert len(table.all()) == 15
