"""Shared pytest fixtures, mock upstream API transport, and OAuth JWT helpers for TrackFlow MCP Server."""

from datetime import datetime, timezone
import json
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from trackflow_server.app import set_upstream_client
from trackflow_server.clients.upstream_client import UpstreamClient
from trackflow_server.logging.audit import get_audit_logger
from trackflow_server.models.schemas import ALLOWED_LIFECYCLE_TRANSITIONS
from trackflow_server.testing.token_helper import (
    ALL_SCOPES,
    DEFAULT_AUDIENCE,
    DEFAULT_ISSUER,
    DEFAULT_JWT_SECRET,
    create_access_token,
)


class MockUpstreamBackend:
    """In-memory stateful mock of TrackFlow's `/api/incidents` and `/api/v1/inventory` endpoints."""

    def __init__(self) -> None:
        self.incidents: Dict[str, Dict[str, Any]] = {
            "INC-001": {
                "id": "INC-001",
                "title": "Delayed pallet shipment to Zaragoza",
                "description": "Pallet delayed at regional hub due to weather.",
                "status": "open",
                "category": "warehouse",
                "origin": "internal",
                "branch": "zaragoza",
                "created_at": "2026-11-17T09:00:00+00:00",
                "updated_at": "2026-11-18T10:30:00+00:00",
            },
            "INC-002": {
                "id": "INC-002",
                "title": "Damaged outer carton on arrival",
                "description": "Carton crushed during last-mile transit in Madrid.",
                "status": "in_progress",
                "category": "damage",
                "origin": "customer",
                "branch": "madrid",
                "created_at": "2026-11-16T08:00:00+00:00",
                "updated_at": "2026-11-17T14:20:00+00:00",
            },
            "INC-003": {
                "id": "INC-003",
                "title": "Duplicate billing invoice inquiry",
                "description": "Resolved duplicate billing entry for partner.",
                "status": "resolved",
                "category": "billing",
                "origin": "partner",
                "branch": "central",
                "created_at": "2026-11-15T10:00:00+00:00",
                "updated_at": "2026-11-16T12:00:00+00:00",
            },
            "INC-004": {
                "id": "INC-004",
                "title": "False alarm sensor notification",
                "description": "Discarded false alarm from warehouse door sensor.",
                "status": "discarded",
                "category": "system",
                "origin": "warehouse",
                "branch": "valencia",
                "created_at": "2026-11-14T11:00:00+00:00",
                "updated_at": "2026-11-14T11:30:00+00:00",
            },
        }
        self.products: Dict[int, Dict[str, Any]] = {
            1: {
                "id": 1,
                "sku": "TF-001",
                "name": "Industrial Thermal Shipping Label Roll",
                "description": "Thermal labels for warehouse barcode printers",
                "stock": 145,
                "min_threshold": 20,
                "is_low_stock": False,
                "warehouse_id": "zaragoza",
            },
            2: {
                "id": 2,
                "sku": "TF-002",
                "name": "Heavy-Duty Euro Pallet Stretch Wrap",
                "description": "High-tensile pallet stretch film roll",
                "stock": 8,
                "min_threshold": 15,
                "is_low_stock": True,
                "warehouse_id": "madrid",
            },
        }
        self.request_log: List[tuple[str, str, Optional[Dict[str, Any]]]] = []
        self.simulate_timeout: bool = False
        self.simulate_server_error: bool = False
        self._counter = 100

    async def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle incoming httpx.Request against the in-memory mock state."""
        parsed = urlparse(str(request.url))
        path = parsed.path
        query = parse_qs(parsed.query)
        body: Optional[Dict[str, Any]] = None
        if request.content:
            try:
                body = json.loads(request.content.decode("utf-8"))
            except Exception:
                body = None

        self.request_log.append((request.method, path, body))

        if self.simulate_timeout:
            raise httpx.ReadTimeout("Simulated upstream timeout", request=request)
        if self.simulate_server_error:
            return httpx.Response(
                503, json={"detail": "Simulated upstream unavailable"}
            )

        # POST /api/incidents
        if request.method == "POST" and path == "/api/incidents":
            if not body:
                return httpx.Response(422, json={"detail": "Missing body"})
            self._counter += 1
            new_id = f"INC-{self._counter}"
            now_iso = datetime.now(timezone.utc).isoformat()
            created = {
                "id": new_id,
                "title": body["title"],
                "description": body["description"],
                "status": "open",
                "category": body["category"],
                "origin": body["origin"],
                "branch": body.get("branch", "central"),
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            self.incidents[new_id] = created
            return httpx.Response(201, json=created)

        # GET /api/incidents
        if request.method == "GET" and path == "/api/incidents":
            items = list(self.incidents.values())
            for field_name in ("status", "category", "origin", "branch"):
                if field_name in query and query[field_name]:
                    expected = query[field_name][0].lower()
                    items = [
                        inc
                        for inc in items
                        if str(inc.get(field_name, "")).lower() == expected
                    ]
            return httpx.Response(200, json=items)

        # PATCH /api/incidents/{id}/status
        if (
            request.method == "PATCH"
            and path.startswith("/api/incidents/")
            and path.endswith("/status")
        ):
            parts = path.strip("/").split("/")
            inc_id = parts[2]
            inc = self.incidents.get(inc_id)
            if not inc:
                return httpx.Response(
                    404, json={"detail": f"Incident with ID '{inc_id}' was not found."}
                )
            target_status = (body or {}).get("status", "")
            current_status = inc["status"]
            allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(current_status, set())
            if target_status not in allowed:
                return httpx.Response(
                    400,
                    json={
                        "detail": (
                            f"Cannot transition incident status from '{current_status}' "
                            f"to '{target_status}'."
                        )
                    },
                )
            inc["status"] = target_status
            inc["updated_at"] = datetime.now(timezone.utc).isoformat()
            return httpx.Response(200, json=inc)

        # GET /api/incidents/{id}
        if request.method == "GET" and path.startswith("/api/incidents/"):
            inc_id = path.strip("/").split("/")[-1]
            inc = self.incidents.get(inc_id)
            if not inc:
                for candidate in self.incidents.values():
                    if candidate["id"].lower() == inc_id.lower():
                        inc = candidate
                        break
            if not inc:
                return httpx.Response(
                    404, json={"detail": f"Incident with ID '{inc_id}' was not found."}
                )
            return httpx.Response(200, json=inc)

        # GET /api/v1/inventory/products/{id}
        if request.method == "GET" and path.startswith("/api/v1/inventory/products/"):
            pid_str = path.strip("/").split("/")[-1]
            try:
                pid = int(pid_str)
            except ValueError:
                return httpx.Response(404, json={"detail": "Not found"})
            product = self.products.get(pid)
            if not product:
                return httpx.Response(404, json={"detail": "Product not found"})
            return httpx.Response(200, json=product)

        # GET /api/v1/inventory/products
        if request.method == "GET" and path == "/api/v1/inventory/products":
            return httpx.Response(200, json=list(self.products.values()))

        return httpx.Response(404, json={"detail": f"Unhandled route {path}"})


@pytest.fixture(autouse=True)
def reset_audit_and_upstream(mock_upstream_backend: MockUpstreamBackend) -> Any:
    """Automatically wire a fresh MockUpstreamBackend and clear audit logs before each test."""
    get_audit_logger().clear()
    transport = httpx.MockTransport(mock_upstream_backend.handle_request)
    client = UpstreamClient(
        base_url="http://trackflow-upstream.test",
        transport=transport,
    )
    set_upstream_client(client)
    yield
    set_upstream_client(None)
    get_audit_logger().clear()


@pytest.fixture
def mock_upstream_backend() -> MockUpstreamBackend:
    """Provide an isolated MockUpstreamBackend instance per test."""
    return MockUpstreamBackend()


@pytest.fixture
def upstream_client(mock_upstream_backend: MockUpstreamBackend) -> UpstreamClient:
    """Provide an UpstreamClient connected to the MockUpstreamBackend."""
    transport = httpx.MockTransport(mock_upstream_backend.handle_request)
    return UpstreamClient(
        base_url="http://trackflow-upstream.test",
        transport=transport,
    )


@pytest.fixture
def token_factory() -> Callable[..., str]:
    """Provide a helper factory for minting test OAuth 2.1 Bearer JWTs."""
    return create_access_token


__all__ = [
    "ALL_SCOPES",
    "DEFAULT_AUDIENCE",
    "DEFAULT_ISSUER",
    "DEFAULT_JWT_SECRET",
    "MockUpstreamBackend",
    "create_access_token",
    "mock_upstream_backend",
    "reset_audit_and_upstream",
    "token_factory",
    "upstream_client",
]
