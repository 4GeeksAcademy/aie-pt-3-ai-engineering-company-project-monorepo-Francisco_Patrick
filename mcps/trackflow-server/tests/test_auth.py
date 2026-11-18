"""Unit and integration tests for OAuth 2.1 authentication, RFC 9728 metadata, and scope enforcement (User Story 3 - T017)."""

import json
from pathlib import Path
from typing import Any, Callable, Dict

import httpx
import pytest

from conftest import MockUpstreamBackend
from trackflow_server.app import create_asgi_app, create_mcp_server
from trackflow_server.auth.middleware import set_current_security_context, verify_bearer_token
from trackflow_server.auth.scopes import TOOL_REQUIRED_SCOPES, check_tool_scope
from trackflow_server.models.errors import (
    AuthenticationRequiredError,
    InsufficientScopeError,
    McpErrorCode,
)


class TestOAuthAndDiscovery:
    """Verification suite for OAuth 2.1 Bearer protection, scope permissions, and tool discovery."""

    async def test_unauthenticated_sse_and_messages_requests_rejected_with_401(self) -> None:
        """US3 Scenario 1 & SC-001: Unauthenticated requests to /sse and /messages/ return 401 with WWW-Authenticate header."""
        app = create_asgi_app(transport="sse")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            sse_res = await client.get("/sse")
            assert sse_res.status_code == 401
            assert "Bearer" in sse_res.headers.get("WWW-Authenticate", "")
            assert "invalid_token" in sse_res.headers.get("WWW-Authenticate", "")
            sse_body = sse_res.json()
            assert sse_body["error_code"] == McpErrorCode.AUTHENTICATION_REQUIRED.value

            msg_res = await client.post(
                "/messages/",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            assert msg_res.status_code == 401
            assert msg_res.json()["error_code"] == McpErrorCode.AUTHENTICATION_REQUIRED.value

    async def test_expired_and_malformed_tokens_rejected_with_401(
        self, token_factory: Callable[..., str]
    ) -> None:
        """Edge Case: Expired or tampered JWTs are rejected with AUTHENTICATION_REQUIRED (401)."""
        expired_token = token_factory(expires_in_seconds=-120)
        with pytest.raises(AuthenticationRequiredError) as exc_exp:
            verify_bearer_token(expired_token)
        assert exc_exp.value.error_code == McpErrorCode.AUTHENTICATION_REQUIRED

        with pytest.raises(AuthenticationRequiredError) as exc_bad:
            verify_bearer_token("not-a-valid-jwt-token")
        assert exc_bad.value.error_code == McpErrorCode.AUTHENTICATION_REQUIRED

        app = create_asgi_app(transport="sse")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get(
                "/sse", headers={"Authorization": f"Bearer {expired_token}"}
            )
            assert res.status_code == 401
            assert res.json()["error_code"] == McpErrorCode.AUTHENTICATION_REQUIRED.value

    async def test_protected_resource_metadata_endpoint_matches_rfc9728_contract(self) -> None:
        """FR-004 & T020: /.well-known/oauth-protected-resource returns RFC 9728 metadata."""
        app = create_asgi_app(transport="sse")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/.well-known/oauth-protected-resource")
            assert res.status_code == 200
            data = res.json()
            assert "resource" in data
            assert isinstance(data["authorization_servers"], list)
            assert len(data["authorization_servers"]) >= 1
            assert set(data["scopes_supported"]) == {
                "incidents:read",
                "incidents:write",
                "incidents:lifecycle",
                "inventory:read",
            }
            assert data["bearer_methods_supported"] == ["header"]

            # Also verify mcpauth /.well-known/oauth-authorization-server route is mounted
            oauth_res = await client.get("/.well-known/oauth-authorization-server")
            assert oauth_res.status_code == 200
            oauth_data = oauth_res.json()
            assert "issuer" in oauth_data

    async def test_fine_grained_scope_enforcement_per_tool(
        self,
        mock_upstream_backend: MockUpstreamBackend,
        token_factory: Callable[..., str],
    ) -> None:
        """US3 Scenario 2 & FR-005: Token lacking required tool scope is denied with INSUFFICIENT_SCOPE."""
        assert TOOL_REQUIRED_SCOPES == {
            "create_incident": "incidents:write",
            "query_incidents": "incidents:read",
            "transition_incident_status": "incidents:lifecycle",
            "query_inventory": "inventory:read",
        }

        read_only_token = token_factory(scopes=["incidents:read"], client_id="reader-bot")
        ctx = verify_bearer_token(read_only_token)

        # incidents:read is allowed for query_incidents
        check_tool_scope("query_incidents", ctx)

        # incidents:read is denied for create_incident, transition_incident_status, query_inventory
        for forbidden_tool in (
            "create_incident",
            "transition_incident_status",
            "query_inventory",
        ):
            with pytest.raises(InsufficientScopeError) as exc_scope:
                check_tool_scope(forbidden_tool, ctx)
            assert exc_scope.value.error_code == McpErrorCode.INSUFFICIENT_SCOPE
            assert exc_scope.value.http_status == 403

        # Verify FastMCP middleware blocks tool call when scope is insufficient
        mcp = create_mcp_server()
        set_current_security_context(ctx)
        try:
            with pytest.raises(Exception) as exc_call:
                await mcp.call_tool(
                    "create_incident",
                    {
                        "title": "Unauthorized incident creation",
                        "description": "Should be blocked by scope middleware",
                        "category": "warehouse",
                        "origin": "branch",
                        "branch": "zaragoza",
                    },
                )
            assert "INSUFFICIENT_SCOPE" in str(exc_call.value) or "incidents:write" in str(exc_call.value)
        finally:
            set_current_security_context(None)

    async def test_http_jsonrpc_messages_scope_and_tool_execution(
        self,
        mock_upstream_backend: MockUpstreamBackend,
        token_factory: Callable[..., str],
    ) -> None:
        """Quickstart Scenario 1: POST /messages/ with insufficient scope returns 403 INSUFFICIENT_SCOPE; valid scope succeeds."""
        app = create_asgi_app(transport="sse")
        transport = httpx.ASGITransport(app=app)
        read_token = token_factory(scopes=["incidents:read"], client_id="limited-client")
        write_token = token_factory(
            scopes=["incidents:read", "incidents:write", "incidents:lifecycle", "inventory:read"],
            client_id="full-client",
        )

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Read token attempting create_incident -> 403 INSUFFICIENT_SCOPE
            denied_res = await client.post(
                "/messages/",
                headers={"Authorization": f"Bearer {read_token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "create_incident",
                        "arguments": {
                            "title": "Test incident",
                            "description": "Testing scope denial",
                            "category": "warehouse",
                            "origin": "branch",
                            "branch": "zaragoza",
                        },
                    },
                },
            )
            assert denied_res.status_code == 403
            denied_body = denied_res.json()
            assert denied_body["error_code"] == McpErrorCode.INSUFFICIENT_SCOPE.value
            assert "incidents:write" in denied_body["message"]

            # 2. Full token invoking query_incidents -> 200 OK
            ok_res = await client.post(
                "/messages/",
                headers={"Authorization": f"Bearer {write_token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "query_incidents",
                        "arguments": {"ticket_id": "INC-001"},
                    },
                },
            )
            assert ok_res.status_code == 200
            ok_body = ok_res.json()
            assert ok_body["result"]["records"][0]["id"] == "INC-001"

    async def test_tool_discovery_metadata_matches_mcp_tools_contract(self) -> None:
        """US3 Scenario 3 & SC-003: Tool discovery publishes complete descriptions and schemas matching contracts/mcp-tools.json."""
        contract_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "specs"
            / "028-mcp-server-tools"
            / "contracts"
            / "mcp-tools.json"
        )
        contract_data: Dict[str, Any] = json.loads(contract_path.read_text(encoding="utf-8"))
        expected_tools = {t["name"]: t for t in contract_data["tools"]}

        mcp = create_mcp_server()
        discovered_tools = await mcp.list_tools()
        discovered_map = {t.name: t for t in discovered_tools}

        assert set(discovered_map.keys()) == set(expected_tools.keys())
        for name, expected in expected_tools.items():
            tool = discovered_map[name]
            assert tool.description and len(tool.description) >= 20
            schema = tool.parameters
            expected_props = set(expected["inputSchema"]["properties"].keys())
            actual_props = set(schema.get("properties", {}).keys())
            assert expected_props == actual_props
