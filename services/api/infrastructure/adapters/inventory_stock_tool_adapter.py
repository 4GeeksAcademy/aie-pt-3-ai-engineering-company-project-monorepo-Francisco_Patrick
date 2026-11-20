"""Read-only Inventory Stock Query Tool adapter for the TrackFlow Support Agent.

Implements `InventoryStockToolPort` (FR-018, FR-019, FR-020, FR-021, FR-022):
- Reads live product stock projections (`id`, `sku`, `name`, `description`, `stock`,
  `min_threshold`, `is_low_stock`, `warehouse_id`) directly from TrackFlow's
  `InventoryService` (SQLModel `inventory.db`) or via optional HTTP transport
  (`GET /inventory/products/{id}`).
- Strictly read-only: exposes only `query_inventory` with zero mutation capabilities.
- Enforces an explicit numerical timeout (default `4.0` seconds) via `ThreadPoolExecutor` /
  `httpx.Timeout`.
- Caps returned records at 20 items while reporting `total_matched`.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import re
import time
from typing import Any, Callable, Dict, List, Optional

import httpx

from application.inventory.inventory_service import InventoryService
from domain.agent.entities import (
    InventoryRecordDTO,
    InventoryToolInput,
    InventoryToolOutput,
)
from domain.agent.ports import InventoryStockToolPort
from domain.common.exceptions import EntityNotFoundError
from domain.inventory.models import InventoryProduct
from domain.knowledge.entities import KnowledgeRuntimeConfig

DEFAULT_TOOL_TIMEOUT_SECONDS = 4.0
MAX_TOOL_RECORDS = 20

_SEARCH_STOPWORDS = {
    "how",
    "many",
    "units",
    "of",
    "sku",
    "are",
    "currently",
    "in",
    "stock",
    "what",
    "is",
    "the",
    "current",
    "inventory",
    "level",
    "availability",
    "available",
    "for",
    "product",
    "products",
    "warehouse",
    "do",
    "we",
    "have",
    "check",
    "status",
    "threshold",
    "low",
}


class InventoryStockQueryToolAdapter(InventoryStockToolPort):
    """Read-only adapter querying live warehouse stock from TrackFlow Inventory Manager."""

    def __init__(
        self,
        inventory_service: Optional[InventoryService] = None,
        inventory_service_factory: Optional[Callable[[], InventoryService]] = None,
        config: Optional[KnowledgeRuntimeConfig] = None,
        timeout_seconds: Optional[float] = None,
        api_base_url: Optional[str] = None,
        internal_api_token: Optional[str] = None,
        http_client: Optional[Any] = None,
    ) -> None:
        """Initialize the read-only Inventory Stock Query Tool adapter.

        Authentication mode:
        - In-process mode (default): Invokes `InventoryService` directly within the
          trusted backend boundary against `inventory.db`.
        - HTTP mode (when `api_base_url` / `AGENT_API_BASE_URL` is set and querying by
          `product_id`): Sends `GET` requests to `/inventory/products/{id}` with optional
          `Authorization: Bearer <token>` loaded from `AGENT_INTERNAL_API_TOKEN`.

        Args:
            inventory_service: Optional pre-wired InventoryService instance.
            inventory_service_factory: Optional factory returning an InventoryService.
            config: Optional KnowledgeRuntimeConfig instance.
            timeout_seconds: Optional numerical timeout override in seconds (defaults to 4.0s).
            api_base_url: Optional HTTP base URL override.
            internal_api_token: Optional bearer token loaded from environment config.
            http_client: Optional httpx-compatible client for testing HTTP transport.
        """
        self._config = config or KnowledgeRuntimeConfig.from_env()
        self._inventory_service = inventory_service
        self._inventory_service_factory = inventory_service_factory
        resolved_timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(self._config.agent_tool_timeout_seconds or DEFAULT_TOOL_TIMEOUT_SECONDS)
        )
        if resolved_timeout <= 0.0:
            raise ValueError("timeout_seconds must be strictly positive (> 0.0).")
        self._timeout_seconds = resolved_timeout
        self._api_base_url = (
            api_base_url.strip().rstrip("/")
            if api_base_url and api_base_url.strip()
            else self._config.agent_api_base_url
        )
        self._internal_api_token = (
            internal_api_token
            if internal_api_token is not None
            else self._config.agent_internal_api_token
        )
        self._http_client = http_client

    @property
    def timeout_seconds(self) -> float:
        """Return the configured numerical timeout in seconds."""
        return self._timeout_seconds

    @property
    def auth_mode(self) -> str:
        """Return documented authentication mode ('in_process', 'http_bearer', or 'http_unauthenticated')."""
        if self._api_base_url:
            return "http_bearer" if self._internal_api_token else "http_unauthenticated"
        return "in_process"

    def _resolve_service(self) -> InventoryService:
        """Resolve the in-process InventoryService collaborator."""
        if self._inventory_service is not None:
            return self._inventory_service
        if self._inventory_service_factory is not None:
            return self._inventory_service_factory()
        from infrastructure.persistence.sqlmodel.inventory_repository import (
            SQLModelInventoryRepository,
        )

        return InventoryService(inventory_repo=SQLModelInventoryRepository())

    @staticmethod
    def _product_to_dto(product: InventoryProduct | Dict[str, Any]) -> InventoryRecordDTO:
        """Convert a domain InventoryProduct or raw dict to an immutable InventoryRecordDTO."""
        if isinstance(product, dict):
            pid = int(product.get("id") or 0)
            sku_code = str(product.get("sku") or "")
            name = str(product.get("name") or "")
            warehouse_id = str(product.get("warehouse_id") or "central")
            stock = int(
                product.get("stock")
                if product.get("stock") is not None
                else product.get("current_stock", 0)
            )
            min_threshold = int(
                product.get("min_threshold")
                if product.get("min_threshold") is not None
                else product.get("low_stock_threshold", 10)
            )
            is_low = bool(
                product.get("is_low_stock")
                if product.get("is_low_stock") is not None
                else (stock <= min_threshold)
            )
            desc = str(
                product.get("description")
                or f"{name} (Warehouse: {warehouse_id})"
            )
            return InventoryRecordDTO(
                id=pid,
                sku=sku_code,
                name=name,
                description=desc,
                stock=stock,
                min_threshold=min_threshold,
                is_low_stock=is_low,
                warehouse_id=warehouse_id,
            )

        warehouse_id = str(getattr(product, "warehouse_id", "central") or "central")
        raw_desc = getattr(product, "description", None)
        description = (
            str(raw_desc)
            if raw_desc
            else f"{product.name} (Warehouse: {warehouse_id})"
        )
        return InventoryRecordDTO(
            id=int(product.id),
            sku=str(product.sku),
            name=str(product.name),
            description=description,
            stock=int(product.current_stock),
            min_threshold=int(product.low_stock_threshold),
            is_low_stock=bool(product.is_low_stock),
            warehouse_id=warehouse_id,
        )

    def _execute_http_product_by_id(self, product_id: int) -> List[InventoryRecordDTO]:
        """Execute read-only single product lookup over HTTP `GET /inventory/products/{id}`."""
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self._internal_api_token:
            headers["Authorization"] = f"Bearer {self._internal_api_token}"

        timeout = httpx.Timeout(self._timeout_seconds)
        base_url = self._api_base_url or "http://127.0.0.1:8000"

        if self._http_client is not None:
            client = self._http_client
            close_client = False
        else:
            client = httpx.Client(timeout=timeout)
            close_client = True

        try:
            resp = client.get(f"{base_url}/inventory/products/{product_id}", headers=headers)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            payload = resp.json()
            return [self._product_to_dto(payload)]
        finally:
            if close_client and hasattr(client, "close"):
                client.close()

    def _execute_lookup(self, tool_input: InventoryToolInput) -> List[InventoryRecordDTO]:
        """Execute read-only inventory lookup via `InventoryService` (or HTTP for single ID)."""
        if self._api_base_url and tool_input.product_id is not None:
            return self._execute_http_product_by_id(tool_input.product_id)

        service = self._resolve_service()

        if tool_input.product_id is not None:
            try:
                product = service.get_product_by_id(int(tool_input.product_id))
            except EntityNotFoundError:
                return []
            if product is None:
                return []
            dto = self._product_to_dto(product)
            if tool_input.low_stock_only and not dto.is_low_stock:
                return []
            return [dto]

        all_products = service.list_products()
        dtos = [self._product_to_dto(p) for p in all_products]

        if tool_input.sku:
            target_sku = tool_input.sku.strip().upper()
            exact_matches = [d for d in dtos if d.sku.upper() == target_sku]
            if exact_matches:
                dtos = exact_matches
            else:
                dtos = [d for d in dtos if target_sku in d.sku.upper()]

        if tool_input.search_query:
            raw_search = tool_input.search_query.strip().lower()
            if raw_search:
                # Direct substring match first
                direct = [
                    d
                    for d in dtos
                    if raw_search in d.sku.lower()
                    or raw_search in d.name.lower()
                    or raw_search in d.description.lower()
                    or raw_search in d.warehouse_id.lower()
                ]
                if direct:
                    dtos = direct
                else:
                    tokens = [
                        tok
                        for tok in re.findall(r"[a-z0-9_-]+", raw_search)
                        if len(tok) >= 2 and tok not in _SEARCH_STOPWORDS
                    ]
                    if tokens:
                        dtos = [
                            d
                            for d in dtos
                            if any(
                                tok in d.sku.lower()
                                or tok in d.name.lower()
                                or tok in d.description.lower()
                                or tok in d.warehouse_id.lower()
                                for tok in tokens
                            )
                        ]
                    else:
                        dtos = []

        if tool_input.low_stock_only:
            dtos = [d for d in dtos if d.is_low_stock]

        return dtos

    def query_inventory(self, tool_input: InventoryToolInput) -> InventoryToolOutput:
        """Query live product stock projections with a strict numerical timeout and 20-record cap.

        Args:
            tool_input: Typed InventoryToolInput criteria.

        Returns:
            InventoryToolOutput with status ('success', 'not_found', 'timeout', 'error'),
            up to 20 records, total_matched count, and latency_ms.
        """
        start_ns = time.perf_counter()
        criteria_dict = tool_input.to_dict()
        cap_limit = max(1, min(MAX_TOOL_RECORDS, int(tool_input.limit)))

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self._execute_lookup, tool_input)
            matched_dtos: List[InventoryRecordDTO] = future.result(
                timeout=self._timeout_seconds
            )
        except (FuturesTimeoutError, TimeoutError, httpx.TimeoutException):
            elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
            return InventoryToolOutput(
                status="timeout",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message=(
                    f"Inventory stock lookup timed out after {self._timeout_seconds:.1f} seconds."
                ),
                queried_criteria=criteria_dict,
            )
        except Exception:
            elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
            return InventoryToolOutput(
                status="error",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message="The Inventory Manager service encountered an error and could not complete the stock lookup.",
                queried_criteria=criteria_dict,
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        # Sort deterministically by (id, sku)
        sorted_dtos = sorted(matched_dtos, key=lambda r: (r.id, r.sku))
        total_matched = len(sorted_dtos)
        capped_records = sorted_dtos[:cap_limit]
        elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))

        if total_matched == 0:
            if tool_input.sku:
                not_found_msg = f"No inventory product matched sku='{tool_input.sku}'."
            elif tool_input.product_id is not None:
                not_found_msg = (
                    f"No inventory product matched product_id={tool_input.product_id}."
                )
            else:
                not_found_msg = (
                    "No inventory products matched the requested search criteria."
                )
            return InventoryToolOutput(
                status="not_found",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message=not_found_msg,
                queried_criteria=criteria_dict,
            )

        return InventoryToolOutput(
            status="success",
            records=capped_records,
            total_matched=total_matched,
            latency_ms=elapsed_ms,
            error_message=None,
            queried_criteria=criteria_dict,
        )


__all__ = [
    "DEFAULT_TOOL_TIMEOUT_SECONDS",
    "InventoryStockQueryToolAdapter",
    "MAX_TOOL_RECORDS",
]
