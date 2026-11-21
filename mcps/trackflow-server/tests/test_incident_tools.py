"""Unit and protocol tests for TrackFlow MCP Server Incident Tools (User Story 1 - T009)."""

import json
from typing import Any, Dict

import pytest

from trackflow_server.app import create_mcp_server
from trackflow_server.models.errors import (
    LifecycleTransitionDisallowedError,
    McpErrorCode,
    ResourceNotFoundError,
    ToolValidationError,
    UpstreamUnavailableError,
)
from conftest import MockUpstreamBackend
from trackflow_server.tools.incidents import (
    create_incident_tool,
    query_incidents_tool,
    transition_incident_status_tool,
)


class TestIncidentTools:
    """Verification suite for `create_incident`, `query_incidents`, and `transition_incident_status`."""

    async def test_create_incident_returns_open_ticket_and_calls_post_endpoint(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """US1 Scenario 1: Creating an incident with valid attributes returns a new 'open' record."""
        result = await create_incident_tool(
            title="Conveyor belt jam in Zaragoza Sector B",
            description="Main sorting conveyor halted due to sensor fault.",
            category="warehouse",
            origin="branch",
            branch="zaragoza",
        )

        assert result["id"].startswith("INC-")
        assert result["status"] == "open"
        assert result["title"] == "Conveyor belt jam in Zaragoza Sector B"
        assert result["category"] == "warehouse"
        assert result["origin"] == "branch"
        assert result["branch"] == "zaragoza"
        assert "created_at" in result
        assert "updated_at" in result

        assert ("POST", "/api/incidents", {
            "title": "Conveyor belt jam in Zaragoza Sector B",
            "description": "Main sorting conveyor halted due to sensor fault.",
            "category": "warehouse",
            "origin": "branch",
            "branch": "zaragoza",
        }) in mock_upstream_backend.request_log

    async def test_create_incident_rejects_invalid_category_or_short_title(self) -> None:
        """Input validation errors raise categorized ToolValidationError (VALIDATION_ERROR)."""
        with pytest.raises(ToolValidationError) as exc_info:
            await create_incident_tool(
                title="Hi",  # Too short (< 3 chars)
                description="Valid description here",
                category="warehouse",
                origin="branch",
                branch="zaragoza",
            )
        assert exc_info.value.error_code == McpErrorCode.VALIDATION_ERROR

        with pytest.raises(ToolValidationError) as exc_cat:
            await create_incident_tool(
                title="Valid Title",
                description="Valid description here",
                category="invalid_category",
                origin="branch",
                branch="zaragoza",
            )
        assert exc_cat.value.error_code == McpErrorCode.VALIDATION_ERROR

    async def test_query_incidents_by_id_and_filters(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """US1 Scenario 2: Querying by ticket_id or filters returns matching domain records."""
        # 1. Exact ID lookup
        by_id = await query_incidents_tool(ticket_id="INC-001")
        assert by_id["status"] == "success"
        assert by_id["total_matched"] == 1
        assert len(by_id["records"]) == 1
        assert by_id["records"][0]["id"] == "INC-001"
        assert by_id["records"][0]["branch"] == "zaragoza"

        # 2. Filter by status="in_progress"
        by_status = await query_incidents_tool(status="in_progress")
        assert by_status["status"] == "success"
        assert by_status["total_matched"] == 1
        assert by_status["records"][0]["id"] == "INC-002"

        # 3. Missing ticket ID raises ResourceNotFoundError
        with pytest.raises(ResourceNotFoundError) as exc_nf:
            await query_incidents_tool(ticket_id="INC-999")
        assert exc_nf.value.error_code == McpErrorCode.RESOURCE_NOT_FOUND

    async def test_transition_incident_status_valid_lifecycle_flow(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """US1 Scenario 3: Valid transition open -> in_progress -> resolved invokes PATCH /api/incidents/{id}/status."""
        # Transition INC-001 from open -> in_progress
        step1 = await transition_incident_status_tool(
            ticket_id="INC-001",
            status="in_progress",
        )
        assert step1["id"] == "INC-001"
        assert step1["status"] == "in_progress"

        # Verify strict routing through PATCH /api/incidents/INC-001/status (FR-007)
        patch_calls = [
            entry
            for entry in mock_upstream_backend.request_log
            if entry[0] == "PATCH" and entry[1] == "/api/incidents/INC-001/status"
        ]
        assert len(patch_calls) == 1
        assert patch_calls[0][2] == {"status": "in_progress"}

        # Transition INC-001 from in_progress -> resolved
        step2 = await transition_incident_status_tool(
            ticket_id="INC-001",
            status="resolved",
        )
        assert step2["status"] == "resolved"

    async def test_transition_incident_status_rejects_disallowed_transitions(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """US1 Scenario 4: Disallowed transitions (open -> resolved, resolved -> in_progress, discarded -> resolved) are rejected."""
        # 1. Direct jump open -> resolved is disallowed
        with pytest.raises(LifecycleTransitionDisallowedError) as exc_jump:
            await transition_incident_status_tool(
                ticket_id="INC-001",
                status="resolved",
            )
        assert exc_jump.value.error_code == McpErrorCode.LIFECYCLE_TRANSITION_DISALLOWED
        assert mock_upstream_backend.incidents["INC-001"]["status"] == "open"

        # 2. Terminal state resolved -> in_progress is disallowed
        with pytest.raises(LifecycleTransitionDisallowedError) as exc_resolved:
            await transition_incident_status_tool(
                ticket_id="INC-003",
                status="in_progress",
            )
        assert exc_resolved.value.error_code == McpErrorCode.LIFECYCLE_TRANSITION_DISALLOWED
        assert mock_upstream_backend.incidents["INC-003"]["status"] == "resolved"

        # 3. Terminal state discarded -> resolved is disallowed
        with pytest.raises(LifecycleTransitionDisallowedError) as exc_discarded:
            await transition_incident_status_tool(
                ticket_id="INC-004",
                status="resolved",
            )
        assert exc_discarded.value.error_code == McpErrorCode.LIFECYCLE_TRANSITION_DISALLOWED
        assert mock_upstream_backend.incidents["INC-004"]["status"] == "discarded"

    async def test_upstream_timeout_maps_to_upstream_unavailable(
        self, mock_upstream_backend: MockUpstreamBackend
    ) -> None:
        """Edge Case: Upstream timeout raises UpstreamUnavailableError (UPSTREAM_UNAVAILABLE)."""
        mock_upstream_backend.simulate_timeout = True
        with pytest.raises(UpstreamUnavailableError) as exc_timeout:
            await query_incidents_tool(ticket_id="INC-001")
        assert exc_timeout.value.error_code == McpErrorCode.UPSTREAM_UNAVAILABLE

    async def test_fastmcp_registered_incident_tools_execution(
        self,
        mock_upstream_backend: MockUpstreamBackend,
        token_factory: Any,
    ) -> None:
        """T011: Verify incident tools are registered on FastMCP server and callable via protocol with valid token."""
        from trackflow_server.auth.middleware import (
            set_current_security_context,
            verify_bearer_token,
        )

        mcp = create_mcp_server()
        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}
        assert "create_incident" in tool_names
        assert "query_incidents" in tool_names
        assert "transition_incident_status" in tool_names

        set_current_security_context(
            verify_bearer_token(token_factory(scopes=["incidents:read"]))
        )
        try:
            tool_result = await mcp.call_tool(
                "query_incidents", {"ticket_id": "INC-001"}
            )
        finally:
            set_current_security_context(None)
        assert tool_result is not None
        text_blocks = [
            getattr(c, "text", "") for c in tool_result.content if hasattr(c, "text")
        ]
        combined = "\n".join(text_blocks)
        parsed: Dict[str, Any] = json.loads(combined)
        assert parsed["status"] == "success"
        assert parsed["records"][0]["id"] == "INC-001"
