"""Unit tests for structured JSON audit logging and PII / credential masking (User Story 3 - T018)."""

import json
from pathlib import Path
from typing import Any, Callable, Dict

import jsonschema
import pytest

from conftest import MockUpstreamBackend
from trackflow_server.app import create_mcp_server
from trackflow_server.auth.middleware import set_current_security_context, verify_bearer_token
from trackflow_server.logging.audit import get_audit_logger, sanitize_arguments


class TestAuditLogging:
    """Verification suite for structured audit logging (FR-011, SC-005) and PII/secret redaction."""

    def test_sanitize_arguments_masks_emails_jwts_and_secret_keys(
        self, token_factory: Callable[..., str]
    ) -> None:
        """Constitution Principle IV: Emails, JWTs, Bearer tokens, and secret fields are strictly redacted."""
        sample_jwt = token_factory(scopes=["incidents:read"])
        raw_args: Dict[str, Any] = {
            "title": "Customer ana.garcia@example.com reported missing parcel",
            "description": f"Caller passed Authorization: Bearer {sample_jwt} and password=super_secret_123",
            "access_token": sample_jwt,
            "nested": {
                "api_key": "sk-live-999999",
                "contact": "support.lead@trackflow.io",
            },
        }

        sanitized = sanitize_arguments(raw_args)
        serialized = json.dumps(sanitized)

        assert "ana.garcia@example.com" not in serialized
        assert "support.lead@trackflow.io" not in serialized
        assert sample_jwt not in serialized
        assert "super_secret_123" not in serialized
        assert "sk-live-999999" not in serialized
        assert "[REDACTED_EMAIL]" in sanitized["title"]
        assert sanitized["access_token"] == "***REDACTED***"
        assert sanitized["nested"]["api_key"] == "***REDACTED***"
        assert sanitized["nested"]["contact"] == "[REDACTED_EMAIL]"

    async def test_audit_log_emitted_for_success_rejected_and_error_outcomes(
        self,
        mock_upstream_backend: MockUpstreamBackend,
        token_factory: Callable[..., str],
    ) -> None:
        """US3 Scenario 4 & SC-005: 100% of tool calls emit audit entries conforming to contracts/audit-log.json."""
        schema_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "specs"
            / "028-mcp-server-tools"
            / "contracts"
            / "audit-log.json"
        )
        audit_schema = json.loads(schema_path.read_text(encoding="utf-8"))

        audit_logger = get_audit_logger()
        audit_logger.clear()

        mcp = create_mcp_server()
        full_ctx = verify_bearer_token(
            token_factory(
                scopes=["incidents:read", "incidents:write", "incidents:lifecycle", "inventory:read"],
                client_id="audit-test-client",
            )
        )
        set_current_security_context(full_ctx)
        try:
            # 1. SUCCESS invocation (with PII in description to verify masking in recorded log)
            await mcp.call_tool(
                "create_incident",
                {
                    "title": "Parcel delay for client@domain.org",
                    "description": "Customer client@domain.org reported delay in Zaragoza.",
                    "category": "delay",
                    "origin": "customer",
                    "branch": "zaragoza",
                },
            )

            # 2. REJECTED invocation (inventory mutation attempt)
            with pytest.raises(Exception):
                await mcp.call_tool(
                    "query_inventory",
                    {"sku": "DELETE TF-001"},
                )

            # 3. ERROR invocation (disallowed lifecycle transition)
            with pytest.raises(Exception):
                await mcp.call_tool(
                    "transition_incident_status",
                    {"ticket_id": "INC-001", "status": "resolved"},
                )
        finally:
            set_current_security_context(None)

        records = audit_logger.records
        assert len(records) == 3

        # Validate every record against contracts/audit-log.json schema
        for entry in records:
            payload = entry.model_dump(exclude_none=True)
            jsonschema.validate(instance=payload, schema=audit_schema)
            assert entry.client_id == "audit-test-client"
            assert entry.latency_ms >= 0.0
            assert "client@domain.org" not in json.dumps(payload)

        assert records[0].tool_name == "create_incident"
        assert records[0].outcome == "SUCCESS"
        assert records[0].error_code is None

        assert records[1].tool_name == "query_inventory"
        assert records[1].outcome == "REJECTED"
        assert records[1].error_code == "INVENTORY_MUTATION_REJECTED"

        assert records[2].tool_name == "transition_incident_status"
        assert records[2].outcome == "ERROR"
        assert records[2].error_code == "LIFECYCLE_TRANSITION_DISALLOWED"
