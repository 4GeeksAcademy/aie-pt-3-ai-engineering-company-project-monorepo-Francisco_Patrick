"""Unit and protocol tests for TrackFlow MCP Server Read-Only Inventory Tool (User Story 2 - T013)."""

import copy
import json
from typing import Any, Dict

import pytest

from conftest import MockUpstreamBackend
from trackflow_server.app import create_mcp_server
from trackflow_server.models.errors import (
    InventoryMutationRejectedError,
    McpErrorCode,
    ResourceNotFoundError,
)
from trackflow_server.tools.inventory import query_inventory_tool


class TestInventoryTool:
    """Verification suite for strictly read-only `query_inventory` and mutation guardrails."""

    async def test_query_inventory_by_sku_and_product_id(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """US2 Scenario 1: Querying by SKU or product_id returns stock levels, warehouse, and low-stock flags."""
        by_sku = await query_inventory_tool(sku="TF-001")
        assert by_sku["status"] == "success"
        assert by_sku["total_matched"] == 1
        record = by_sku["records"][0]
        assert record["sku"] == "TF-001"
        assert record["stock"] == 145
        assert record["min_threshold"] == 20
        assert record["is_low_stock"] is False
        assert record["warehouse_id"] == "zaragoza"

        by_id = await query_inventory_tool(product_id=2)
        assert by_id["status"] == "success"
        assert by_id["total_matched"] == 1
        low_record = by_id["records"][0]
        assert low_record["sku"] == "TF-002"
        assert low_record["stock"] == 8
        assert low_record["is_low_stock"] is True

    async def test_query_inventory_free_text_query(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """Free text search matches product name or description."""
        res = await query_inventory_tool(query="Stretch Wrap")
        assert res["status"] == "success"
        assert res["total_matched"] == 1
        assert res["records"][0]["sku"] == "TF-002"

    async def test_query_inventory_missing_sku_returns_not_found(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """US2 Scenario 3: Querying non-existent SKU raises structured ResourceNotFoundError."""
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await query_inventory_tool(sku="TF-NONEXISTENT-999")
        assert exc_info.value.error_code == McpErrorCode.RESOURCE_NOT_FOUND

    @pytest.mark.parametrize(
        "mutation_kwargs",
        [
            {"sku": "TF-001", "action": "update", "stock_adjustment": 50},
            {"sku": "TF-001", "quantity_change": -10},
            {"product_id": 1, "order_type": "inbound", "quantity": 100},
            {"sku": "TF-001", "stock": 500},
            {"sku": "TF-001", "operation": "delete"},
            {"query": "update stock for SKU TF-001 to 500 units"},
            {"query": "create inbound order for 100 units of TF-001"},
            {"sku": "DELETE TF-001"},
        ],
    )
    async def test_query_inventory_rejects_all_mutation_attempts_with_zero_side_effects(
        self,
        mock_upstream_backend: MockUpstreamBackend,
        mutation_kwargs: Dict[str, Any],
    ) -> None:
        """US2 Scenario 2 & SC-002: 100% of write/mutation payloads are rejected with INVENTORY_MUTATION_REJECTED."""
        snapshot_before = copy.deepcopy(mock_upstream_backend.products)
        requests_before = len(mock_upstream_backend.request_log)

        with pytest.raises(InventoryMutationRejectedError) as exc_info:
            await query_inventory_tool(**mutation_kwargs)

        assert exc_info.value.error_code == McpErrorCode.INVENTORY_MUTATION_REJECTED
        assert exc_info.value.http_status == 403
        assert "read-only" in exc_info.value.message.lower()
        assert mock_upstream_backend.products == snapshot_before
        assert len(mock_upstream_backend.request_log) == requests_before

    async def test_fastmcp_exposes_only_read_only_inventory_tool(
        self,
        mock_upstream_backend: MockUpstreamBackend,
        token_factory: Any,
    ) -> None:
        """T015: Verify query_inventory is registered and no write inventory tools exist."""
        from trackflow_server.auth.middleware import (
            set_current_security_context,
            verify_bearer_token,
        )

        mcp = create_mcp_server()
        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}

        assert "query_inventory" in tool_names
        prohibited_tools = {
            "create_product",
            "update_product",
            "delete_product",
            "adjust_stock",
            "update_inventory",
            "create_inbound_order",
            "create_outbound_order",
        }
        assert tool_names.isdisjoint(prohibited_tools)

        set_current_security_context(
            verify_bearer_token(token_factory(scopes=["inventory:read"]))
        )
        try:
            tool_result = await mcp.call_tool("query_inventory", {"sku": "TF-001"})
        finally:
            set_current_security_context(None)
        text_blocks = [
            getattr(c, "text", "") for c in tool_result.content if hasattr(c, "text")
        ]
        parsed = json.loads("\n".join(text_blocks))
        assert parsed["status"] == "success"
        assert parsed["records"][0]["sku"] == "TF-001"
