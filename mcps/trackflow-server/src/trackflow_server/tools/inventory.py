"""Strictly read-only MCP tool for TrackFlow Warehouse Inventory Queries (`query_inventory`)."""

import re
from typing import Annotated, Any, Dict, Optional

from fastmcp import FastMCP
from pydantic import Field, ValidationError

from trackflow_server.app import get_upstream_client
from trackflow_server.models.errors import (
    InventoryMutationRejectedError,
    ResourceNotFoundError,
    ToolValidationError,
)
from trackflow_server.models.schemas import (
    QueryInventoryInput,
    QueryInventoryResponse,
)

_ALLOWED_INVENTORY_KEYS = {"sku", "product_id", "query"}

_MUTATION_PARAMETER_KEYS = {
    "action",
    "operation",
    "method",
    "stock",
    "current_stock",
    "stock_adjustment",
    "stock_delta",
    "quantity",
    "quantity_change",
    "delta",
    "order_type",
    "create_order",
    "inbound",
    "outbound",
    "update",
    "delete",
    "remove",
    "adjust",
    "set_stock",
    "min_threshold",
    "low_stock_threshold",
}

_MUTATION_STRING_PATTERN = re.compile(
    r"\b(?:update|modify|set|change|delete|remove|drop|insert|create|add|adjust|increase|decrease|deduct|restock|dispatch|inbound\s+order|outbound\s+order)\b",
    re.IGNORECASE,
)


def enforce_inventory_read_only_guard(
    *,
    sku: Optional[str] = None,
    product_id: Optional[int] = None,
    query: Optional[str] = None,
    extra_kwargs: Optional[Dict[str, Any]] = None,
) -> None:
    """Intercept and reject any parameter or text payload attempting to mutate inventory (FR-010, T016).

    Raises:
        InventoryMutationRejectedError: When any write/mutation indicator is present.
    """
    if extra_kwargs:
        extra_keys = set(extra_kwargs.keys())
        mutation_keys = extra_keys & _MUTATION_PARAMETER_KEYS
        if mutation_keys or extra_keys:
            rejected_fields = sorted(mutation_keys or extra_keys)
            raise InventoryMutationRejectedError(
                message=(
                    f"Inventory access via MCP is strictly read-only. "
                    f"Prohibited mutation parameter(s) detected: {rejected_fields}."
                ),
                details={"prohibited_parameters": rejected_fields},
            )

    for field_name, text_val in (("sku", sku), ("query", query)):
        if isinstance(text_val, str) and text_val.strip():
            if _MUTATION_STRING_PATTERN.search(text_val):
                raise InventoryMutationRejectedError(
                    message=(
                        f"Inventory access via MCP is strictly read-only. "
                        f"Mutation command detected in '{field_name}' parameter."
                    ),
                    details={"field": field_name, "value": text_val},
                )


async def query_inventory_tool(
    sku: Optional[str] = None,
    product_id: Optional[int] = None,
    query: Optional[str] = None,
    **extra_kwargs: Any,
) -> Dict[str, Any]:
    """Query warehouse inventory stock projections and availability by SKU, product ID, or search query.

    STRICTLY READ-ONLY: Any attempt to mutate stock or submit orders is immediately rejected
    with `INVENTORY_MUTATION_REJECTED`.
    """
    enforce_inventory_read_only_guard(
        sku=sku,
        product_id=product_id,
        query=query,
        extra_kwargs=extra_kwargs,
    )

    try:
        validated = QueryInventoryInput(
            sku=sku,
            product_id=product_id,
            query=query,
        )
    except ValidationError as exc:
        raise ToolValidationError(
            f"Invalid parameters for query_inventory: {exc.errors()}",
            details={"validation_errors": exc.errors()},
        ) from exc

    criteria = validated.model_dump(exclude_none=True)
    client = get_upstream_client()
    records = await client.query_inventory(
        sku=validated.sku,
        product_id=validated.product_id,
        query=validated.query,
    )

    if not records and (validated.sku is not None or validated.product_id is not None):
        target = (
            f"sku='{validated.sku}'"
            if validated.sku
            else f"product_id={validated.product_id}"
        )
        raise ResourceNotFoundError(
            f"No inventory product record found matching {target}.",
            details=criteria,
        )

    response = QueryInventoryResponse(
        status="success" if records else "not_found",
        records=records,
        total_matched=len(records),
        queried_criteria=criteria,
    )
    return response.model_dump()


def register_inventory_tools(mcp: FastMCP) -> None:
    """Register the strictly read-only `query_inventory` tool on the FastMCP server."""

    @mcp.tool(
        name="query_inventory",
        description=(
            "Query warehouse inventory stock projections and availability by SKU or product ID. "
            "STRICTLY READ-ONLY: Any attempt to mutate stock or submit orders is rejected "
            "with INVENTORY_MUTATION_REJECTED. Required OAuth scope: 'inventory:read'."
        ),
    )
    async def query_inventory(
        sku: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Stock Keeping Unit code (e.g. 'TF-001')",
            ),
        ] = None,
        product_id: Annotated[
            Optional[int],
            Field(
                default=None,
                ge=1,
                description="Numerical product ID",
            ),
        ] = None,
        query: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Free text query matching product name or description",
            ),
        ] = None,
    ) -> Dict[str, Any]:
        return await query_inventory_tool(
            sku=sku,
            product_id=product_id,
            query=query,
        )


__all__ = [
    "enforce_inventory_read_only_guard",
    "query_inventory_tool",
    "register_inventory_tools",
]
