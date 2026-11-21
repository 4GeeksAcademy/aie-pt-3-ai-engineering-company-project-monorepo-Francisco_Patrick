"""Integration tests for Support Agent FastAPI endpoints (T043).

Verifies:
- `POST /api/v1/agent/query` and `POST /agent/query` for:
  - Standard policy grounded answers (`node_sequence: ["intake", "retrieval", "generation"]`, `sources_consulted: ["rag"]`)
  - Live support ticket queries (`node_sequence: ["intake", "ticket_tool", "generation"]`, `sources_consulted: ["ticket_tool"]`)
  - Honest fallback recovery on non-existent ticket (`node_sequence: ["intake", "ticket_tool", "tool_fallback"]`, `fallback_triggered: true`)
  - Live inventory stock queries (`node_sequence: ["intake", "inventory_tool", "generation"]`, `sources_consulted: ["inventory_tool"]`)
  - Out-of-scope policy refusal, whitespace early termination, and write-mutation refusal.
- `GET /api/v1/agent/trace/{trace_id}` (200 OK with `sources_consulted`, `fallback_triggered`, `tool_calls`, and step latencies; 404 Not Found for missing ID)
- `GET /api/v1/agent/health` (200 OK reporting compiled 7-node graph and checkpointer)
- Defensive error shielding and zero raw stack trace or internal file path leakage.
"""

import os
from typing import Any, Dict, List

from fastapi.testclient import TestClient
from tinydb import TinyDB

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-agent-integration-tests")
os.environ["QDRANT_URL"] = ""
os.environ["QDRANT_HOST"] = ""
os.environ["QDRANT_PATH"] = ""

from application.inventory.dto import InboundOrderCreateDTO, ProductCreateDTO  # noqa: E402
from application.inventory.inventory_service import InventoryService  # noqa: E402
from domain.agent.entities import AgentCheckpoint, AgentQueryRequest, AgentQueryResult, AgentTrace  # noqa: E402
from domain.agent.ports import SupportAgentServicePort  # noqa: E402
from domain.incident_model import Incident  # noqa: E402
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException  # noqa: E402
from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository  # noqa: E402
from infrastructure.persistence.sqlmodel.inventory_repository import SQLModelInventoryRepository  # noqa: E402
from infrastructure.persistence.tinydb.client import get_tinydb  # noqa: E402
from main import app  # noqa: E402
from presentation.dependencies import get_support_agent_service  # noqa: E402
from shared.incidents.enums import IncidentCategory, IncidentOrigin, IncidentStatus  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


