"""Unit and workflow integration tests for Support Agent with LangGraph (T008, T009, T014, T015, T020, T021, T038).

Verifies:
- US1 (T008, T009): Single-responsibility nodes (`intake_node`, `retrieval_node`, `generation_node`)
  and standard linear reasoning workflow (`intake` -> `retrieval` -> `generation`).
- US2 (T014, T015): Conditional routing edges (`route_after_intake`, `route_after_retrieval`)
  and honest policy refusal (`refusal_node`) when similarity < 0.62 or query is blank.
- US3 (T020, T021): Execution tracing (`AgentTrace`, `TraceRegistry`), positive step latencies,
  and state checkpointing/inspection via LangGraph `MemorySaver`.
- Polish (T038): Build-time graph compilation validation and fail-fast `GraphCompilationError`
  on disconnected or misconfigured nodes.
"""

from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
import pytest

from application.services.agent_workflow import (
    build_support_agent_graph,
    compile_and_validate_graph,
    generation_node,
    intake_node,
    refusal_node,
    retrieval_node,
    route_after_intake,
    route_after_retrieval,
)
from application.services.knowledge_service import STANDARD_REFUSAL_MESSAGE
from application.services.support_agent_service import SupportAgentService
from application.services.trace_registry import TraceRegistry
from domain.agent.entities import (
    AgentQueryRequest,
    AgentState,
    KnowledgeChunk,
    RetrievedContext,
)
from domain.agent.exceptions import GraphCompilationError, TraceNotFoundError
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
# Phase 3: User Story 1 - Single-Responsibility Nodes & Standard Flow (T008, T009)
# ==============================================================================


