"""Unit and workflow integration tests for Support Agent with LangGraph (T010, T016, T022, T027, T032, T035).

Verifies:
- US1 (T010): Single-responsibility nodes (`intake_node`, `retrieval_node`, `generation_node`),
  standard policy RAG reasoning workflow (`intake` -> `retrieval` -> `generation`), and build-time
  graph compilation validation.
- US2 (T016): Autonomous ticket intent classification (`classify_and_plan_query`),
  `ticket_tool_node`, and hybrid canonical ordering (`ticket_tool` -> `retrieval` -> `generation`).
- US3 (T022): `tool_fallback_node`, `route_after_ticket_tool`, `route_after_tool_fallback`,
  pure tool fallback termination, and hybrid graceful partial answers.
- US4 (T027): Autonomous inventory intent routing, `inventory_tool_node`,
  `route_after_inventory_tool`, and multi-tool canonical sequencing (`ticket_tool` -> `inventory_tool` -> `retrieval`).
- US5 (T032): Empty-query early termination, write/mutation guardrail refusal at intake,
  and `< 0.62` similarity policy refusal.
- US6 (T035): Multi-source `AgentTrace` recording (`sources_consulted`, `fallback_triggered`,
  `tool_calls`, `step_latencies`) and `MemorySaver` checkpoint inspection.
"""

from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
import pytest

from application.services.agent_workflow import (
    REQUIRED_WORKFLOW_NODES,
    build_support_agent_graph,
    classify_and_plan_query,
    compile_and_validate_graph,
    detect_mutation_attempt,
    generation_node,
    intake_node,
    inventory_tool_node,
    refusal_node,
    retrieval_node,
    route_after_intake,
    route_after_inventory_tool,
    route_after_retrieval,
    route_after_ticket_tool,
    route_after_tool_fallback,
    ticket_tool_node,
    tool_fallback_node,
)
from application.services.knowledge_service import STANDARD_REFUSAL_MESSAGE
from application.services.support_agent_service import SupportAgentService
from application.services.trace_registry import TraceRegistry
from domain.agent.entities import (
    AgentQueryRequest,
    AgentState,
    InventoryRecordDTO,
    InventoryToolInput,
    InventoryToolOutput,
    KnowledgeChunk,
    RetrievedContext,
    TicketRecordDTO,
    TicketToolInput,
    TicketToolOutput,
    ToolCallStatus,
)
from domain.agent.exceptions import GraphCompilationError, TraceNotFoundError
from domain.agent.ports import InventoryStockToolPort, SupportTicketToolPort
from domain.knowledge.entities import generate_chunk_id
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)