class TestSupportAgentRoutesIntegration:
    """End-to-end HTTP integration test suite for `/api/v1/agent/*` and `/agent/*` (T043)."""

    def test_t043_health_endpoint_v1_and_legacy_alias_reports_7_nodes(self) -> None:
        """T043: GET /api/v1/agent/health and GET /agent/health must report compiled state and all 7 nodes."""
        expected_nodes = [
            "intake",
            "ticket_tool",
            "inventory_tool",
            "retrieval",
            "tool_fallback",
            "generation",
            "refusal",
        ]
        for path in ("/api/v1/agent/health", "/agent/health"):
            res = client.get(path)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "healthy"
            assert data["compiled"] is True
            assert data["nodes"] == expected_nodes
            assert data["checkpointer"] == "MemorySaver"

    def test_t043_query_endpoint_standard_policy_and_trace_retrieval(self) -> None:
        """T043: POST /api/v1/agent/query returns grounded answer, citations, sources_consulted=['rag'], and GET /trace/{trace_id} returns step breakdown."""
        res = client.post(
            "/api/v1/agent/query",
            json={
                "query": "What is TrackFlow's standard return window and who covers return shipping costs?",
                "top_k": 3,
                "min_score": 0.62,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert data["fallback_triggered"] is False
        assert data["sources_consulted"] == ["rag"]
        assert data["tool_calls"] == []
        assert "30 days" in data["answer"]
        assert "client brand" in data["answer"].lower()
        assert data["node_sequence"] == ["intake", "retrieval", "generation"]
        assert data["trace_id"] != ""
        assert data["execution_time_ms"] > 0.0
        assert len(data["sources"]) >= 1
        assert any(s["source_document"] == "returns-policy" for s in data["sources"])

        # Fetch trace via GET /api/v1/agent/trace/{trace_id}
        trace_id = data["trace_id"]
        trace_res = client.get(f"/api/v1/agent/trace/{trace_id}")
        assert trace_res.status_code == 200
        trace_data = trace_res.json()
        assert trace_data["trace_id"] == trace_id
        assert trace_data["node_sequence"] == ["intake", "retrieval", "generation"]
        assert trace_data["sources_consulted"] == ["rag"]
        assert trace_data["fallback_triggered"] is False
        assert trace_data["tool_calls"] == []
        assert set(trace_data["step_latencies"].keys()) == {
            "intake",
            "retrieval",
            "generation",
        }
        assert all(v > 0.0 for v in trace_data["step_latencies"].values())
        assert trace_data["total_duration_ms"] >= sum(
            trace_data["step_latencies"].values()
        )
        assert trace_data["is_refusal"] is False
        assert trace_data["source_count"] == len(data["sources"])
        assert set(trace_data["node_outputs"].keys()) == {
            "intake",
            "retrieval",
            "generation",
        }
        assert trace_data["node_outputs"]["retrieval"]["context_count"] >= 1
        assert trace_data["node_outputs"]["generation"]["answer"] == data["answer"]

    def test_t043_query_endpoint_live_ticket_tool_and_missing_ticket_fallback(
        self,
    ) -> None:
        """T043: POST /api/v1/agent/query autonomously routes live ticket queries to ticket_tool and missing tickets to tool_fallback."""
        active_db = get_tinydb()
        repo = TinyDBIncidentRepository(active_db)
        repo.save(
            Incident(
                id="INC-001",
                title="Delayed pallet shipment to Zaragoza",
                description="Pallet delayed at hub.",
                category=IncidentCategory.WAREHOUSE,
                status=IncidentStatus.OPEN,
                origin=IncidentOrigin.INTERNAL,
                branch="zaragoza",
                created_at="2026-11-17T09:00:00+00:00",
                updated_at="2026-11-18T10:30:00+00:00",
            )
        )

        # 1. Existing ticket INC-001
        res = client.post(
            "/api/v1/agent/query",
            json={"query": "What is the current status and category of ticket INC-001?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert data["fallback_triggered"] is False
        assert data["sources_consulted"] == ["ticket_tool"]
        assert data["node_sequence"] == ["intake", "ticket_tool", "generation"]
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool_name"] == "ticket_tool"
        assert data["tool_calls"][0]["status"] == "success"
        assert data["tool_calls"][0]["total_matched"] == 1
        assert "INC-001" in data["answer"]
        assert "open" in data["answer"].lower()
        assert "zaragoza" in data["answer"].lower()

        # 2. Non-existent ticket INC-999999 -> honest tool_fallback
        miss_res = client.post(
            "/api/v1/agent/query",
            json={"query": "What is the status of ticket INC-999999?"},
        )
        assert miss_res.status_code == 200
        miss_data = miss_res.json()
        assert miss_data["is_refusal"] is False
        assert miss_data["fallback_triggered"] is True
        assert miss_data["sources_consulted"] == ["ticket_tool"]
        assert miss_data["node_sequence"] == ["intake", "ticket_tool", "tool_fallback"]
        assert len(miss_data["tool_calls"]) == 1
        assert miss_data["tool_calls"][0]["status"] == "not_found"
        assert "couldn't confirm the status of ticket 'INC-999999'" in miss_data["answer"]

        # Verify trace endpoint reflects fallback metadata
        trace_res = client.get(f"/api/v1/agent/trace/{miss_data['trace_id']}")
        assert trace_res.status_code == 200
        trace_body = trace_res.json()
        assert trace_body["fallback_triggered"] is True
        assert trace_body["sources_consulted"] == ["ticket_tool"]
        assert trace_body["tool_calls"][0]["status"] == "not_found"

    def test_t025_agent_uses_mcp_ticket_tool_adapter_and_multi_source_rag_routing(
        self,
    ) -> None:
        """T025 & US4 Scenarios 1-3: Support Agent uses McpTicketToolAdapter and preserves multi-source ticket_tool -> rag routing."""
        from infrastructure.adapters.mcp_ticket_tool_adapter import McpTicketToolAdapter
        from presentation.dependencies import get_support_ticket_tool_dep

        wired_ticket_tool = get_support_ticket_tool_dep()
        assert isinstance(wired_ticket_tool, McpTicketToolAdapter)

        active_db = get_tinydb()
        repo = TinyDBIncidentRepository(active_db)
        repo.save(
            Incident(
                id="INC-001",
                title="Delayed pallet shipment to Zaragoza",
                description="Pallet delayed at hub.",
                category=IncidentCategory.WAREHOUSE,
                status=IncidentStatus.OPEN,
                origin=IncidentOrigin.INTERNAL,
                branch="zaragoza",
                created_at="2026-11-17T09:00:00+00:00",
                updated_at="2026-11-18T10:30:00+00:00",
            )
        )

        hybrid_res = client.post(
            "/api/v1/agent/query",
            json={
                "query": "What is the status of ticket INC-001 and what is TrackFlow's standard return window?",
                "top_k": 3,
                "min_score": 0.62,
            },
        )
        assert hybrid_res.status_code == 200
        hybrid_data = hybrid_res.json()
        assert hybrid_data["is_refusal"] is False
        assert hybrid_data["sources_consulted"] == ["ticket_tool", "rag"]
        assert hybrid_data["node_sequence"] == [
            "intake",
            "ticket_tool",
            "retrieval",
            "generation",
        ]
        assert "INC-001" in hybrid_data["answer"]
        assert "30 days" in hybrid_data["answer"]
        assert len(hybrid_data["sources"]) >= 1

    def test_t043_query_endpoint_live_inventory_tool_routing(self) -> None:
        """T043: POST /api/v1/agent/query autonomously routes SKU stock queries to inventory_tool."""
        inv_service = InventoryService(inventory_repo=SQLModelInventoryRepository())
        created = inv_service.create_product(
            ProductCreateDTO(
                sku="TF-1001",
                name="Industrial Thermal Shipping Label Roll",
                warehouse_id="zaragoza",
                low_stock_threshold=20,
            )
        )
        inv_service.create_inbound_order(
            InboundOrderCreateDTO(
                sku_id=created.id,
                warehouse_id="zaragoza",
                quantity=145,
            ),
            user_uuid="test-seed",
        )

        res = client.post(
            "/api/v1/agent/query",
            json={"query": "How many units of SKU TF-1001 are currently in stock?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert data["fallback_triggered"] is False
        assert data["sources_consulted"] == ["inventory_tool"]
        assert data["node_sequence"] == ["intake", "inventory_tool", "generation"]
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool_name"] == "inventory_tool"
        assert data["tool_calls"][0]["status"] == "success"
        assert "TF-1001" in data["answer"]
        assert "145 units" in data["answer"]

    def test_t043_query_endpoint_honest_refusal_and_mutation_guardrail(self) -> None:
        """T043: POST /api/v1/agent/query routes out-of-scope topic and write-mutation attempts to refusal."""
        res = client.post(
            "/api/v1/agent/query",
            json={
                "query": "What are the temperature requirements for pharmaceutical refrigeration?",
                "top_k": 3,
                "min_score": 0.62,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is True
        assert data["sources"] == []
        assert data["node_sequence"] == ["intake", "retrieval", "refusal"]
        assert "does not contain verified policy regarding" in data["answer"]
        assert "pharmaceutical refrigeration" in data["answer"].lower()

        # Write-mutation refusal at intake
        mut_res = client.post(
            "/api/v1/agent/query",
            json={"query": "Close ticket INC-001 immediately"},
        )
        assert mut_res.status_code == 200
        mut_data = mut_res.json()
        assert mut_data["is_refusal"] is True
        assert mut_data["node_sequence"] == ["intake", "refusal"]
        assert "read-only" in mut_data["answer"].lower()

    def test_t043_query_endpoint_whitespace_query_halts_at_intake_refusal(self) -> None:
        """T043: Whitespace-only query halts at intake -> refusal without invoking retrieval or generation."""
        res = client.post(
            "/api/v1/agent/query",
            json={"query": "    "},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is True
        assert data["sources"] == []
        assert data["node_sequence"] == ["intake", "refusal"]

    def test_t043_trace_endpoint_returns_404_when_trace_not_found(self) -> None:
        """T043: GET /api/v1/agent/trace/{trace_id} returns HTTP 404 with sanitized payload when trace is missing."""
        res = client.get("/api/v1/agent/trace/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        body = res.json()
        assert "detail" in body
        assert "error_code" in body
        assert body["error_code"] == "TRACE_NOT_FOUND"

    def test_t043_defensive_error_shielding_prevents_stack_trace_and_secret_leaks(
        self,
    ) -> None:
        """T043: Synthetic internal faults must return HTTP 500 SanitizedErrorResponse with zero stack trace or path leaks."""

        class CrashingAgentService(SupportAgentServicePort):
            def query(self, request: AgentQueryRequest) -> AgentQueryResult:
                raise RuntimeError(
                    "FATAL: Traceback at /srv/internal/secret_db_connection.py line 99: "
                    "password=super_secret_admin_pass_123"
                )

            def get_trace(self, trace_id: str) -> AgentTrace:
                raise RuntimeError("Internal registry corruption at /srv/internal/trace.py")

            def get_checkpoints(self, thread_id: str) -> List[AgentCheckpoint]:
                return []

            def get_health(self) -> Dict[str, Any]:
                return {
                    "status": "healthy",
                    "compiled": True,
                    "nodes": [
                        "intake",
                        "ticket_tool",
                        "inventory_tool",
                        "retrieval",
                        "tool_fallback",
                        "generation",
                        "refusal",
                    ],
                    "checkpointer": "MemorySaver",
                }

        app.dependency_overrides[get_support_agent_service] = lambda: CrashingAgentService()
        try:
            res = client.post(
                "/api/v1/agent/query",
                json={"query": "What is TrackFlow's standard return window?"},
            )
            assert res.status_code == 500
            raw_text = res.text
            assert "Traceback" not in raw_text
            assert "secret_db_connection.py" not in raw_text
            assert "super_secret_admin_pass_123" not in raw_text
            assert "line 99" not in raw_text

            body = res.json()
            assert body["error_code"] == "INTERNAL_WORKFLOW_ERROR"
            assert "An internal error occurred" in body["detail"]
        finally:
            app.dependency_overrides.pop(get_support_agent_service, None)

    def test_t043_validation_error_on_empty_string_query_returns_422(self) -> None:
        """T043: Empty string query (`""`) returns HTTP 422 without stack traces."""
        res = client.post("/api/v1/agent/query", json={"query": ""})
        assert res.status_code == 422
        assert "Traceback" not in res.text

    def test_t043_vector_store_unavailable_returns_http_503(self) -> None:
        """T043: When vector store raises KnowledgeBaseUnavailableException, endpoint returns HTTP 503."""

        class UnavailableAgentService(SupportAgentServicePort):
            def query(self, request: AgentQueryRequest) -> AgentQueryResult:
                raise KnowledgeBaseUnavailableException(
                    "Vector store cluster temporarily unavailable."
                )

            def get_trace(self, trace_id: str) -> AgentTrace:
                raise KnowledgeBaseUnavailableException("Unavailable")

            def get_checkpoints(self, thread_id: str) -> List[AgentCheckpoint]:
                return []

            def get_health(self) -> Dict[str, Any]:
                return {}

        app.dependency_overrides[get_support_agent_service] = (
            lambda: UnavailableAgentService()
        )
        try:
            res = client.post(
                "/api/v1/agent/query",
                json={"query": "What is the standard return window?"},
            )
            assert res.status_code == 503
            body = res.json()
            assert body["error"] == "SERVICE_UNAVAILABLE"
        finally:
            app.dependency_overrides.pop(get_support_agent_service, None)
