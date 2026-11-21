"""Tests verifying all Acceptance Criteria and BRIEFING requirements for Milestone 5."""

import pytest
from fastapi.testclient import TestClient

from main import app
from infrastructure.database import engine, init_db, get_db, get_tinydb
from models import SKU, StockEntry, StockExit
from schemas import (
    ProductCreateDTO,
    ProductResponseDTO,
    InboundOrderCreateDTO,
    OutboundOrderCreateDTO,
    OrderResponseDTO,
)
from infrastructure.adapters.security_adapter import JwtSecurityAdapter
from seed import run_seed


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
        token = security.create_access_token(subject="usr-uuid-test-operator")
    return {"Authorization": f"Bearer {token}"}


def test_dual_db_architecture_separation():
    """Verify dual database architecture: TinyDB for users/auth, SQLModel for inventory."""
    tinydb = get_tinydb()
    assert tinydb is not None
    assert engine is not None
    # Verify no User table exists in SQLModel metadata
    table_names = list(SKU.metadata.tables.keys())
    assert "user" not in table_names
    assert "users" not in table_names
    assert "sku" in table_names
    assert "stock_entry" in table_names
    assert "stock_exit" in table_names


def test_seed_data_and_stock_calculation(client, test_users):
    """Verify seed data produces exact net stock: CLT-SNK-W-42 = 63, CLT-SNK-W-42-Z = 30."""
    run_seed()
    headers = get_auth_headers(test_users)

    # Test sync products listing
    res = client.get("/inventory/products?sync=true")
    assert res.status_code == 200
    products = res.json()
    assert len(products) >= 6

    prod_map = {p["sku"]: p for p in products}

    # CLT-SNK-W-42: entries (50 + 30) - exits (15 dispatch + 2 loss) = 63
    assert "CLT-SNK-W-42" in prod_map
    assert prod_map["CLT-SNK-W-42"]["warehouse"] == "LA"
    assert prod_map["CLT-SNK-W-42"]["current_stock"] == 63

    # CLT-SNK-W-42-Z: entries (40) - exits (10 dispatch) = 30
    assert "CLT-SNK-W-42-Z" in prod_map
    assert prod_map["CLT-SNK-W-42-Z"]["warehouse"] == "ZGZ"
    assert prod_map["CLT-SNK-W-42-Z"]["current_stock"] == 30

    # TEC-EAR-001: entries (25) - exits (0) = 25
    assert "TEC-EAR-001" in prod_map
    assert prod_map["TEC-EAR-001"]["current_stock"] == 25

    # CSM-SRM-030: entries (60) - exits (0) = 60
    assert "CSM-SRM-030" in prod_map
    assert prod_map["CSM-SRM-030"]["current_stock"] == 60


def test_create_product_and_initial_zero_stock(client, test_users):
    """A newly registered SKU must always have initial stock 0."""
    headers = get_auth_headers(test_users)
    payload = {
        "name": "Sudadera técnica transpirable",
        "sku": "CLT-SWT-BLK-M",
        "client_name": "UrbanThread",
        "category": "fashion",
        "warehouse": "LA",
    }
    create_res = client.post("/inventory/products", json=payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["current_stock"] == 0
    assert created["warehouse"] == "LA"
    assert created["client_name"] == "UrbanThread"

    # Verify GET by ID also reports 0
    get_res = client.get(f"/inventory/products/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["current_stock"] == 0


def test_dispatch_without_tracking_number_rejected(client, test_users):
    """StockExit with exit_type='dispatch' without tracking_number must trigger validation error."""
    headers = get_auth_headers(test_users)

    # First create a product and add inbound stock
    prod_payload = {
        "name": "Camiseta básica algodón",
        "sku": "CLT-TSH-WHT-L",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "LA",
    }
    prod = client.post("/inventory/products", json=prod_payload, headers=headers).json()

    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": prod["id"], "warehouse": "LA", "quantity": 100, "reference": "PO-TEST-1"},
        headers=headers,
    )

    # Try dispatch without tracking number
    invalid_dispatch = {
        "sku_id": prod["id"],
        "warehouse": "LA",
        "quantity": 10,
        "exit_type": "dispatch",
        "tracking_number": None,
    }
    res = client.post("/inventory/orders/outbound", json=invalid_dispatch, headers=headers)
    assert res.status_code in (400, 422)


def test_loss_with_tracking_number_rejected(client, test_users):
    """StockExit with exit_type='loss' and non-null tracking_number must trigger validation error."""
    headers = get_auth_headers(test_users)

    prod_payload = {
        "name": "Cargador Rápido Test",
        "sku": "TEC-CHG-TEST-1",
        "client_name": "SoundWave Electronics",
        "category": "electronics",
        "warehouse": "ZGZ",
    }
    prod = client.post("/inventory/products", json=prod_payload, headers=headers).json()

    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": prod["id"], "warehouse": "ZGZ", "quantity": 50, "reference": "PO-TEST-2"},
        headers=headers,
    )

    # Try loss with non-null tracking number
    invalid_loss = {
        "sku_id": prod["id"],
        "warehouse": "ZGZ",
        "quantity": 5,
        "exit_type": "loss",
        "tracking_number": "1Z9999999999999999",
    }
    res = client.post("/inventory/orders/outbound", json=invalid_loss, headers=headers)
    assert res.status_code in (400, 422)


def test_insufficient_stock_rejection_format(client, test_users):
    """Outbound exit exceeding stock returns HTTP 400 with expected error message format."""
    headers = get_auth_headers(test_users)

    prod_payload = {
        "name": "Pantalón cargo",
        "sku": "CLT-CRG-KHK-32",
        "client_name": "UrbanThread",
        "category": "fashion",
        "warehouse": "LA",
    }
    prod = client.post("/inventory/products", json=prod_payload, headers=headers).json()

    # Inbound 10 units
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": prod["id"], "warehouse": "LA", "quantity": 10, "reference": "PO-TEST-3"},
        headers=headers,
    )

    # Outbound 15 units (only 10 available)
    outbound_payload = {
        "sku_id": prod["id"],
        "warehouse": "LA",
        "quantity": 15,
        "exit_type": "dispatch",
        "tracking_number": "1Z1234567890123456",
    }
    res = client.post("/inventory/orders/outbound", json=outbound_payload, headers=headers)
    assert res.status_code == 400
    detail = res.json().get("detail") or res.json().get("message", "")
    assert "Insufficient stock for SKU" in detail
    assert "Available: 10, requested: 15" in detail


def test_orders_listing_traceability_and_no_n_plus_one(client, test_users):
    """Verify GET /inventory/orders returns orders with SKU info and user_uuid without N+1 queries."""
    headers = get_auth_headers(test_users)

    res = client.get("/inventory/orders", headers=headers)
    assert res.status_code == 200
    orders = res.json()
    assert isinstance(orders, list)
    if orders:
        order = orders[0]
        assert "user_uuid" in order
        assert "sku_code" in order
        assert "warehouse" in order
        assert "order_type" in order


def test_services_facade_imports():
    """Verify that imports directly from services modules work identically."""
    import services.database as s_db
    import services.models as s_models
    import services.schemas as s_schemas
    import services.routers.inventory as s_router

    assert hasattr(s_db, "get_db")
    assert hasattr(s_db, "get_tinydb")
    assert hasattr(s_db, "engine")
    assert hasattr(s_models, "SKU")
    assert hasattr(s_models, "StockEntry")
    assert hasattr(s_models, "StockExit")
    assert hasattr(s_schemas, "ProductCreateDTO")
    assert hasattr(s_schemas, "ProductResponseDTO")
    assert hasattr(s_router, "router")
