"""Integration tests verifying strict storage isolation between Agent Memory and Qdrant (T025).

Verifies Quickstart Scenario 6, Monorepo Constitution Principle VII, FR-006, and SC-005:
- Across 10 memory proposals (5 approved, 5 discarded) and cross-session memory recalls,
  the Qdrant static knowledge base (`trackflow_knowledge`) receives zero write, upsert,
  delete, or mutation calls, and its indexed point count delta is strictly 0.
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
    InventoryToolInput,
    InventoryToolOutput,
    KnowledgeChunk,
    RetrievedContext,
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


class _ReadOnlyTrackedVectorStore(VectorStorePort):
    """Spy VectorStorePort verifying zero write operations occur during memory lifecycles."""

    def __init__(self, initial_count: int = 24) -> None:
        self._initial_count = initial_count
        self._current_count = initial_count
        self.write_operations: List[str] = []
        chunk = KnowledgeChunk(
            id=generate_chunk_id("returns-policy", 0),
            company="trackflow",
            source_document="returns-policy",
            section="Standard Return Policy",
            language="en",
            chunk_index=0,
            text="TrackFlow provides a 30-day return window for standard orders.",
        )
        self._ctx = RetrievedContext(chunk=chunk, similarity_score=0.89, rank=1)

    def ensure_collection(self) -> None:
        pass

    def upsert_chunks(self, chunks: List[KnowledgeChunk]) -> Dict[str, int]:
        self.write_operations.append("upsert_chunks")
        self._current_count += len(chunks)
        raise AssertionError(
            "Violation of SC-005 / Principle VII: Qdrant static knowledge must never be mutated by agent memory!"
        )

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
            "indexed_points_count": self._current_count,
            "vector_dimensions": 384,
        }


class _StubEmbedder(EmbeddingServicePort):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.1] * 384


class _StubLLM(LLMGenerationPort):
    def generate_grounded_answer(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
    ) -> str:
        return "Standard 30-day return window applies per returns-policy."


class _NoOpTicketTool(SupportTicketToolPort):
    def query_tickets(self, tool_input: TicketToolInput) -> TicketToolOutput:
        return TicketToolOutput(status="success", records=[], total_matched=0, latency_ms=0.1)


class _NoOpInventoryTool(InventoryStockToolPort):
    def query_inventory(self, tool_input: InventoryToolInput) -> InventoryToolOutput:
        return InventoryToolOutput(status="success", records=[], total_matched=0, latency_ms=0.1)


class TestMemoryStorageIsolation:
    """Integration test suite proving 100% read-only Qdrant isolation (T025, SC-005)."""

    def test_zero_qdrant_writes_across_10_memory_proposal_lifecycles(self) -> None:
        """Scenario 6: 10 proposals (5 approved, 5 discarded) produce delta=0 in Qdrant trackflow_knowledge."""
        vector_store = _ReadOnlyTrackedVectorStore(initial_count=24)
        memory_repo = TinyDBAgentMemoryRepository()
        audit_repo = TinyDBMemoryAuditLogRepository()
        memory_service = AgentMemoryService(
            memory_repository=memory_repo,
            audit_repository=audit_repo,
            guardrail_validator=MemoryGuardrailValidator(),
            intent_classifier=UserIntentClassifier(),
        )
        agent_service = SupportAgentService(
            vector_store=vector_store,
            embedding_service=_StubEmbedder(),
            llm_generator=_StubLLM(),
            ticket_tool=_NoOpTicketTool(),
            inventory_tool=_NoOpInventoryTool(),
            trace_registry=TraceRegistry(),
            memory_service=memory_service,
        )

        initial_qdrant_count = vector_store.get_health_status()["indexed_points_count"]
        assert initial_qdrant_count == 24

        carriers = [
            ("SEUR", "Zaragoza"),
            ("GLS", "Zaragoza"),
            ("Correos", "Zaragoza"),
            ("DHL", "Zaragoza"),
            ("MRW", "Zaragoza"),
            ("FedEx", "Los Angeles"),
            ("UPS", "Los Angeles"),
            ("USPS", "Los Angeles"),
            ("OnTrac", "Los Angeles"),
            ("LaserShip", "Los Angeles"),
        ]

        for idx, (carrier, region) in enumerate(carriers):
            thread_id = f"isolation_thread_{idx}"
            # Generate proposal
            prop_res = agent_service.query(
                AgentQueryRequest(
                    query=f"{carrier} no longer covers the rural {region} zone; local carriers must be used starting this month.",
                    thread_id=thread_id,
                )
            )
            assert prop_res.memory_proposal is not None

            if idx < 5:
                # Approve first 5
                agent_service.query(
                    AgentQueryRequest(
                        query=f"Yes, please remember that rule for {carrier}.",
                        thread_id=thread_id,
                    )
                )
            else:
                # Discard/reject remaining 5
                agent_service.query(
                    AgentQueryRequest(
                        query="No, do not save that rule.",
                        thread_id=thread_id,
                    )
                )

        post_qdrant_count = vector_store.get_health_status()["indexed_points_count"]
        delta = post_qdrant_count - initial_qdrant_count

        assert delta == 0
        assert vector_store.write_operations == []
        assert len(memory_repo.search_memories(active_only=True)) == 5
        assert len(audit_repo.list_entries(limit=100)) == 20
