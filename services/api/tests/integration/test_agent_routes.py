"""Integration tests for Support Agent FastAPI endpoints (T030, T031, T032).

Verifies:
- T030: `POST /api/v1/agent/query` and `POST /agent/query` for standard policy grounded answers
  (`node_sequence: ["intake", "retrieval", "generation"]`) and out-of-scope refusal
  (`node_sequence: ["intake", "retrieval", "refusal"]`, `is_refusal: true`, `sources: []`).
- T031: `GET /api/v1/agent/trace/{trace_id}` (200 OK with step latencies and 404 Not Found for missing ID)
  and `GET /api/v1/agent/health` (200 OK reporting compiled graph and checkpointer).
- T032: Defensive error shielding and zero raw stack trace or internal file path leakage under
  synthetic runtime faults and validation errors.
"""

import os
from typing import Any, Dict, List

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-agent-integration-tests")
os.environ["QDRANT_URL"] = ""
os.environ["QDRANT_HOST"] = ""
os.environ["QDRANT_PATH"] = ""

from domain.agent.entities import AgentCheckpoint, AgentQueryRequest, AgentQueryResult, AgentTrace  # noqa: E402
from domain.agent.ports import SupportAgentServicePort  # noqa: E402
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException  # noqa: E402
from main import app  # noqa: E402
from presentation.dependencies import get_support_agent_service  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


class TestSupportAgentRoutesIntegration:
    """End-to-end HTTP integration test suite for `/api/v1/agent/*` and `/agent/*`."""

    def test_t031_health_endpoint_v1_and_legacy_alias(self) -> None:
        """T031: GET /api/v1/agent/health and GET /agent/health must report compiled state and nodes."""
        for path in ("/api/v1/agent/health", "/agent/health"):
            res = client.get(path)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "healthy"
            assert data["compiled"] is True
            assert data["nodes"] == ["intake", "retrieval", "generation", "refusal"]
            assert data["checkpointer"] == "MemorySaver"

    def test_t030_query_endpoint_standard_policy_and_trace_retrieval(self) -> None:
        """T030, T031: POST /api/v1/agent/query returns grounded answer, citations, trace_id, and node_sequence, and GET /trace/{trace_id} returns step breakdown."""
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

    def test_t030_query_endpoint_honest_refusal_path(self) -> None:
        """T030: POST /api/v1/agent/query on out-of-scope topic routes to refusal without generation."""
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

        # Verify trace reflects refusal path
        trace_res = client.get(f"/api/v1/agent/trace/{data['trace_id']}")
        assert trace_res.status_code == 200
        trace_data = trace_res.json()
        assert trace_data["node_sequence"] == ["intake", "retrieval", "refusal"]
        assert "generation" not in trace_data["step_latencies"]
        assert trace_data["is_refusal"] is True
        assert trace_data["source_count"] == 0

    def test_t030_query_endpoint_whitespace_query_halts_at_intake_refusal(self) -> None:
        """T030: Whitespace-only query halts at intake -> refusal without invoking retrieval or generation."""
        res = client.post(
            "/api/v1/agent/query",
            json={"query": "    "},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is True
        assert data["sources"] == []
        assert data["node_sequence"] == ["intake", "refusal"]

    def test_t031_trace_endpoint_returns_404_when_trace_not_found(self) -> None:
        """T031: GET /api/v1/agent/trace/{trace_id} returns HTTP 404 with sanitized payload when trace is missing."""
        res = client.get("/api/v1/agent/trace/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        body = res.json()
        assert "detail" in body
        assert "error_code" in body
        assert body["error_code"] == "TRACE_NOT_FOUND"

    def test_t032_defensive_error_shielding_prevents_stack_trace_and_secret_leaks(
        self,
    ) -> None:
        """T032: Synthetic internal faults must return HTTP 500 SanitizedErrorResponse with zero stack trace or path leaks."""

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
                    "nodes": ["intake", "retrieval", "generation", "refusal"],
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

    def test_t032_validation_error_on_empty_string_query_returns_422(self) -> None:
        """T032: Empty string query (`""`) returns HTTP 422 without stack traces."""
        res = client.post("/api/v1/agent/query", json={"query": ""})
        assert res.status_code == 422
        assert "Traceback" not in res.text

    def test_t032_vector_store_unavailable_returns_http_503(self) -> None:
        """T032: When vector store raises KnowledgeBaseUnavailableException, endpoint returns HTTP 503."""

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