class StubEmbeddingService(EmbeddingServicePort):
    """Deterministic stub embedding service tracking invocation counts."""

    def __init__(self) -> None:
        """Initialize call counter."""
        self.embed_query_calls = 0

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Return 384-dim vectors for documents."""
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        """Return 384-dim vector for query and increment counter."""
        self.embed_query_calls += 1
        return [0.1] * 384


class StubVectorStore(VectorStorePort):
    """Configurable stub vector store tracking search calls."""

    def __init__(self, candidates: List[RetrievedContext]) -> None:
        """Initialize with preset RetrievedContext list."""
        self._candidates = candidates
        self.search_calls = 0

    def ensure_collection(self) -> None:
        """No-op collection initialization."""

    def upsert_chunks(self, chunks: List[KnowledgeChunk]) -> Dict[str, int]:
        """Return stub upsert summary."""
        return {"added": len(chunks), "updated": 0, "total": len(chunks)}

    def search(
        self,
        query_vector: List[float],
        top_k: int = 3,
        language: Optional[str] = None,
    ) -> List[RetrievedContext]:
        """Return up to top_k candidates and record search invocation."""
        self.search_calls += 1
        return self._candidates[:top_k]

    def get_health_status(self) -> Dict[str, Any]:
        """Return healthy stub status."""
        return {
            "status": "healthy",
            "collection_name": "trackflow_knowledge",
            "indexed_points_count": 12,
            "vector_dimensions": 384,
        }


class StubLLMGenerator(LLMGenerationPort):
    """Stub LLM generator recording invocations and input contexts."""

    def __init__(self) -> None:
        """Initialize call tracking."""
        self.generate_calls = 0
        self.last_contexts: List[RetrievedContext] = []

    def generate_grounded_answer(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
    ) -> str:
        """Synthesize grounded answer strictly from pre-retrieved contexts."""
        self.generate_calls += 1
        self.last_contexts = list(contexts)
        return (
            f"TrackFlow offers a 30-day return window from delivery per "
            f"{contexts[0].chunk.source_document}. {contexts[0].chunk.text}"
        )


class StubTicketTool(SupportTicketToolPort):
    """Configurable stub SupportTicketToolPort for workflow unit tests."""

    def __init__(
        self,
        records_by_id: Optional[Dict[str, TicketRecordDTO]] = None,
        forced_status: Optional[ToolCallStatus] = None,
        forced_error: Optional[str] = None,
    ) -> None:
        """Initialize stub ticket tool."""
        self.records_by_id = records_by_id or {
            "INC-001": TicketRecordDTO(
                id="INC-001",
                title="Delayed pallet shipment to Zaragoza",
                description="Pallet delayed at regional hub.",
                status="open",
                category="delay",
                origin="warehouse",
                branch="zaragoza",
                created_at="2026-11-17T09:00:00+00:00",
                updated_at="2026-11-18T10:30:00+00:00",
            )
        }
        self.forced_status = forced_status
        self.forced_error = forced_error
        self.calls: List[TicketToolInput] = []

    def query_tickets(self, tool_input: TicketToolInput) -> TicketToolOutput:
        """Return configured TicketToolOutput."""
        self.calls.append(tool_input)
        if self.forced_status is not None:
            return TicketToolOutput(
                status=self.forced_status,
                records=[],
                total_matched=0,
                latency_ms=4.2,
                error_message=self.forced_error or f"Forced {self.forced_status}",
                queried_criteria=tool_input.to_dict(),
            )

        if tool_input.ticket_id:
            rec = self.records_by_id.get(tool_input.ticket_id.upper())
            if rec is None:
                return TicketToolOutput(
                    status="not_found",
                    records=[],
                    total_matched=0,
                    latency_ms=1.5,
                    error_message=f"No incident record matched ticket_id='{tool_input.ticket_id}'.",
                    queried_criteria=tool_input.to_dict(),
                )
            return TicketToolOutput(
                status="success",
                records=[rec],
                total_matched=1,
                latency_ms=2.1,
                queried_criteria=tool_input.to_dict(),
            )

        all_recs = list(self.records_by_id.values())
        return TicketToolOutput(
            status="success" if all_recs else "not_found",
            records=all_recs[:20],
            total_matched=len(all_recs),
            latency_ms=2.5,
            queried_criteria=tool_input.to_dict(),
        )


class StubInventoryTool(InventoryStockToolPort):
    """Configurable stub InventoryStockToolPort for workflow unit tests."""

    def __init__(
        self,
        records_by_sku: Optional[Dict[str, InventoryRecordDTO]] = None,
        forced_status: Optional[ToolCallStatus] = None,
    ) -> None:
        """Initialize stub inventory tool."""
        self.records_by_sku = records_by_sku or {
            "TF-1001": InventoryRecordDTO(
                id=1,
                sku="TF-1001",
                name="Industrial Thermal Shipping Label Roll",
                description="Industrial Thermal Shipping Label Roll (Warehouse: zaragoza)",
                stock=145,
                min_threshold=20,
                is_low_stock=False,
                warehouse_id="zaragoza",
            )
        }
        self.forced_status = forced_status
        self.calls: List[InventoryToolInput] = []

    def query_inventory(self, tool_input: InventoryToolInput) -> InventoryToolOutput:
        """Return configured InventoryToolOutput."""
        self.calls.append(tool_input)
        if self.forced_status is not None:
            return InventoryToolOutput(
                status=self.forced_status,
                records=[],
                total_matched=0,
                latency_ms=3.8,
                error_message=f"Forced {self.forced_status}",
                queried_criteria=tool_input.to_dict(),
            )

        if tool_input.sku:
            rec = self.records_by_sku.get(tool_input.sku.upper())
            if rec is None:
                return InventoryToolOutput(
                    status="not_found",
                    records=[],
                    total_matched=0,
                    latency_ms=1.4,
                    error_message=f"No inventory product matched sku='{tool_input.sku}'.",
                    queried_criteria=tool_input.to_dict(),
                )
            return InventoryToolOutput(
                status="success",
                records=[rec],
                total_matched=1,
                latency_ms=1.9,
                queried_criteria=tool_input.to_dict(),
            )

        all_recs = list(self.records_by_sku.values())
        return InventoryToolOutput(
            status="success" if all_recs else "not_found",
            records=all_recs[:20],
            total_matched=len(all_recs),
            latency_ms=2.0,
            queried_criteria=tool_input.to_dict(),
        )


def _make_context(
    source_document: str = "returns-policy",
    section: str = "Standard Return Window & Return Shipping Costs",
    text: str = "Standard return window: 30 days from delivery unless the client brand has customized it.",
    score: float = 0.88,
    rank: int = 1,
) -> RetrievedContext:
    """Create a sample RetrievedContext for unit tests."""
    chunk = KnowledgeChunk(
        id=generate_chunk_id(source_document, rank - 1),
        company="trackflow",
        source_document=source_document,
        section=section,
        language="en",
        chunk_index=rank - 1,
        text=text,
    )
    return RetrievedContext(chunk=chunk, similarity_score=score, rank=rank)


# ==============================================================================
# Phase 3: User Story 1 - Single-Responsibility Nodes & Standard Flow (T010)
# ==============================================================================


class TestUserStory1SingleResponsibilityNodes:
    """Unit tests for intake_node, retrieval_node, generation_node, and standard workflow (T010)."""

    def test_t010_intake_node_sanitizes_input_and_initializes_trace_metadata(self) -> None:
        """T010: intake_node must sanitize query, clamp length, plan selected_sources, and initialize trace metadata."""
        initial_state: AgentState = {
            "query": "   What is TrackFlow'\\''s   standard return window?  \x00 ",
            "top_k": 3,
            "min_score": 0.62,
        }
        updated = intake_node(initial_state)

        assert updated["query"] == "What is TrackFlow's standard return window?"
        assert updated["selected_sources"] == ["rag"]
        assert updated["trace_id"] != ""
        assert updated["node_history"] == ["intake"]
        assert "intake" in updated["step_latencies"]
        assert updated["step_latencies"]["intake"] > 0.0
        assert updated["is_refusal"] is False

    def test_t010_retrieval_node_reuses_ports_and_records_rag_source(self) -> None:
        """T010: retrieval_node must embed query, search vector store, filter by min_score (0.62), and append 'rag' to sources_consulted."""
        high_ctx = _make_context(score=0.86, rank=1)
        low_ctx = _make_context(
            source_document="sla-delivery",
            section="Delivery Tiers",
            text="Standard shipping takes 3 to 5 business days domestically.",
            score=0.49,
            rank=2,
        )
        embedder = StubEmbeddingService()
        vector_store = StubVectorStore([high_ctx, low_ctx])

        state_after_intake: AgentState = {
            "query": "What is TrackFlow's standard return window?",
            "top_k": 3,
            "min_score": 0.62,
            "trace_id": "trace-001",
            "node_history": ["intake"],
            "step_latencies": {"intake": 0.5},
        }
        updated = retrieval_node(
            state_after_intake,
            vector_store=vector_store,
            embedding_service=embedder,
        )

        assert embedder.embed_query_calls == 1
        assert vector_store.search_calls == 1
        assert len(updated["contexts"]) == 1
        assert updated["contexts"][0].similarity_score == 0.86
        assert updated["sources_consulted"] == ["rag"]
        assert updated["node_history"] == ["intake", "retrieval"]
        assert updated["step_latencies"]["retrieval"] > 0.0

    def test_t010_generation_node_consumes_pre_retrieved_contexts_without_retrieval(self) -> None:
        """T010: generation_node must synthesize answer from state contexts and extract citations without calling retrieval."""
        ctx = _make_context(score=0.89, rank=1)
        llm = StubLLMGenerator()

        state_after_retrieval: AgentState = {
            "query": "What is TrackFlow's standard return window?",
            "contexts": [ctx],
            "trace_id": "trace-002",
            "node_history": ["intake", "retrieval"],
            "step_latencies": {"intake": 0.4, "retrieval": 3.2},
        }
        updated = generation_node(state_after_retrieval, llm_generator=llm)

        assert llm.generate_calls == 1
        assert llm.last_contexts == [ctx]
        assert updated["is_refusal"] is False
        assert "30-day return window" in updated["answer"]
        assert len(updated["sources"]) == 1
        assert updated["sources"][0].source_document == "returns-policy"
        assert updated["sources"][0].similarity_score == 0.89
        assert updated["node_history"] == ["intake", "retrieval", "generation"]
        assert updated["step_latencies"]["generation"] > 0.0

    def test_t010_standard_reasoning_workflow_execution_end_to_end(self) -> None:
        """T010: Compiled graph must execute intake -> retrieval -> generation for a valid policy inquiry."""
        ctx = _make_context(score=0.91, rank=1)
        embedder = StubEmbeddingService()
        vector_store = StubVectorStore([ctx])
        llm = StubLLMGenerator()
        ticket_tool = StubTicketTool()
        inventory_tool = StubInventoryTool()

        compiled_graph = build_support_agent_graph(
            vector_store=vector_store,
            embedding_service=embedder,
            llm_generator=llm,
            ticket_tool=ticket_tool,
            inventory_tool=inventory_tool,
        )

        final_state = compiled_graph.invoke(
            {
                "query": "What is TrackFlow's standard return window?",
                "top_k": 3,
                "min_score": 0.62,
                "trace_id": "test-thread-us1",
            },
            config={"configurable": {"thread_id": "test-thread-us1"}},
        )

        assert final_state["node_history"] == ["intake", "retrieval", "generation"]
        assert final_state["sources_consulted"] == ["rag"]
        assert final_state["is_refusal"] is False
        assert "30-day" in final_state["answer"]
        assert len(final_state["sources"]) == 1
        assert len(ticket_tool.calls) == 0
        assert len(inventory_tool.calls) == 0


# ==============================================================================
# Phase 4: User Story 2 - Autonomous Ticket Routing & Hybrid Execution (T016)
# ==============================================================================


class TestUserStory2AutonomousTicketRouting:
    """Unit tests for autonomous ticket intent routing, ticket_tool_node, and hybrid canonical order (T016)."""

    def test_t016_classify_and_plan_query_distinguishes_ticket_rag_and_hybrid(self) -> None:
        """T016: classify_and_plan_query autonomously selects ticket_tool, rag, or canonical hybrid order."""
        # 1. Pure ticket ID inquiry
        sources, t_in, i_in = classify_and_plan_query(
            "What is the current status and category of ticket INC-001?"
        )
        assert sources == ["ticket_tool"]
        assert t_in is not None and t_in.ticket_id == "INC-001"
        assert i_in is None

        # 2. Filtered ticket inquiry
        sources_f, t_in_f, _ = classify_and_plan_query(
            "Are there any open delay incidents originating from warehouse in Zaragoza?"
        )
        assert sources_f == ["ticket_tool"]
        assert t_in_f is not None
        assert t_in_f.status == "open"
        assert t_in_f.category == "delay"
        assert t_in_f.origin == "warehouse"
        assert t_in_f.branch == "zaragoza"

        # 3. Hybrid inquiry (policy question asked BEFORE ticket ID still orders canonically: ticket_tool -> rag)
        sources_h, t_in_h, _ = classify_and_plan_query(
            "What is our standard return policy window, and what is the status of ticket INC-001?"
        )
        assert sources_h == ["ticket_tool", "rag"]
        assert t_in_h is not None and t_in_h.ticket_id == "INC-001"

    def test_t016_ticket_only_and_hybrid_workflow_execution(self) -> None:
        """T016: Compiled graph routes ticket inquiry to ticket_tool -> generation and hybrid inquiry to ticket_tool -> retrieval -> generation."""
        ctx = _make_context(score=0.90, rank=1)
        embedder = StubEmbeddingService()
        vector_store = StubVectorStore([ctx])
        llm = StubLLMGenerator()
        ticket_tool = StubTicketTool()
        inventory_tool = StubInventoryTool()

        compiled = build_support_agent_graph(
            vector_store=vector_store,
            embedding_service=embedder,
            llm_generator=llm,
            ticket_tool=ticket_tool,
            inventory_tool=inventory_tool,
        )

        # 1. Ticket-only run
        ticket_state = compiled.invoke(
            {"query": "What is the current status of ticket INC-001?", "trace_id": "t-ticket"},
            config={"configurable": {"thread_id": "t-ticket"}},
        )
        assert ticket_state["node_history"] == ["intake", "ticket_tool", "generation"]
        assert ticket_state["sources_consulted"] == ["ticket_tool"]
        assert ticket_state["fallback_triggered"] is False
        assert "INC-001" in ticket_state["answer"]
        assert "zaragoza" in ticket_state["answer"].lower()
        assert embedder.embed_query_calls == 0

        # 2. Hybrid run
        hybrid_state = compiled.invoke(
            {
                "query": "What is the status of ticket INC-001, and what is TrackFlow's standard return window?",
                "trace_id": "t-hybrid",
            },
            config={"configurable": {"thread_id": "t-hybrid"}},
        )
        assert hybrid_state["node_history"] == [
            "intake",
            "ticket_tool",
            "retrieval",
            "generation",
        ]
        assert hybrid_state["sources_consulted"] == ["ticket_tool", "rag"]
        assert "INC-001" in hybrid_state["answer"]
        assert "30-day" in hybrid_state["answer"]
        assert len(hybrid_state["sources"]) == 1


# ==============================================================================
# Phase 5: User Story 3 - Tool Timeouts & Honest Fallback Recovery (T022)
# ==============================================================================


class TestUserStory3ToolFallbackRecovery:
    """Unit tests for tool_fallback_node, missing record fallback, timeout fallback, and partial hybrid answers (T022)."""

    def test_t022_pure_ticket_fallback_on_missing_record_and_timeout(self) -> None:
        """T022: Missing ticket or tool timeout transitions to tool_fallback and terminates without hallucination."""
        ctx = _make_context(score=0.90, rank=1)
        embedder = StubEmbeddingService()
        vector_store = StubVectorStore([ctx])
        llm = StubLLMGenerator()

        # 1. Missing ticket INC-999999
        compiled_missing = build_support_agent_graph(
            vector_store=vector_store,
            embedding_service=embedder,
            llm_generator=llm,
            ticket_tool=StubTicketTool(),
            inventory_tool=StubInventoryTool(),
        )
        missing_state = compiled_missing.invoke(
            {"query": "What is the status of ticket INC-999999?", "trace_id": "t-miss"},
            config={"configurable": {"thread_id": "t-miss"}},
        )
        assert missing_state["node_history"] == ["intake", "ticket_tool", "tool_fallback"]
        assert missing_state["sources_consulted"] == ["ticket_tool"]
        assert missing_state["fallback_triggered"] is True
        assert missing_state["is_refusal"] is False
        assert "couldn't confirm the status of ticket 'INC-999999'" in missing_state["answer"]
        assert llm.generate_calls == 0

        # 2. Simulated timeout
        compiled_timeout = build_support_agent_graph(
            vector_store=vector_store,
            embedding_service=embedder,
            llm_generator=llm,
            ticket_tool=StubTicketTool(forced_status="timeout"),
            inventory_tool=StubInventoryTool(),
        )
        timeout_state = compiled_timeout.invoke(
            {"query": "What is the status of ticket INC-001?", "trace_id": "t-timeout"},
            config={"configurable": {"thread_id": "t-timeout"}},
        )
        assert timeout_state["node_history"] == ["intake", "ticket_tool", "tool_fallback"]
        assert timeout_state["fallback_triggered"] is True
        assert "timed out" in timeout_state["answer"].lower()
        assert llm.generate_calls == 0

    def test_t022_hybrid_query_with_failed_tool_returns_graceful_partial_answer(self) -> None:
        """T022: When ticket lookup fails in a hybrid query but RAG succeeds, workflow executes ticket_tool -> retrieval -> tool_fallback -> generation."""
        ctx = _make_context(score=0.91, rank=1)
        compiled = build_support_agent_graph(
            vector_store=StubVectorStore([ctx]),
            embedding_service=StubEmbeddingService(),
            llm_generator=StubLLMGenerator(),
            ticket_tool=StubTicketTool(),
            inventory_tool=StubInventoryTool(),
        )

        partial_state = compiled.invoke(
            {
                "query": "What is the status of ticket INC-999999, and what is TrackFlow's standard return window?",
                "trace_id": "t-partial",
            },
            config={"configurable": {"thread_id": "t-partial"}},
        )
        assert partial_state["node_history"] == [
            "intake",
            "ticket_tool",
            "retrieval",
            "tool_fallback",
            "generation",
        ]
        assert partial_state["sources_consulted"] == ["ticket_tool", "rag"]
        assert partial_state["fallback_triggered"] is True
        assert "INC-999999" in partial_state["answer"]
        assert "couldn't confirm" in partial_state["answer"].lower()
        assert "30-day" in partial_state["answer"]
        assert len(partial_state["sources"]) == 1


# ==============================================================================
# Phase 6: User Story 4 - Inventory Stock Tool & Multi-Tool Sequencing (T027)
# ==============================================================================


class TestUserStory4InventoryToolRouting:
    """Unit tests for inventory intent classification, inventory_tool_node, and multi-tool sequencing (T027)."""

    def test_t027_autonomous_inventory_routing_and_fallback(self) -> None:
        """T027: SKU query autonomously routes intake -> inventory_tool -> generation, and missing SKU routes to tool_fallback."""
        ctx = _make_context(score=0.90, rank=1)
        ticket_tool = StubTicketTool()
        inventory_tool = StubInventoryTool()
        compiled = build_support_agent_graph(
            vector_store=StubVectorStore([ctx]),
            embedding_service=StubEmbeddingService(),
            llm_generator=StubLLMGenerator(),
            ticket_tool=ticket_tool,
            inventory_tool=inventory_tool,
        )

        # 1. Existing SKU TF-1001
        inv_state = compiled.invoke(
            {"query": "How many units of SKU TF-1001 are currently in stock?", "trace_id": "t-inv"},
            config={"configurable": {"thread_id": "t-inv"}},
        )
        assert inv_state["node_history"] == ["intake", "inventory_tool", "generation"]
        assert inv_state["sources_consulted"] == ["inventory_tool"]
        assert inv_state["fallback_triggered"] is False
        assert "TF-1001" in inv_state["answer"]
        assert "145 units" in inv_state["answer"]
        assert len(ticket_tool.calls) == 0

        # 2. Missing SKU TF-9999 -> tool_fallback
        miss_inv_state = compiled.invoke(
            {"query": "How many units of SKU TF-9999 are currently in stock?", "trace_id": "t-inv-miss"},
            config={"configurable": {"thread_id": "t-inv-miss"}},
        )
        assert miss_inv_state["node_history"] == [
            "intake",
            "inventory_tool",
            "tool_fallback",
        ]
        assert miss_inv_state["fallback_triggered"] is True
        assert "couldn't confirm the stock availability for SKU 'TF-9999'" in miss_inv_state["answer"]

        # 3. Multi-tool + RAG canonical sequencing: ticket_tool -> inventory_tool -> retrieval -> generation
        all_three_state = compiled.invoke(
            {
                "query": "Check SKU TF-1001 stock, ticket INC-001 status, and our standard return window.",
                "trace_id": "t-all-three",
            },
            config={"configurable": {"thread_id": "t-all-three"}},
        )
        assert all_three_state["node_history"] == [
            "intake",
            "ticket_tool",
            "inventory_tool",
            "retrieval",
            "generation",
        ]
        assert all_three_state["sources_consulted"] == [
            "ticket_tool",
            "inventory_tool",
            "rag",
        ]


# ==============================================================================
# Phase 7: User Story 5 - Conditional Branching & Policy/Mutation Refusal (T032)
# ==============================================================================


class TestUserStory5ConditionalBranchingAndRefusal:
    """Unit tests for empty query, write-mutation guardrail refusal, and < 0.62 policy refusal (T032)."""

    def test_t032_route_after_intake_and_mutation_detection(self) -> None:
        """T032: route_after_intake routes blank/short and write-mutation queries to 'refusal'."""
        assert route_after_intake({"query": ""}) == "refusal"
        assert route_after_intake({"query": "   "}) == "refusal"
        assert route_after_intake({"query": "ab"}) == "refusal"
        assert detect_mutation_attempt("Close ticket INC-001 immediately") is True
        assert detect_mutation_attempt("Delete incident INC-002") is True
        assert detect_mutation_attempt("Update stock for SKU TF-1001 to 500 units") is True
        assert detect_mutation_attempt("What is the current status of ticket INC-001?") is False
        assert detect_mutation_attempt("Are there any open incidents?") is False

    def test_t032_workflow_refuses_mutation_empty_and_unindexed_queries(self) -> None:
        """T032: Compiled graph halts at intake -> refusal for empty and mutation prompts, and routes < 0.62 policy queries to intake -> retrieval -> refusal."""
        sub_ctx = _make_context(score=0.41, rank=1)
        embedder = StubEmbeddingService()
        vector_store = StubVectorStore([sub_ctx])
        llm = StubLLMGenerator()
        ticket_tool = StubTicketTool()
        inventory_tool = StubInventoryTool()

        compiled_graph = build_support_agent_graph(
            vector_store=vector_store,
            embedding_service=embedder,
            llm_generator=llm,
            ticket_tool=ticket_tool,
            inventory_tool=inventory_tool,
        )

        # 1. Empty whitespace query -> intake -> refusal
        empty_state = compiled_graph.invoke(
            {"query": "   \t\n  ", "trace_id": "thread-empty"},
            config={"configurable": {"thread_id": "thread-empty"}},
        )
        assert empty_state["node_history"] == ["intake", "refusal"]
        assert empty_state["is_refusal"] is True
        assert empty_state["answer"] == STANDARD_REFUSAL_MESSAGE

        # 2. Write/mutation prompt -> intake -> refusal (zero tool calls, zero vector search)
        mutation_state = compiled_graph.invoke(
            {"query": "Close ticket INC-001 and delete incident INC-002", "trace_id": "thread-mut"},
            config={"configurable": {"thread_id": "thread-mut"}},
        )
        assert mutation_state["node_history"] == ["intake", "refusal"]
        assert mutation_state["is_refusal"] is True
        assert "read-only" in mutation_state["answer"].lower()
        assert len(ticket_tool.calls) == 0
        assert embedder.embed_query_calls == 0

        # 3. Out-of-scope policy query -> intake -> retrieval -> refusal
        refusal_state = compiled_graph.invoke(
            {
                "query": "What is TrackFlow's pharmaceutical refrigeration policy?",
                "trace_id": "thread-refusal",
            },
            config={"configurable": {"thread_id": "thread-refusal"}},
        )
        assert refusal_state["node_history"] == ["intake", "retrieval", "refusal"]
        assert refusal_state["is_refusal"] is True
        assert refusal_state["sources"] == []
        assert embedder.embed_query_calls == 1
        assert llm.generate_calls == 0


# ==============================================================================
# Phase 8: User Story 6 - Multi-Source Tracing & State Checkpointing (T035)
# ==============================================================================


class TestUserStory6TracingAndCheckpointing:
    """Unit tests for multi-source AgentTrace telemetry, TraceRegistry, and MemorySaver checkpointing (T035)."""

    def test_t035_support_agent_service_records_multi_source_trace_and_checkpoints(self) -> None:
        """T035: SupportAgentService records sources_consulted, fallback_triggered, tool_calls, and checkpoints."""
        ctx = _make_context(score=0.87, rank=1)
        checkpointer = MemorySaver()
        registry = TraceRegistry()
        service = SupportAgentService(
            vector_store=StubVectorStore([ctx]),
            embedding_service=StubEmbeddingService(),
            llm_generator=StubLLMGenerator(),
            ticket_tool=StubTicketTool(),
            inventory_tool=StubInventoryTool(),
            trace_registry=registry,
            checkpointer=checkpointer,
        )

        # 1. Hybrid query trace
        thread_id = "checkpoint-hybrid-thread-42"
        result = service.query(
            AgentQueryRequest(
                query="What is the status of ticket INC-001 and what is our standard return window?",
                thread_id=thread_id,
            )
        )

        assert result.trace_id == thread_id
        assert result.node_sequence == ["intake", "ticket_tool", "retrieval", "generation"]
        assert result.sources_consulted == ["ticket_tool", "rag"]
        assert result.fallback_triggered is False
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool_name"] == "ticket_tool"
        assert result.tool_calls[0]["status"] == "success"

        trace = service.get_trace(thread_id)
        assert trace.sources_consulted == ["ticket_tool", "rag"]
        assert trace.fallback_triggered is False
        assert len(trace.tool_calls) == 1
        assert len(trace.checkpoints) >= 1
        assert trace.checkpoints[-1].state_delta["sources_consulted"] == ["ticket_tool", "rag"]

        with pytest.raises(TraceNotFoundError):
            service.get_trace("non-existent-trace-id")


# ==============================================================================
# Build-Time Graph Compilation Validation
# ==============================================================================


class TestBuildTimeGraphCompilationValidation:
    """Unit tests verifying build-time fail-fast compilation on structural defects (FR-006)."""

    def test_fails_at_compile_time_when_required_node_is_missing_or_disconnected(
        self,
    ) -> None:
        """compile_and_validate_graph must raise GraphCompilationError when any required node is missing or disconnected."""
        assert len(REQUIRED_WORKFLOW_NODES) == 7

        # 1. Missing required nodes
        incomplete_graph: StateGraph = StateGraph(AgentState)
        incomplete_graph.add_node("intake", intake_node)
        incomplete_graph.add_edge(START, "intake")
        incomplete_graph.add_edge("intake", END)

        with pytest.raises(GraphCompilationError, match="Missing required workflow nodes"):
            compile_and_validate_graph(incomplete_graph)

        # 2. Disconnected / orphan node with no incoming edges
        disconnected_graph: StateGraph = StateGraph(AgentState)
        for node_name in REQUIRED_WORKFLOW_NODES:
            disconnected_graph.add_node(node_name, intake_node)
        disconnected_graph.add_node("orphan_node", refusal_node)

        disconnected_graph.add_edge(START, "intake")
        disconnected_graph.add_edge("intake", "ticket_tool")
        disconnected_graph.add_edge("ticket_tool", "inventory_tool")
        disconnected_graph.add_edge("inventory_tool", "retrieval")
        disconnected_graph.add_edge("retrieval", "tool_fallback")
        disconnected_graph.add_edge("tool_fallback", "generation")
        disconnected_graph.add_edge("generation", "refusal")
        disconnected_graph.add_edge("refusal", END)

        with pytest.raises(GraphCompilationError, match="orphan_node|unreachable|disconnected"):
            compile_and_validate_graph(disconnected_graph)
