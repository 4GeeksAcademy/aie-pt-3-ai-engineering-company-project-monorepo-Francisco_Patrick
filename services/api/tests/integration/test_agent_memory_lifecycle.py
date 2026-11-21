"""Integration tests for Support Agent Memory lifecycle (T011, T018, T026).

Covers:
- US1 (T011): Single-call candidate proposal generation on operator corrections
  (`test_single_call_carrier_proposal`) and dismissal of non-memorable interactions.
- US2 (T018): Explicit intent classification (`approve`, `reject`, `edit`, `unrelated_or_ambiguous`),
  safe default discard on topic shifts (`test_safe_default_discard_on_topic_shift`),
  single pending proposal queue enforcement, and same-turn multi-intent query continuation.
- US3 (T026): Cross-session memory recall (`test_approve_and_cross_session_recall`)
  applying stored operational rules in fresh sessions.
"""

from typing import Any, Dict, List, Optional

from application.services.memory_guardrails import MemoryGuardrailValidator
from application.services.memory_service import (
    AgentMemoryService,
    UserIntentClassifier,
)
from application.services.support_agent_service import SupportAgentService
from application.services.trace_registry import TraceRegistry
from domain.agent.entities import (
    AgentQueryRequest,
    InventoryRecordDTO,
    InventoryToolInput,
    InventoryToolOutput,
    KnowledgeChunk,
    RetrievedContext,
    TicketRecordDTO,
    TicketToolInput,
    TicketToolOutput,
)
from domain.agent.ports import InventoryStockToolPort, SupportTicketToolPort
from domain.knowledge.entities import generate_chunk_id
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)
from infrastructure.persistence.tinydb.agent_memory_repository import (
    TinyDBAgentMemoryRepository,
)
from infrastructure.persistence.tinydb.memory_audit_log_repository import (
    TinyDBMemoryAuditLogRepository,
)


class _StubEmbedder(EmbeddingServicePort):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.1] * 384


class _StubVectorStore(VectorStorePort):
    def __init__(self) -> None:
        chunk = KnowledgeChunk(
            id=generate_chunk_id("sla-delivery", 0),
            company="trackflow",
            source_document="sla-delivery",
            section="Regional Carrier Dispatch & SLA Tiers",
            language="en",
            chunk_index=0,
            text="Standard regional deliveries in Spain and the US use approved national and regional carriers.",
        )
        self._ctx = RetrievedContext(chunk=chunk, similarity_score=0.88, rank=1)
        self.upsert_calls = 0

    def ensure_collection(self) -> None:
        pass

    def upsert_chunks(self, chunks: List[KnowledgeChunk]) -> Dict[str, int]:
        self.upsert_calls += 1
        return {"added": len(chunks), "updated": 0, "total": len(chunks)}

    def search(
        self,
        query_vector: List[float],
        top_k: int = 3,
        language: Optional[str] = None,
    ) -> List[RetrievedContext]:
        return [self._ctx][:top_k]

    def get_health_status(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "collection_name": "trackflow_knowledge",
            "indexed_points_count": 12,
            "vector_dimensions": 384,
        }


class _StubLLM(LLMGenerationPort):
    def generate_grounded_answer(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
    ) -> str:
        ctx_text = contexts[0].chunk.text if contexts else ""
        src_doc = contexts[0].chunk.source_document if contexts else "sla-delivery"
        return f"Per {src_doc}, {ctx_text}"


class _StubTicketTool(SupportTicketToolPort):
    def query_tickets(self, tool_input: TicketToolInput) -> TicketToolOutput:
        rec = TicketRecordDTO(
            id=tool_input.ticket_id or "INC-001",
            title="Delayed shipment in Los Angeles",
            description="Port congestion delay.",
            status="open",
            category="delay",
            origin="carrier",
            branch=tool_input.branch or "los_angeles",
            created_at="2026-11-20T09:00:00+00:00",
            updated_at="2026-11-21T09:00:00+00:00",
        )
        return TicketToolOutput(
            status="success",
            records=[rec],
            total_matched=1,
            latency_ms=1.5,
            queried_criteria=tool_input.to_dict(),
        )


class _StubInventoryTool(InventoryStockToolPort):
    def query_inventory(self, tool_input: InventoryToolInput) -> InventoryToolOutput:
        sku = (tool_input.sku or "SKU-401").upper()
        rec = InventoryRecordDTO(
            id=401,
            sku=sku,
            name="Packaging Box XL",
            description="Heavy duty shipping carton",
            stock=320,
            min_threshold=50,
            is_low_stock=False,
            warehouse_id="zaragoza",
        )
        return InventoryToolOutput(
            status="success",
            records=[rec],
            total_matched=1,
            latency_ms=1.2,
            queried_criteria=tool_input.to_dict(),
        )