class TestUserStory1SingleResponsibilityNodes:
    """Unit tests for intake_node, retrieval_node, generation_node, and standard workflow."""

    def test_t008_intake_node_sanitizes_input_and_initializes_trace_metadata(self) -> None:
        """T008: intake_node must sanitize query, clamp length, and initialize trace metadata."""
        initial_state: AgentState = {
            "query": "   What is TrackFlow'\\''s   standard return window?  \x00 ",
            "top_k": 3,
            "min_score": 0.62,
        }
        updated = intake_node(initial_state)

        assert updated["query"] == "What is TrackFlow's standard return window?"
        assert updated["trace_id"] != ""
        assert updated["node_history"] == ["intake"]
        assert "intake" in updated["step_latencies"]
        assert updated["step_latencies"]["intake"] > 0.0
        assert updated["is_refusal"] is False

    def test_t008_retrieval_node_reuses_ports_and_filters_by_min_score(self) -> None:
        """T008: retrieval_node must embed query, search vector store, and filter by min_score (0.62)."""
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
        assert updated["node_history"] == ["intake", "retrieval"]
        assert updated["step_latencies"]["retrieval"] > 0.0

    def test_t008_generation_node_consumes_pre_retrieved_contexts_without_retrieval(self) -> None:
        """T008: generation_node must synthesize answer from state contexts and extract citations without calling retrieval."""
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

    def test_t009_standard_reasoning_workflow_execution_end_to_end(self) -> None:
        """T009: Compiled graph must execute intake -> retrieval -> generation for a valid policy inquiry."""
        ctx = _make_context(score=0.91, rank=1)
        embedder = StubEmbeddingService()
        vector_store = StubVectorStore([ctx])
        llm = StubLLMGenerator()

        compiled_graph = build_support_agent_graph(
            vector_store=vector_store,
            embedding_service=embedder,
            llm_generator=llm,
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
        assert final_state["is_refusal"] is False
        assert "30-day" in final_state["answer"]
        assert len(final_state["sources"]) == 1
        assert embedder.embed_query_calls == 1
        assert vector_store.search_calls == 1
        assert llm.generate_calls == 1


# ==============================================================================
# Phase 4: User Story 2 - Conditional Routing & Honest Policy Refusal (T014, T015)
# ==============================================================================


class TestUserStory2ConditionalBranchingAndRefusal:
    """Unit tests for route_after_intake, route_after_retrieval, and refusal_node."""

    def test_t014_route_after_intake_branches_correctly(self) -> None:
        """T014: route_after_intake must route blank/short queries to 'refusal' and valid queries to 'retrieval'."""
        assert route_after_intake({"query": ""}) == "refusal"
        assert route_after_intake({"query": "   "}) == "refusal"
        assert route_after_intake({"query": "ab"}) == "refusal"
        assert route_after_intake({"query": "What is the return policy?"}) == "retrieval"

    def test_t014_route_after_retrieval_enforces_threshold(self) -> None:
        """T014: route_after_retrieval must route empty or sub-threshold contexts to 'refusal' and qualified contexts to 'generation'."""
        assert route_after_retrieval({"contexts": [], "min_score": 0.62}) == "refusal"
        sub_threshold_ctx = _make_context(score=0.58)
        assert (
            route_after_retrieval({"contexts": [sub_threshold_ctx], "min_score": 0.62})
            == "refusal"
        )
        qualified_ctx = _make_context(score=0.62)
        assert (
            route_after_retrieval({"contexts": [qualified_ctx], "min_score": 0.62})
            == "generation"
        )

    def test_t015_refusal_node_formats_honest_refusal_and_clears_sources(self) -> None:
        """T015: refusal_node must set is_refusal=True, clear sources, and format topic-aware refusal message."""
        state: AgentState = {
            "query": "What are the temperature requirements for pharmaceutical refrigeration?",
            "node_history": ["intake", "retrieval"],
            "step_latencies": {"intake": 0.3, "retrieval": 2.1},
        }
        updated = refusal_node(state)

        assert updated["is_refusal"] is True
        assert updated["sources"] == []
        assert "TrackFlow internal documentation does not contain verified policy regarding" in updated["answer"]
        assert "pharmaceutical refrigeration" in updated["answer"].lower()
        assert updated["node_history"] == ["intake", "retrieval", "refusal"]
        assert updated["step_latencies"]["refusal"] > 0.0

        # Empty query refusal uses standard refusal message
        empty_updated = refusal_node({"query": "", "node_history": ["intake"], "step_latencies": {}})
        assert empty_updated["is_refusal"] is True
        assert empty_updated["answer"] == STANDARD_REFUSAL_MESSAGE

    def test_t017_t018_workflow_halts_early_on_empty_query_and_branches_to_refusal_on_unindexed_query(
        self,
    ) -> None:
        """T017, T018: Compiled graph halts before retrieval on empty input and branches to refusal without generation on low similarity."""
        sub_ctx = _make_context(score=0.41, rank=1)
        embedder = StubEmbeddingService()
        vector_store = StubVectorStore([sub_ctx])
        llm = StubLLMGenerator()

        compiled_graph = build_support_agent_graph(
            vector_store=vector_store,
            embedding_service=embedder,
            llm_generator=llm,
        )

        # 1. Empty whitespace query -> intake -> refusal (zero vector search, zero LLM calls)
        empty_state = compiled_graph.invoke(
            {"query": "   \t\n  ", "trace_id": "thread-empty"},
            config={"configurable": {"thread_id": "thread-empty"}},
        )
        assert empty_state["node_history"] == ["intake", "refusal"]
        assert empty_state["is_refusal"] is True
        assert embedder.embed_query_calls == 0
        assert vector_store.search_calls == 0
        assert llm.generate_calls == 0

        # 2. Out-of-scope query -> intake -> retrieval -> refusal (zero LLM calls)
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
        assert vector_store.search_calls == 1
        assert llm.generate_calls == 0


# ==============================================================================
# Phase 5: User Story 3 - Execution Tracing & State Checkpointing (T020, T021)
# ==============================================================================


class TestUserStory3TracingAndCheckpointing:
    """Unit tests for AgentTrace telemetry, TraceRegistry, and MemorySaver checkpointing."""

    def test_t020_support_agent_service_records_queryable_trace_and_latencies(self) -> None:
        """T020: SupportAgentService must record a queryable AgentTrace with exact node sequence and positive step latencies."""
        ctx = _make_context(score=0.87, rank=1)
        registry = TraceRegistry()
        service = SupportAgentService(
            vector_store=StubVectorStore([ctx]),
            embedding_service=StubEmbeddingService(),
            llm_generator=StubLLMGenerator(),
            trace_registry=registry,
        )

        result = service.query(
            AgentQueryRequest(
                query="What is TrackFlow's standard return window?",
                top_k=3,
                min_score=0.62,
            )
        )

        assert result.trace_id != ""
        assert result.node_sequence == ["intake", "retrieval", "generation"]
        assert result.is_refusal is False
        assert result.execution_time_ms > 0.0

        trace = service.get_trace(result.trace_id)
        assert trace.trace_id == result.trace_id
        assert trace.node_sequence == ["intake", "retrieval", "generation"]
        for node_name in ("intake", "retrieval", "generation"):
            assert node_name in trace.step_latencies
            assert trace.step_latencies[node_name] > 0.0
            assert node_name in trace.node_outputs
        assert trace.node_outputs["retrieval"]["context_count"] == 1
        assert trace.node_outputs["generation"]["answer"] == result.answer
        assert trace.total_duration_ms >= sum(trace.step_latencies.values())
        assert trace.source_count == 1
        assert trace.final_answer == result.answer

        with pytest.raises(TraceNotFoundError):
            service.get_trace("non-existent-trace-id")

    def test_t021_memory_saver_checkpointer_persists_state_snapshots_per_thread(self) -> None:
        """T021: MemorySaver checkpointer must persist inspectable state snapshots for each thread_id."""
        ctx = _make_context(score=0.85, rank=1)
        checkpointer = MemorySaver()
        registry = TraceRegistry()
        service = SupportAgentService(
            vector_store=StubVectorStore([ctx]),
            embedding_service=StubEmbeddingService(),
            llm_generator=StubLLMGenerator(),
            trace_registry=registry,
            checkpointer=checkpointer,
        )

        thread_id = "checkpoint-test-thread-42"
        result = service.query(
            AgentQueryRequest(
                query="What is TrackFlow's standard return window?",
                thread_id=thread_id,
            )
        )

        assert result.trace_id == thread_id
        checkpoints = service.get_checkpoints(thread_id)
        assert len(checkpoints) >= 1
        assert all(cp.thread_id == thread_id for cp in checkpoints)
        assert all(cp.checkpoint_id != "" for cp in checkpoints)

        # Verify direct LangGraph state inspection via checkpointer config
        state_snapshot = service.compiled_graph.get_state(
            {"configurable": {"thread_id": thread_id}}
        )
        assert state_snapshot is not None
        assert state_snapshot.values["query"] == "What is TrackFlow's standard return window?"
        assert state_snapshot.values["node_history"] == ["intake", "retrieval", "generation"]


# ==============================================================================
# Phase 8: Build-Time Graph Compilation Validation (T038)
# ==============================================================================


class TestBuildTimeGraphCompilationValidation:
    """Unit tests verifying build-time fail-fast compilation on structural defects (FR-006, SC-006, T038)."""

    def test_t038_fails_at_compile_time_when_required_node_is_missing_or_disconnected(
        self,
    ) -> None:
        """T038: compile_and_validate_graph must raise GraphCompilationError when a node is disconnected or missing."""
        # 1. Missing required nodes
        incomplete_graph: StateGraph = StateGraph(AgentState)
        incomplete_graph.add_node("intake", intake_node)
        incomplete_graph.add_edge(START, "intake")
        incomplete_graph.add_edge("intake", END)

        with pytest.raises(GraphCompilationError, match="Missing required workflow nodes"):
            compile_and_validate_graph(incomplete_graph)

        # 2. Disconnected / orphan node with no incoming or outgoing edges
        disconnected_graph: StateGraph = StateGraph(AgentState)
        disconnected_graph.add_node("intake", intake_node)
        disconnected_graph.add_node("retrieval", intake_node)
        disconnected_graph.add_node("generation", intake_node)
        disconnected_graph.add_node("refusal", refusal_node)
        disconnected_graph.add_node("orphan_node", refusal_node)

        disconnected_graph.add_edge(START, "intake")
        disconnected_graph.add_edge("intake", "retrieval")
        disconnected_graph.add_edge("retrieval", "generation")
        disconnected_graph.add_edge("generation", END)
        disconnected_graph.add_edge("refusal", END)

        with pytest.raises(GraphCompilationError, match="orphan_node|unreachable|disconnected"):
            compile_and_validate_graph(disconnected_graph)
