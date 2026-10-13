import time
import pytest
from infrastructure.cache import ResponseCache


def test_cache_set_and_get_hit() -> None:
    cache = ResponseCache()
    cache.set("test_key", {"data": 123}, ttl_seconds=60)
    result = cache.get("test_key")
    assert result == {"data": 123}


def test_cache_get_miss() -> None:
    cache = ResponseCache()
    assert cache.get("non_existent_key") is None


def test_cache_ttl_expiration() -> None:
    cache = ResponseCache()
    cache.set("ephemeral_key", "ephemeral_value", ttl_seconds=1)
    assert cache.get("ephemeral_key") == "ephemeral_value"
    # Sleep slightly longer than 1 second to verify TTL eviction
    time.sleep(1.1)
    assert cache.get("ephemeral_key") is None


def test_cache_invalidate_single_key() -> None:
    cache = ResponseCache()
    cache.set("key_1", "val_1", ttl_seconds=60)
    cache.set("key_2", "val_2", ttl_seconds=60)

    assert cache.invalidate("key_1") is True
    assert cache.get("key_1") is None
    assert cache.get("key_2") == "val_2"
    assert cache.invalidate("key_1") is False


def test_cache_invalidate_prefix() -> None:
    cache = ResponseCache()
    cache.set("suppliers:all", [{"id": 1}], ttl_seconds=60)
    cache.set("suppliers:country=USA", [{"id": 1}], ttl_seconds=60)
    cache.set("suppliers:country=Spain", [{"id": 2}], ttl_seconds=60)
    cache.set("incident_summary:global", {"total": 5}, ttl_seconds=60)
    cache.set("inventory_products:wh-la", [{"sku": "SKU-1"}], ttl_seconds=60)

    # Invalidate suppliers namespace
    invalidated_count = cache.invalidate_prefix("suppliers:")
    assert invalidated_count == 3

    assert cache.get("suppliers:all") is None
    assert cache.get("suppliers:country=USA") is None
    assert cache.get("suppliers:country=Spain") is None
    # Other namespaces remain untouched
    assert cache.get("incident_summary:global") == {"total": 5}
    assert cache.get("inventory_products:wh-la") == [{"sku": "SKU-1"}]


def test_cache_clear() -> None:
    cache = ResponseCache()
    cache.set("k1", "v1", ttl_seconds=60)
    cache.set("k2", "v2", ttl_seconds=60)
    assert cache.size() == 2

    cache.clear()
    assert cache.size() == 0
    assert cache.get("k1") is None
    assert cache.get("k2") is None


def test_cache_size_with_expired_entries() -> None:
    cache = ResponseCache()
    cache.set("live_key", "live_val", ttl_seconds=60)
    cache.set("expiring_key", "expiring_val", ttl_seconds=1)
    assert cache.size() == 2

    time.sleep(1.1)
    assert cache.size() == 1
    assert cache.get("live_key") == "live_val"
