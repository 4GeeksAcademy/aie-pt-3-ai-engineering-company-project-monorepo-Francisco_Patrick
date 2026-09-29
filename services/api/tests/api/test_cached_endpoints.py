import pytest
from fastapi.testclient import TestClient
from main import app
from infrastructure.cache import response_cache
from domain.models import User
from presentation.dependencies import get_current_user

client = TestClient(app)

mock_admin_user = User(
    id="admin-cached-test-uuid",
    email="admin_cached@trackflow.example",
    hashed_password="mock",
    is_active=True,
    role="admin",
    created_at="2026-09-29T10:00:00"
)


@pytest.fixture(autouse=True)
def setup_teardown_cache():
    response_cache.clear()
    app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    yield
    response_cache.clear()
    app.dependency_overrides.pop(get_current_user, None)


def test_incident_summary_caching_and_mutation_invalidation():
    # 1. Initial read should populate cache
    res1 = client.get("/api/incidents/summary")
    assert res1.status_code == 200
    initial_summary = res1.json()

    # Verify cache key exists
    assert response_cache.get("incident_summary:global") is not None

    # 2. Subsequent read returns cached result
    res2 = client.get("/api/incidents/summary")
    assert res2.status_code == 200
    assert res2.json() == initial_summary

    # 3. Create new incident to trigger invalidation
    new_inc = {
        "title": "Cache Invalidation Test Incident",
        "description": "Ensuring cache invalidation functions properly",
        "category": "warehouse",
        "origin": "internal",
        "branch": "los_angeles"
    }
    create_res = client.post("/api/incidents", json=new_inc)
    assert create_res.status_code == 201

    # Verify cache was invalidated
    assert response_cache.get("incident_summary:global") is None

    # 4. Next read should repopulate cache with incremented count
    res3 = client.get("/api/incidents/summary")
    assert res3.status_code == 200
    updated_summary = res3.json()
    assert updated_summary["total_incidents"] == initial_summary["total_incidents"] + 1
    assert response_cache.get("incident_summary:global") is not None


def test_suppliers_caching_and_mutation_invalidation():
    # 1. Create a supplier
    sup_payload = {
        "name": "Cache Test Supplier Corp",
        "country": "Germany",
        "categories": ["packaging"],
        "cost_per_kg": 14.50,
        "status": "active"
    }
    create_res = client.post("/suppliers", json=sup_payload)
    assert create_res.status_code == 201
    supplier_id = create_res.json()["id"]

    # 2. Query suppliers with filter
    res1 = client.get("/suppliers?country=Germany")
    assert res1.status_code == 200
    assert len(res1.json()) >= 1
    cache_key = "suppliers:country=Germany&category="
    assert response_cache.get(cache_key) is not None

    # 3. Query with different filter (parameter isolation)
    res_other = client.get("/suppliers?country=Japan")
    assert res_other.status_code == 200
    other_cache_key = "suppliers:country=Japan&category="
    assert response_cache.get(other_cache_key) is not None

    # 4. Update rate to trigger invalidation
    patch_res = client.patch(f"/suppliers/{supplier_id}/rate", json={"cost_per_kg": 19.99})
    assert patch_res.status_code == 200

    # Verify both supplier cache keys were purged
    assert response_cache.get(cache_key) is None
    assert response_cache.get(other_cache_key) is None


def test_inventory_products_caching_and_inbound_invalidation():
    # 1. Query products list to populate cache
    res1 = client.get("/inventory/products")
    assert res1.status_code == 200
    initial_products = res1.json()
    assert response_cache.get("inventory_products:all") is not None

    # 2. Register inbound delivery to trigger invalidation
    if len(initial_products) > 0:
        target_sku_id = initial_products[0]["id"]
        inbound_payload = {
            "sku_id": target_sku_id,
            "warehouse_id": "wh-la",
            "quantity": 25
        }
        inbound_res = client.post("/inventory/orders/inbound", json=inbound_payload)
        assert inbound_res.status_code == 201

        # Verify inventory cache was cleared
        assert response_cache.get("inventory_products:all") is None

        # 3. Subsequent list query returns updated stock
        res2 = client.get("/inventory/products")
        assert res2.status_code == 200
        assert response_cache.get("inventory_products:all") is not None
