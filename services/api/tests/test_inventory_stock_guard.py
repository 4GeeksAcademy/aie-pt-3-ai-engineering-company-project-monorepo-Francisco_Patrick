import pytest
from infrastructure.adapters.security_adapter import JwtSecurityAdapter


def get_auth_headers(test_users=None):
    if test_users:
        token = test_users["active_token"]
    else:
        security = JwtSecurityAdapter()
        token = security.create_access_token(subject="usr-uuid-1001")
    return {"Authorization": f"Bearer {token}"}


def create_test_product(client, test_users, sku="SKU-GUARD-100", warehouse="wh-la"):
    headers = get_auth_headers(test_users)
    payload = {
        "sku": sku,
        "name": f"Stock Guard Item {sku}",
        "warehouse_id": warehouse,
        "low_stock_threshold": 10
    }
    response = client.post("/inventory/products", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_outbound_exceeding_stock_rejected(client, test_users):
    """Verifies that an outbound request exceeding available stock is rejected with HTTP 400."""
    product = create_test_product(client, test_users, sku="SKU-GUARD-001", warehouse="wh-la")
    product_id = product["id"]
    headers = get_auth_headers(test_users)

    # Inbound 10 units
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": product_id, "warehouse_id": "wh-la", "quantity": 10},
        headers=headers
    )

    # Request outbound 15 units (exceeding available 10)
    outbound_payload = {
        "sku_id": product_id,
        "warehouse_id": "wh-la",
        "quantity": 15
    }
    res = client.post("/inventory/orders/outbound", json=outbound_payload, headers=headers)
    assert res.status_code == 400
    assert "Insufficient stock" in res.json()["detail"]

    # Verify stock remains unchanged at 10
    prod_res = client.get(f"/inventory/products/{product_id}")
    assert prod_res.status_code == 200
    assert prod_res.json()["current_stock"] == 10


def test_multi_warehouse_stock_isolation(client, test_users):
    """Verifies that stock calculations are strictly isolated by warehouse partition."""
    product = create_test_product(client, test_users, sku="SKU-GUARD-002", warehouse="wh-la")
    product_id = product["id"]
    headers = get_auth_headers(test_users)

    # Inbound 100 units to wh-la
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": product_id, "warehouse_id": "wh-la", "quantity": 100},
        headers=headers
    )

    # Attempt outbound 10 units from wh-zgz (where stock is 0)
    outbound_zgz_payload = {
        "sku_id": product_id,
        "warehouse_id": "wh-zgz",
        "quantity": 10
    }
    res_zgz = client.post("/inventory/orders/outbound", json=outbound_zgz_payload, headers=headers)
    assert res_zgz.status_code == 400
    assert "Insufficient stock" in res_zgz.json()["detail"]

    # Now add stock to wh-zgz (20 units)
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": product_id, "warehouse_id": "wh-zgz", "quantity": 20},
        headers=headers
    )

    # Outbound 10 units from wh-zgz should now succeed
    res_zgz_ok = client.post("/inventory/orders/outbound", json=outbound_zgz_payload, headers=headers)
    assert res_zgz_ok.status_code == 201


def test_outbound_zero_stock_rejected(client, test_users):
    """Verifies outbound request on zero initial stock product is rejected."""
    product = create_test_product(client, test_users, sku="SKU-GUARD-003", warehouse="wh-la")
    product_id = product["id"]
    headers = get_auth_headers(test_users)

    outbound_payload = {
        "sku_id": product_id,
        "warehouse_id": "wh-la",
        "quantity": 5
    }
    res = client.post("/inventory/orders/outbound", json=outbound_payload, headers=headers)
    assert res.status_code == 400
    assert "Insufficient stock" in res.json()["detail"]