def _build_test_agent_service() -> tuple[
    SupportAgentService,
    TinyDBAgentMemoryRepository,
    TinyDBMemoryAuditLogRepository,
    _StubVectorStore,
]:
    memory_repo = TinyDBAgentMemoryRepository()
    audit_repo = TinyDBMemoryAuditLogRepository()
    memory_service = AgentMemoryService(
        memory_repository=memory_repo,
        audit_repository=audit_repo,
        guardrail_validator=MemoryGuardrailValidator(),
        intent_classifier=UserIntentClassifier(),
    )
    vector_store = _StubVectorStore()
    agent_service = SupportAgentService(
        vector_store=vector_store,
        embedding_service=_StubEmbedder(),
        llm_generator=_StubLLM(),
        ticket_tool=_StubTicketTool(),
        inventory_tool=_StubInventoryTool(),
        trace_registry=TraceRegistry(),
        memory_service=memory_service,
    )
    return agent_service, memory_repo, audit_repo, vector_store


class TestAgentMemoryLifecycleIntegration:
    """End-to-end integration tests for US1, US2, and US3 memory lifecycle."""

    def test_single_call_carrier_proposal(self) -> None:
        """Scenario 1 (US1): Carrier route correction generates response + pending proposal with 0 DB writes."""
        agent_service, memory_repo, audit_repo, vector_store = _build_test_agent_service()

        result = agent_service.query(
            AgentQueryRequest(
                query="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
                thread_id="session_zaragoza_1",
            )
        )

        assert result.is_refusal is False
        assert "Would you like me to remember this rule for future sessions?" in result.answer
        assert result.memory_proposal is not None
        assert result.memory_proposal.category == "carrier_rule"
        assert result.memory_proposal.target_entity == "SEUR"
        assert result.memory_proposal.country_code == "ES"
        assert result.memory_proposal.status == "pending"

        # Deferred persistence: zero records in persistent storage until confirmation
        assert len(memory_repo.search_memories()) == 0
        assert vector_store.upsert_calls == 0

        # Audit log recorded 'proposed' event
        audit_entries = audit_repo.list_entries(
            proposal_id=result.memory_proposal.proposal_id
        )
        assert len(audit_entries) == 1
        assert audit_entries[0].event_type == "proposed"
        assert audit_entries[0].resulting_action == "proposal_created"

    def test_non_memorable_queries_generate_no_proposal(self) -> None:
        """US1 Scenario 4: Ephemeral tracking queries, closings, and translations generate no proposal."""
        agent_service, memory_repo, _, _ = _build_test_agent_service()

        for idx, query_text in enumerate(
            [
                "Where is package XJ4471?",
                "Perfect, that resolved it.",
                "Translate this customer email to English.",
            ]
        ):
            res = agent_service.query(
                AgentQueryRequest(
                    query=query_text,
                    thread_id=f"session_ephemeral_{idx}",
                )
            )
            assert res.memory_proposal is None
            assert "Would you like me to remember" not in res.answer

        assert len(memory_repo.search_memories()) == 0

    def test_approve_and_cross_session_recall(self) -> None:
        """Scenario 2 (US2 & US3): Explicit approval persists rule and fresh session recalls it."""
        agent_service, memory_repo, audit_repo, vector_store = _build_test_agent_service()

        # Turn 1: Operator provides carrier correction in session 1
        turn1 = agent_service.query(
            AgentQueryRequest(
                query="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
                thread_id="session_zaragoza_approve",
            )
        )
        assert turn1.memory_proposal is not None
        proposal_id = turn1.memory_proposal.proposal_id
        assert len(memory_repo.search_memories()) == 0

        # Turn 2: Operator explicitly approves the pending proposal
        turn2 = agent_service.query(
            AgentQueryRequest(
                query="Yes, please remember that rule for SEUR.",
                thread_id="session_zaragoza_approve",
            )
        )
        assert turn2.is_refusal is False
        # Each turn gets a unique trace_id while sharing thread_id for multi-turn proposal resolution
        assert turn1.trace_id != turn2.trace_id
        assert agent_service.get_trace(turn1.trace_id).query.startswith("SEUR no longer")
        assert agent_service.get_trace(turn2.trace_id).query.startswith("Yes, please remember")
        stored_memories = memory_repo.search_memories(
            category="carrier_rule", target_entity="SEUR", country_code="ES"
        )
        assert len(stored_memories) == 1
        assert "rural Zaragoza" in stored_memories[0].content or "SEUR" in stored_memories[0].content

        # Verify audit log recorded 'approved' with resulting_action='memory_persisted'
        approved_logs = audit_repo.list_entries(
            proposal_id=proposal_id, event_type="approved"
        )
        assert len(approved_logs) == 1
        assert approved_logs[0].resulting_action == "memory_persisted"

        # Turn 3: Fresh session queries carrier selection for rural Zaragoza
        turn3 = agent_service.query(
            AgentQueryRequest(
                query="What carrier should I assign for rural shipments in Zaragoza?",
                thread_id="session_new_2",
            )
        )
        assert turn3.is_refusal is False
        assert len(turn3.recalled_memories) >= 1
        assert any("SEUR" in mem for mem in turn3.recalled_memories)
        assert "SEUR" in turn3.answer
        assert "local" in turn3.answer.lower()
        assert "agent_memory" in turn3.sources_consulted
        assert vector_store.upsert_calls == 0

    def test_safe_default_discard_on_topic_shift(self) -> None:
        """Scenario 3 (US2): Topic shift discards pending proposal, leaves DB empty, and answers residual query."""
        agent_service, memory_repo, audit_repo, _ = _build_test_agent_service()

        # Stage active proposal
        turn1 = agent_service.query(
            AgentQueryRequest(
                query="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
                thread_id="session_topic_shift",
            )
        )
        assert turn1.memory_proposal is not None
        proposal_id = turn1.memory_proposal.proposal_id

        # Respond with an unrelated inventory query
        turn2 = agent_service.query(
            AgentQueryRequest(
                query="Can you check current stock for SKU-401?",
                thread_id="session_topic_shift",
            )
        )
        # Proposal discarded, 0 records written
        assert len(memory_repo.search_memories()) == 0
        discard_logs = audit_repo.list_entries(
            proposal_id=proposal_id, event_type="discarded"
        )
        assert len(discard_logs) == 1
        assert discard_logs[0].resulting_action == "proposal_discarded"

        # Residual query was processed in the exact same turn via inventory_tool
        assert "inventory_tool" in turn2.sources_consulted
        assert "SKU-401" in turn2.answer
        assert "320 units" in turn2.answer

    def test_edit_flow_and_multi_intent_same_turn_continuation(self) -> None:
        """US2 Scenarios 4 & 5 & FR-015: Edit updates pending proposal; multi-intent approves and answers new query."""
        agent_service, memory_repo, audit_repo, _ = _build_test_agent_service()

        # 1. Generate initial proposal
        turn1 = agent_service.query(
            AgentQueryRequest(
                query="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
                thread_id="session_edit_flow",
            )
        )
        assert turn1.memory_proposal is not None
        proposal_id = turn1.memory_proposal.proposal_id

        # 2. User edits the rule
        turn2 = agent_service.query(
            AgentQueryRequest(
                query="Remember it, but only for packages over 5kg",
                thread_id="session_edit_flow",
            )
        )
        # Still 0 persisted memories (awaiting confirmation of edited proposal)
        assert len(memory_repo.search_memories()) == 0
        assert turn2.memory_proposal is not None
        assert "5kg" in turn2.memory_proposal.summary
        edit_logs = audit_repo.list_entries(
            proposal_id=proposal_id, event_type="edited"
        )
        assert len(edit_logs) == 1

        # 3. User approves edited proposal AND asks an inventory question in the same turn (FR-015)
        turn3 = agent_service.query(
            AgentQueryRequest(
                query="Yes save that, and what is the current stock of SKU-401?",
                thread_id="session_edit_flow",
            )
        )
        # Memory committed with edited content
        stored = memory_repo.search_memories(target_entity="SEUR")
        assert len(stored) == 1
        assert "5kg" in stored[0].content
        # And inventory question answered in same turn
        assert "inventory_tool" in turn3.sources_consulted
        assert "SKU-401" in turn3.answer

    def test_single_pending_proposal_queue_limit_suppresses_secondary_candidates(self) -> None:
        """FR-012: At most one memory proposal may be pending per thread; secondary candidates are suppressed."""
        _, memory_repo, audit_repo, _ = _build_test_agent_service()
        memory_service = AgentMemoryService(
            memory_repository=memory_repo,
            audit_repository=audit_repo,
            guardrail_validator=MemoryGuardrailValidator(),
            intent_classifier=UserIntentClassifier(),
        )

        p1, _ = memory_service.evaluate_turn_for_proposal(
            user_message="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
            base_answer="Answer 1",
            thread_id="queue-thread-1",
        )
        assert p1 is not None

        # Before p1 is resolved, another candidate evaluation on the same thread must preserve p1 and not create p2
        p2, _ = memory_service.evaluate_turn_for_proposal(
            user_message="FedEx no longer covers rural Los Angeles; local carriers must be used starting this month.",
            base_answer="Answer 2",
            thread_id="queue-thread-1",
        )
        assert p2 is not None
        assert p2.proposal_id == p1.proposal_id
        assert p2.target_entity == "SEUR"
        assert len(audit_repo.list_entries(event_type="proposed")) == 1

    def test_rest_api_endpoints_for_proposals_feedback_carrier_profile_and_audit_logs(
        self,
    ) -> None:
        """T015, T024, T029, T037: Verify FastAPI endpoints for query proposal, feedback, carrier profile, and audit logs."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from presentation.api.v1 import agent as agent_router
        from presentation.api.v1 import memory as memory_router
        from presentation.dependencies import (
            get_agent_memory_service_dep,
            get_support_agent_service,
        )

        agent_service, _, _, _ = _build_test_agent_service()
        memory_service = agent_service.memory_service

        test_app = FastAPI()
        test_app.include_router(agent_router.router, prefix="/api/v1/agent")
        test_app.include_router(memory_router.router, prefix="/api/v1/memory")
        test_app.include_router(memory_router.router, prefix="/api/v1/agent/memory")
        test_app.dependency_overrides[get_support_agent_service] = lambda: agent_service
        test_app.dependency_overrides[get_agent_memory_service_dep] = (
            lambda: memory_service
        )

        client = TestClient(test_app)

        # 1. POST /api/v1/agent/query with carrier correction
        q_resp = client.post(
            "/api/v1/agent/query",
            json={
                "query": "SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
                "thread_id": "rest-thread-1",
            },
        )
        assert q_resp.status_code == 200
        q_data = q_resp.json()
        assert q_data["memory_proposal"] is not None
        proposal_id = q_data["memory_proposal"]["proposal_id"]
        assert q_data["memory_proposal"]["target_entity"] == "SEUR"

        # 2. GET /api/v1/agent/memory/proposals/pending
        pend_resp = client.get(
            "/api/v1/agent/memory/proposals/pending",
            params={"thread_id": "rest-thread-1"},
        )
        assert pend_resp.status_code == 200
        assert pend_resp.json()["proposal"]["proposal_id"] == proposal_id

        # 3. POST /api/v1/agent/proposals/{proposal_id}/feedback (approve)
        fb_resp = client.post(
            f"/api/v1/agent/proposals/{proposal_id}/feedback",
            json={"action": "approve", "operator_id": "op_zaragoza_1"},
        )
        assert fb_resp.status_code == 200
        fb_data = fb_resp.json()
        assert fb_data["status"] == "approved"
        assert fb_data["resulting_action"] == "memory_persisted"
        assert fb_data["committed_memory_id"] is not None

        # 4. GET /api/v1/memory/carriers/SEUR/ES and /api/v1/agent/memory/carriers/SEUR?country_code=ES
        prof_path_resp = client.get("/api/v1/memory/carriers/SEUR/ES")
        assert prof_path_resp.status_code == 200
        prof_data = prof_path_resp.json()
        assert prof_data["carrier"] == "SEUR"
        assert prof_data["country_code"] == "ES"
        assert len(prof_data["active_rules"]) == 1

        prof_query_resp = client.get(
            "/api/v1/agent/memory/carriers/SEUR", params={"country_code": "ES"}
        )
        assert prof_query_resp.status_code == 200
        assert prof_query_resp.json()["active_rules"] == prof_data["active_rules"]

        # 5. GET /api/v1/memory/audit-logs
        logs_resp = client.get("/api/v1/memory/audit-logs")
        assert logs_resp.status_code == 200
        logs_data = logs_resp.json()
        assert len(logs_data) >= 2
        assert {entry["event_type"] for entry in logs_data} >= {"proposed", "approved"}

    def test_ambiguous_non_question_remark_discards_proposal_without_false_positive_residual_query(
        self,
    ) -> None:
        """Ambiguous 12+ char non-question remark ('I need to think about whether to save that') discards proposal cleanly without triggering RAG/tool execution as a residual query."""
        agent_service, memory_repo, audit_repo, _ = _build_test_agent_service()

        turn1 = agent_service.query(
            AgentQueryRequest(
                query="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
                thread_id="session_ambiguous_remark",
            )
        )
        assert turn1.memory_proposal is not None
        proposal_id = turn1.memory_proposal.proposal_id

        turn2 = agent_service.query(
            AgentQueryRequest(
                query="I need to think about whether to save that.",
                thread_id="session_ambiguous_remark",
            )
        )
        assert turn2.is_refusal is False
        assert len(memory_repo.search_memories()) == 0
        # Pure proposal discard turn: should not consult RAG or operational tools for the hesitation remark
        assert turn2.sources_consulted == []
        discard_logs = audit_repo.list_entries(
            proposal_id=proposal_id, event_type="discarded"
        )
        assert len(discard_logs) == 1
        assert discard_logs[0].resulting_action == "proposal_discarded"

