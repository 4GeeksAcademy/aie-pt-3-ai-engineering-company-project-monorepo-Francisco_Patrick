"""Resilient async HTTP client for upstream TrackFlow Incidents and Inventory APIs."""

import os
import re
from typing import Any, Dict, List, Optional

import httpx

from trackflow_server.models.errors import (
    LifecycleTransitionDisallowedError,
    ResourceNotFoundError,
    ToolValidationError,
    TrackFlowMcpError,
    UpstreamUnavailableError,
)
from trackflow_server.models.schemas import (
    CreateIncidentInput,
    IncidentTicketModel,
    InventoryProductModel,
    validate_lifecycle_transition,
)

DEFAULT_UPSTREAM_TIMEOUT_SECONDS = 4.0
MAX_RETURNED_RECORDS = 20


class UpstreamClient:
    """Async HTTP client communicating with TrackFlow `/api/incidents` and `/api/v1/inventory`."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: float = DEFAULT_UPSTREAM_TIMEOUT_SECONDS,
        api_token: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        resolved_url = (
            base_url
            or os.environ.get("TRACKFLOW_API_BASE_URL")
            or "http://127.0.0.1:8000"
        )
        self._base_url = resolved_url.strip().rstrip("/")
        if timeout_seconds <= 0.0 or timeout_seconds > 4.0:
            timeout_seconds = min(max(timeout_seconds, 0.1), 4.0)
        self._timeout_seconds = float(timeout_seconds)
        self._api_token = (
            api_token
            if api_token is not None
            else os.environ.get("TRACKFLOW_INTERNAL_API_TOKEN")
        )
        self._external_client = http_client
        self._transport = transport

    @property
    def base_url(self) -> str:
        """Return the upstream API base URL."""
        return self._base_url

    @property
    def timeout_seconds(self) -> float:
        """Return the configured hard timeout in seconds (<= 4.0s)."""
        return self._timeout_seconds

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Execute an HTTP request with bounded timeout and map transport errors."""
        url = f"{self._base_url}{path}"
        headers = self._build_headers()
        timeout = httpx.Timeout(self._timeout_seconds)

        try:
            if self._external_client is not None:
                response = await self._external_client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    timeout=timeout,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_body,
                        headers=headers,
                    )
        except httpx.TimeoutException as exc:
            raise UpstreamUnavailableError(
                f"Upstream request '{method} {path}' timed out after {self._timeout_seconds:.1f}s.",
                details={"method": method, "path": path, "reason": "timeout"},
            ) from exc
        except httpx.RequestError as exc:
            raise UpstreamUnavailableError(
                f"Upstream service unreachable during '{method} {path}'.",
                details={"method": method, "path": path, "reason": "connection_error"},
            ) from exc

        if response.status_code >= 500:
            raise UpstreamUnavailableError(
                f"Upstream service returned HTTP {response.status_code} for '{method} {path}'.",
                details={
                    "method": method,
                    "path": path,
                    "http_status": response.status_code,
                },
            )
        return response

    @staticmethod
    def _parse_incident(raw: Dict[str, Any]) -> IncidentTicketModel:
        """Normalize raw upstream incident payload into IncidentTicketModel."""
        return IncidentTicketModel(
            id=str(raw.get("id") or raw.get("legacy_id") or ""),
            title=str(raw.get("title") or ""),
            description=str(raw.get("description") or ""),
            status=str(raw.get("status") or "open"),
            category=str(raw.get("category") or "warehouse"),
            origin=str(raw.get("origin") or "customer"),
            branch=str(raw.get("branch") or "central"),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
        )

    @staticmethod
    def _parse_inventory_product(raw: Dict[str, Any]) -> InventoryProductModel:
        """Normalize raw upstream product payload into InventoryProductModel."""
        pid = int(raw.get("id") or 0)
        sku = str(raw.get("sku") or "")
        name = str(raw.get("name") or "")
        warehouse_id = str(raw.get("warehouse_id") or "central")
        stock = int(
            raw["stock"]
            if "stock" in raw and raw["stock"] is not None
            else raw.get("current_stock", 0)
        )
        min_threshold = int(
            raw["min_threshold"]
            if "min_threshold" in raw and raw["min_threshold"] is not None
            else raw.get("low_stock_threshold", 10)
        )
        is_low_stock = bool(
            raw["is_low_stock"]
            if "is_low_stock" in raw and raw["is_low_stock"] is not None
            else (stock <= min_threshold)
        )
        description = str(
            raw.get("description") or f"{name} (Warehouse: {warehouse_id})"
        )
        return InventoryProductModel(
            id=pid,
            sku=sku,
            name=name,
            description=description,
            stock=max(0, stock),
            min_threshold=max(0, min_threshold),
            is_low_stock=is_low_stock,
            warehouse_id=warehouse_id,
        )

    async def create_incident(
        self, payload: CreateIncidentInput
    ) -> IncidentTicketModel:
        """Create a new incident via `POST /api/incidents`."""
        body = {
            "title": payload.title,
            "description": payload.description,
            "category": payload.category.value,
            "origin": payload.origin.value,
            "branch": payload.branch.value,
        }
        response = await self._request("POST", "/api/incidents", json_body=body)
        if response.status_code == 422 or response.status_code == 400:
            detail = self._extract_error_detail(response)
            raise ToolValidationError(
                f"Upstream incident creation validation failed: {detail}"
            )
        if response.status_code not in (200, 201):
            raise UpstreamUnavailableError(
                f"Unexpected status {response.status_code} from POST /api/incidents."
            )
        return self._parse_incident(response.json())

    async def get_incident(self, ticket_id: str) -> IncidentTicketModel:
        """Retrieve a single incident by ID via `GET /api/incidents/{id}`."""
        cleaned_id = ticket_id.strip()
        response = await self._request("GET", f"/api/incidents/{cleaned_id}")
        if response.status_code == 404:
            raise ResourceNotFoundError(
                f"Incident with ID '{cleaned_id}' was not found.",
                details={"ticket_id": cleaned_id},
            )
        if response.status_code != 200:
            raise UpstreamUnavailableError(
                f"Unexpected status {response.status_code} from GET /api/incidents/{cleaned_id}."
            )
        return self._parse_incident(response.json())

    async def list_incidents(
        self,
        *,
        status: Optional[str] = None,
        category: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> List[IncidentTicketModel]:
        """List incidents matching optional filters via `GET /api/incidents`."""
        params: Dict[str, str] = {}
        if status:
            params["status"] = status.strip().lower()
        if category:
            params["category"] = category.strip().lower()
        if origin:
            params["origin"] = origin.strip().lower()
        if branch:
            params["branch"] = branch.strip().lower()

        response = await self._request("GET", "/api/incidents", params=params or None)
        if response.status_code != 200:
            raise UpstreamUnavailableError(
                f"Unexpected status {response.status_code} from GET /api/incidents."
            )
        data = response.json()
        if not isinstance(data, list):
            return []
        models = [self._parse_incident(item) for item in data if isinstance(item, dict)]
        models.sort(
            key=lambda r: (r.updated_at or "", r.created_at or "", r.id or ""),
            reverse=True,
        )
        return models

    async def transition_incident_status(
        self,
        ticket_id: str,
        target_status: str,
    ) -> IncidentTicketModel:
        """Transition an incident's lifecycle status strictly via `PATCH /api/incidents/{id}/status`.

        Performs pre-flight state check when the current incident state is retrievable,
        and routes the transition exclusively through `PATCH /api/incidents/{id}/status` (FR-007).
        """
        cleaned_id = ticket_id.strip()
        normalized_target = target_status.strip().lower()

        # Retrieve current incident to validate lifecycle transition rules deterministically
        current_incident = await self.get_incident(cleaned_id)
        is_allowed, reason = validate_lifecycle_transition(
            current_incident.status, normalized_target
        )
        if not is_allowed:
            raise LifecycleTransitionDisallowedError(
                reason or f"Invalid lifecycle transition to '{normalized_target}'.",
                ticket_id=cleaned_id,
                current_status=current_incident.status,
                target_status=normalized_target,
            )

        response = await self._request(
            "PATCH",
            f"/api/incidents/{cleaned_id}/status",
            json_body={"status": normalized_target},
        )
        if response.status_code == 404:
            raise ResourceNotFoundError(
                f"Incident with ID '{cleaned_id}' was not found.",
                details={"ticket_id": cleaned_id},
            )
        if response.status_code in (400, 409, 422):
            detail = self._extract_error_detail(response)
            raise LifecycleTransitionDisallowedError(
                detail or f"Transition to '{normalized_target}' was rejected by lifecycle rules.",
                ticket_id=cleaned_id,
                current_status=current_incident.status,
                target_status=normalized_target,
            )
        if response.status_code != 200:
            raise UpstreamUnavailableError(
                f"Unexpected status {response.status_code} from PATCH /api/incidents/{cleaned_id}/status."
            )
        return self._parse_incident(response.json())

    async def query_inventory(
        self,
        *,
        sku: Optional[str] = None,
        product_id: Optional[int] = None,
        query: Optional[str] = None,
    ) -> List[InventoryProductModel]:
        """Execute strictly read-only inventory queries against `/api/v1/inventory/products`."""
        products: List[InventoryProductModel] = []

        if product_id is not None:
            response = await self._request(
                "GET", f"/api/v1/inventory/products/{int(product_id)}"
            )
            if response.status_code == 404:
                return []
            if response.status_code != 200:
                raise UpstreamUnavailableError(
                    f"Unexpected status {response.status_code} from GET /api/v1/inventory/products/{product_id}."
                )
            products = [self._parse_inventory_product(response.json())]
        else:
            params: Dict[str, str] = {}
            if sku:
                params["sku"] = sku.strip()
            if query:
                params["query"] = query.strip()

            response = await self._request(
                "GET", "/api/v1/inventory/products", params=params or None
            )
            if response.status_code == 404:
                return []
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, list):
                    products = [
                        self._parse_inventory_product(item)
                        for item in payload
                        if isinstance(item, dict)
                    ]
                elif isinstance(payload, dict) and "items" in payload:
                    products = [
                        self._parse_inventory_product(item)
                        for item in payload["items"]
                        if isinstance(item, dict)
                    ]
                elif isinstance(payload, dict) and "id" in payload and "sku" in payload:
                    products = [self._parse_inventory_product(payload)]
            elif response.status_code == 202:
                # Upstream FastAPI /api/v1/inventory/products returns 202 async task;
                # probe sequential product IDs via GET /api/v1/inventory/products/{id}
                products = await self._probe_products_by_id()
            else:
                raise UpstreamUnavailableError(
                    f"Unexpected status {response.status_code} from GET /api/v1/inventory/products."
                )

        # Apply client-side exact/substring filtering for SKU and free-text query
        if sku:
            target_sku = sku.strip().upper()
            exact = [p for p in products if p.sku.upper() == target_sku]
            products = exact if exact else [p for p in products if target_sku in p.sku.upper()]

        if query:
            raw_q = query.strip().lower()
            if raw_q:
                direct = [
                    p
                    for p in products
                    if raw_q in p.sku.lower()
                    or raw_q in p.name.lower()
                    or raw_q in p.description.lower()
                    or raw_q in p.warehouse_id.lower()
                ]
                if direct:
                    products = direct
                else:
                    tokens = [
                        tok
                        for tok in re.findall(r"[a-z0-9_-]+", raw_q)
                        if len(tok) >= 2
                    ]
                    if tokens:
                        products = [
                            p
                            for p in products
                            if any(
                                tok in p.sku.lower()
                                or tok in p.name.lower()
                                or tok in p.description.lower()
                                or tok in p.warehouse_id.lower()
                                for tok in tokens
                            )
                        ]
                    else:
                        products = []

        products.sort(key=lambda p: (p.id, p.sku))
        return products[:MAX_RETURNED_RECORDS]

    async def _probe_products_by_id(self, max_id: int = 25) -> List[InventoryProductModel]:
        """Read products via `GET /api/v1/inventory/products/{id}` when list endpoint is async-queued."""
        found: List[InventoryProductModel] = []
        consecutive_misses = 0
        for pid in range(1, max_id + 1):
            resp = await self._request("GET", f"/api/v1/inventory/products/{pid}")
            if resp.status_code == 200:
                found.append(self._parse_inventory_product(resp.json()))
                consecutive_misses = 0
            elif resp.status_code == 404:
                consecutive_misses += 1
                if consecutive_misses >= 5 and found:
                    break
        return found

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        """Extract human-readable error message from an upstream HTTP error response."""
        try:
            body = response.json()
            if isinstance(body, dict):
                if "detail" in body:
                    return str(body["detail"])
                if "message" in body:
                    return str(body["message"])
        except Exception:
            pass
        return response.text or f"HTTP {response.status_code}"


__all__ = [
    "DEFAULT_UPSTREAM_TIMEOUT_SECONDS",
    "MAX_RETURNED_RECORDS",
    "UpstreamClient",
]
