import pytest
from infrastructure.adapters.security_adapter import JwtSecurityAdapter


def get_auth_headers(test_users=None):
    if test_users:
        token = test_users["active_token"]
    else:
        security = JwtSecurityAdapter()
        token = security.create_access_token(subject="usr-uuid-1001")
    return {"Authorization": f"Bearer {token}"}


def create_test_product(client, test_users, sku="SKU-ORD-100", warehouse="wh-la"):
    headers = get_auth_headers(test_users)
    payload = {
        "sku": sku,
        "name": f"Test Item {sku}",
        "warehouse_id": warehouse,
        "low_stock_threshold": 10
    }
    response = client.post("/inventory/products", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_inbound_order_success(client, test_users):
    product = create_test_product(client, test_users, sku="SKU-IN-001", warehouse="wh-la")
    product_id = product["id"]
    headers = get_auth_headers(test_users)

    inbound_payload = {
        "sku_id": product_id,
        "warehouse_id": "wh-la",
        "quantity": 50
    }
    res = client.post("/inventory/orders/inbound", json=inbound_payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["order_type"] == "inbound"
    assert data["sku_id"] == product_id
    assert data["sku_code"] == "SKU-IN-001"
    assert data["quantity"] == 50
    assert data["user_uuid"] == test_users["active"].id

    # Verify updated stock on product endpoint
    prod_res = client.get(f"/inventory/products/{product_id}")
    assert prod_res.status_code == 200
    assert prod_res.json()["current_stock"] == 50


def test_outbound_order_success(client, test_users):
    product = create_test_product(client, test_users, sku="SKU-OUT-002", warehouse="wh-la")
    product_id = product["id"]
    headers = get_auth_headers(test_users)

    # Inbound 50
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": product_id, "warehouse_id": "wh-la", "quantity": 50},
        headers=headers
    )

    # Outbound 20
    outbound_payload = {
        "sku_id": product_id,
        "warehouse_id": "wh-la",
        "quantity": 20
    }
    out_res = client.post("/inventory/orders/outbound", json=outbound_payload, headers=headers)
    assert out_res.status_code == 201
    data = out_res.json()
    assert data["order_type"] == "outbound"
    assert data["quantity"] == 20

    # Dynamic stock: 50 - 20 = 30
    prod_res = client.get(f"/inventory/products/{product_id}")
    assert prod_res.status_code == 200
    assert prod_res.json()["current_stock"] == 30


def test_list_orders(client, test_users):
    product = create_test_product(client, test_users, sku="SKU-LIST-003", warehouse="wh-zgz")
    product_id = product["id"]
    headers = get_auth_headers(test_users)

    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": product_id, "warehouse_id": "wh-zgz", "quantity": 100},
        headers=headers
    )
    client.post(
        "/inventory/orders/outbound",
        json={"sku_id": product_id, "warehouse_id": "wh-zgz", "quantity": 30},
        headers=headers
    )

    res = client.get("/inventory/orders", headers=headers)
    assert res.status_code == 200
    orders = res.json()
    assert isinstance(orders, list)
    assert len(orders) >= 2

    # Check order fields
    first_order = orders[0]
    assert "id" in first_order
    assert "order_type" in first_order
    assert "sku_code" in first_order
    assert "user_uuid" in first_order


def test_create_order_nonexistent_sku_returns_404(client, test_users):
    headers = get_auth_headers(test_users)
    payload = {
        "sku_id": 999999,
        "warehouse_id": "wh-la",
        "quantity": 10
    }
    res = client.post("/inventory/orders/inbound", json=payload, headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_create_order_invalid_quantity_returns_422(client, test_users):
    headers = get_auth_headers(test_users)
    payload = {
        "sku_id": 1,
        "warehouse_id": "wh-la",
        "quantity": 0
    }
    res = client.post("/inventory/orders/inbound", json=payload, headers=headers)
    assert res.status_code in (400, 422)



def test_create_order_unauthenticated_returns_401(client):
    payload = {
        "sku_id": 1,
        "warehouse_id": "wh-la",
        "quantity": 10
    }
    res = client.post("/inventory/orders/inbound", json=payload)
    assert res.status_code == 401
