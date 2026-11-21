"""Unit tests for McpTicketToolAdapter using langchain-mcp-adapters (User Story 4 - T024)."""

import asyncio
import json
from typing import Any, Dict, List
import warnings

from langchain_core.tools import StructuredTool
import pytest

from domain.agent.entities import TicketToolInput
from infrastructure.adapters.mcp_ticket_tool_adapter import McpTicketToolAdapter


class MockMultiServerMCPClient:
    """Mock of `langchain_mcp_adapters.client.MultiServerMCPClient` returning LangChain MCP tools."""

    def __init__(
        self,
        records: List[Dict[str, Any]],
        *,
        simulate_timeout: bool = False,
        simulate_error: bool = False,
    ) -> None:
        self._records = records
        self._simulate_timeout = simulate_timeout
        self._simulate_error = simulate_error
        self.invocations: List[Dict[str, Any]] = []

    async def get_tools(self) -> List[StructuredTool]:
        """Return a LangChain StructuredTool representing the MCP `query_incidents` tool."""

        async def _query_incidents(
            ticket_id: str | None = None,
            status: str | None = None,
            category: str | None = None,
            origin: str | None = None,
            branch: str | None = None,
        ) -> str:
            self.invocations.append(
                {
                    "ticket_id": ticket_id,
                    "status": status,
                    "category": category,
                    "origin": origin,
                    "branch": branch,
                }
            )
            if self._simulate_timeout:
                await asyncio.sleep(2.0)
            if self._simulate_error:
                raise RuntimeError("MCP server connection failed")

            matched = list(self._records)
            if ticket_id:
                matched = [
                    r
                    for r in matched
                    if str(r.get("id", "")).lower() == ticket_id.lower()
                ]
            if status:
                matched = [
                    r
                    for r in matched
                    if str(r.get("status", "")).lower() == status.lower()
                ]
            if branch:
                matched = [
                    r
                    for r in matched
                    if str(r.get("branch", "")).lower() == branch.lower()
                ]
            return json.dumps(
                {
                    "status": "success" if matched else "not_found",
                    "records": matched,
                    "total_matched": len(matched),
                    "queried_criteria": {"ticket_id": ticket_id, "status": status},
                }
            )

        return [
            StructuredTool.from_function(
                coroutine=_query_incidents,
                name="query_incidents",
                description="Query operational incident records via MCP",
            )
        ]


class TestMcpTicketToolAdapter:
    """Verification suite for McpTicketToolAdapter (T024, T026)."""

    def test_query_tickets_via_langchain_mcp_client_by_ticket_id(self) -> None:
        """US4 Scenario 1: Adapter invokes MCP `query_incidents` tool via MultiServerMCPClient and maps TicketRecordDTO."""
        sample_records = [
            {
                "id": "INC-001",
                "title": "Delayed pallet shipment to Zaragoza",
                "description": "Pallet delayed at hub.",
                "status": "open",
                "category": "warehouse",
                "origin": "internal",
                "branch": "zaragoza",
                "created_at": "2026-11-17T09:00:00+00:00",
                "updated_at": "2026-11-18T10:30:00+00:00",
            }
        ]
        mock_client = MockMultiServerMCPClient(sample_records)
        adapter = McpTicketToolAdapter(mcp_client=mock_client, timeout_seconds=2.0)

        output = adapter.query_tickets(TicketToolInput(ticket_id="INC-001"))

        assert output.status == "success"
        assert output.total_matched == 1
        assert len(output.records) == 1
        assert output.records[0].id == "INC-001"
        assert output.records[0].branch == "zaragoza"
        assert len(mock_client.invocations) == 1
        assert mock_client.invocations[0]["ticket_id"] == "INC-001"

    def test_query_tickets_returns_not_found_when_mcp_returns_empty(self) -> None:
        """Missing ticket ID via MCP returns status='not_found'."""
        mock_client = MockMultiServerMCPClient([])
        adapter = McpTicketToolAdapter(mcp_client=mock_client, timeout_seconds=2.0)

        output = adapter.query_tickets(TicketToolInput(ticket_id="INC-404"))
        assert output.status == "not_found"
        assert output.total_matched == 0
        assert output.records == []

    def test_query_tickets_handles_mcp_timeout_and_errors_gracefully(self) -> None:
        """Timeout and MCP transport errors map to 'timeout' and 'error' statuses without crashing."""
        timeout_client = MockMultiServerMCPClient([], simulate_timeout=True)
        timeout_adapter = McpTicketToolAdapter(
            mcp_client=timeout_client, timeout_seconds=0.15
        )
        timeout_out = timeout_adapter.query_tickets(TicketToolInput(ticket_id="INC-001"))
        assert timeout_out.status == "timeout"

        error_client = MockMultiServerMCPClient([], simulate_error=True)
        error_adapter = McpTicketToolAdapter(
            mcp_client=error_client, timeout_seconds=1.0
        )
        error_out = error_adapter.query_tickets(TicketToolInput(ticket_id="INC-001"))
        assert error_out.status == "error"

    def test_multi_server_mcp_client_connection_config_uses_sse_and_bearer_header(self) -> None:
        """Verify adapter builds SSEConnection config compatible with langchain-mcp-adapters MultiServerMCPClient."""
        adapter = McpTicketToolAdapter(
            mcp_server_url="http://localhost:8001/sse",
            auth_token="test-jwt-token-xyz",
        )
        conn_config = adapter.build_connection_config()
        assert "trackflow" in conn_config
        assert conn_config["trackflow"]["transport"] == "sse"
        assert conn_config["trackflow"]["url"] == "http://localhost:8001/sse"
        assert (
            conn_config["trackflow"]["headers"]["Authorization"]
            == "Bearer test-jwt-token-xyz"
        )

    def test_legacy_adapter_emits_deprecation_warning(self) -> None:
        """T029: Instantiating legacy IncidentSupportTicketToolAdapter emits DeprecationWarning."""
        from infrastructure.adapters.support_ticket_tool_adapter import (
            IncidentSupportTicketToolAdapter,
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = IncidentSupportTicketToolAdapter()
            deprecation_warnings = [
                w for w in caught if issubclass(w.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "McpTicketToolAdapter" in str(deprecation_warnings[0].message)
