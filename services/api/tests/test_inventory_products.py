import pytest
from sqlmodel import SQLModel, create_engine, Session
from fastapi.testclient import TestClient

from main import app
from infrastructure.database import engine, init_db, get_db
from infrastructure.adapters.security_adapter import JwtSecurityAdapter
import models  # noqa: F401


@pytest.fixture(autouse=True)
def setup_inventory_db():
    """Initializes tables on default test engine for inventory tests."""
    init_db(engine)
    yield


def get_auth_headers(test_users=None):
    if test_users:
        token = test_users["active_token"]
    else:
        security = JwtSecurityAdapter()
        token = security.create_access_token(subject="usr-uuid-1001")
    return {"Authorization": f"Bearer {token}"}


def test_get_products_empty(client):
    response = client.get("/inventory/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_product_requires_auth(client):
    payload = {
        "sku": "SKU-TEST-101",
        "name": "Test Box",
        "warehouse_id": "wh-la",
        "low_stock_threshold": 10
    }
    response = client.post("/inventory/products", json=payload)
    assert response.status_code == 401


def test_create_product_success(client, test_users):
    headers = get_auth_headers(test_users)
    payload = {
        "sku": "SKU-LA-1001",
        "name": "Standard LA Pallet",
        "warehouse_id": "wh-la",
        "low_stock_threshold": 20
    }
    response = client.post("/inventory/products", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "SKU-LA-1001"
    assert data["name"] == "Standard LA Pallet"
    assert data["warehouse_id"] == "wh-la"
    assert data["low_stock_threshold"] == 20
    assert data["current_stock"] == 0
    assert "id" in data


def test_get_product_by_id(client, test_users):
    headers = get_auth_headers(test_users)
    payload = {
        "sku": "SKU-ZGZ-2002",
        "name": "Zaragoza Parcel Container",
        "warehouse_id": "wh-zgz",
        "low_stock_threshold": 15
    }
    create_res = client.post("/inventory/products", json=payload, headers=headers)
    assert create_res.status_code == 201
    product_id = create_res.json()["id"]

    get_res = client.get(f"/inventory/products/{product_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == product_id
    assert data["sku"] == "SKU-ZGZ-2002"
    assert data["current_stock"] == 0


def test_get_product_not_found(client):
    response = client.get("/inventory/products/999999")
    assert response.status_code == 404


def test_create_duplicate_sku_rejection(client, test_users):
    headers = get_auth_headers(test_users)
    payload = {
        "sku": "SKU-DUP-3003",
        "name": "Duplicate SKU Test Item",
        "warehouse_id": "wh-la",
        "low_stock_threshold": 5
    }
    first_res = client.post("/inventory/products", json=payload, headers=headers)
    assert first_res.status_code == 201

    second_res = client.post("/inventory/products", json=payload, headers=headers)
    assert second_res.status_code == 400
    assert "already exists" in second_res.json()["detail"]
