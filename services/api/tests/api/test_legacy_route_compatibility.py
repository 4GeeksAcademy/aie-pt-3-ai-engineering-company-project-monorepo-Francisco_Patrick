"""Regression tests guaranteeing legacy route prefixes stay identical to canonical /api/v1 routes."""

from datetime import datetime, timezone
from typing import Dict, List, Tuple

import pytest

# (legacy_path, v1_path) pairs for read-only endpoints that must respond identically
READ_ROUTE_PAIRS: List[Tuple[str, str]] = [
    ("/suppliers", "/api/v1/suppliers"),
    ("/inventory/products", "/api/v1/inventory/products"),
    ("/inventory/orders", "/api/v1/inventory/orders"),
    ("/api/incidents", "/api/v1/incidents"),
    ("/api/incidents/summary", "/api/v1/incidents/summary"),
    ("/auth/me", "/api/v1/auth/me"),
    ("/profiles/me", "/api/v1/profiles/me"),
]


def _headers(test_users: Dict) -> Dict[str, str]:
    return {"Authorization": f"Bearer {test_users['admin_token']}"}


@pytest.mark.parametrize("legacy_path,v1_path", READ_ROUTE_PAIRS)
def test_read_routes_match_between_legacy_and_v1(client, test_users, legacy_path, v1_path):
    headers = _headers(test_users)
    legacy = client.get(legacy_path, headers=headers)
    canonical = client.get(v1_path, headers=headers)

    assert legacy.status_code == canonical.status_code
    assert legacy.status_code == 200
    assert legacy.json() == canonical.json()


@pytest.mark.parametrize("legacy_path,v1_path", READ_ROUTE_PAIRS)
def test_protected_routes_reject_anonymous_identically(client, legacy_path, v1_path):
    if legacy_path in ("/inventory/products", "/api/incidents", "/api/incidents/summary"):
        pytest.skip("Endpoint is intentionally public in the legacy contract")
    legacy = client.get(legacy_path)
    canonical = client.get(v1_path)
    assert legacy.status_code == canonical.status_code == 401


def test_admin_users_listing_matches(client, test_users):
    headers = _headers(test_users)
    legacy = client.get("/users", headers=headers)
    canonical = client.get("/api/v1/users", headers=headers)
    assert legacy.status_code == canonical.status_code == 200
    assert legacy.json() == canonical.json()


def test_supplier_lifecycle_works_on_both_prefixes(client, test_users):
    headers = _headers(test_users)
    for prefix in ("/suppliers", "/api/v1/suppliers"):
        created = client.post(
            prefix,
            json={
                "name": f"Compat Supplier {prefix}",
                "country": "Spain",
                "categories": ["packaging"],
                "cost_per_kg": 12.5,
                "status": "active",
            },
            headers=headers,
        )
        assert created.status_code == 201
        supplier_id = created.json()["id"]

        assert client.get(f"{prefix}/{supplier_id}", headers=headers).status_code == 200
        assert (
            client.patch(
                f"{prefix}/{supplier_id}/rate", json={"cost_per_kg": 20.0}, headers=headers
            ).status_code
            == 200
        )
        assert client.delete(f"{prefix}/{supplier_id}", headers=headers).status_code == 204
        assert client.get(f"{prefix}/{supplier_id}", headers=headers).status_code == 404


def test_inventory_missing_product_returns_404_on_both_prefixes(client):
    legacy = client.get("/inventory/products/999999")
    canonical = client.get("/api/v1/inventory/products/999999")
    assert legacy.status_code == canonical.status_code == 404
    assert "not found" in legacy.json()["detail"]


def test_login_available_on_both_prefixes(client, test_users):
    form = {
        "username": "user@example.com",
        "password": test_users["active_raw_password"],
    }
    legacy = client.post("/auth/login", data=form)
    canonical = client.post("/api/v1/auth/login", data=form)
    assert legacy.status_code == canonical.status_code == 200
    assert legacy.json()["token_type"] == canonical.json()["token_type"] == "bearer"


def test_telemetry_ingest_on_both_prefixes(client):
    payload = {
        "events": [
            {
                "eventId": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": "sess_compat",
                "userId": None,
                "event_type": "frontend_error_captured",
                "schemaVersion": "1.0.0",
                "requestId": "req_compat",
                "properties": {"errorName": "TypeError"},
            }
        ]
    }
    for path in ("/telemetry/events", "/api/v1/telemetry/events"):
        response = client.post(path, json=payload)
        assert response.status_code == 200
        assert response.json() == {"received": 1}


def test_csv_analysis_and_export_on_both_prefixes(client):
    csv_body = (
        "title,description,category,status,origin,branch,satisfaction_index\n"
        "Late parcel,Delivery delayed,last_mile,open,customer,central,3\n"
    )
    for prefix in ("/api/incidents", "/api/v1/incidents"):
        missing_export = client.get(f"{prefix}/results/export")
        assert missing_export.status_code in (200, 404)

        analyzed = client.post(
            f"{prefix}/analyze",
            files={"file": ("incidents.csv", csv_body, "text/csv")},
        )
        assert analyzed.status_code == 200
        assert "metrics" in analyzed.json()

        exported = client.get(f"{prefix}/results/export")
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith("text/csv")
        assert "Metric,Value" in exported.text

        bad = client.post(
            f"{prefix}/analyze", files={"file": ("notes.txt", "x", "text/plain")}
        )
        assert bad.status_code == 400
