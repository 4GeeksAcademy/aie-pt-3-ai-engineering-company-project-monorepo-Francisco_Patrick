"""LangGraph state workflow for the TrackFlow Support Agent.

Implements:
- Single-responsibility nodes: `intake_node`, `retrieval_node`, `generation_node`, `refusal_node`
- Deterministic conditional routing edges: `route_after_intake`, `route_after_retrieval`
- Build-time structural validation and compilation (`compile_and_validate_graph`, `build_support_agent_graph`)
- Per-node latency telemetry and `MemorySaver` state checkpointing.
"""

import re
import time
import uuid
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Set

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from application.services.guardrails import BusinessGuardrailValidator
from application.services.knowledge_service import (
    DEFAULT_SIMILARITY_THRESHOLD,
    STANDARD_REFUSAL_MESSAGE,
    build_refusal_message,
)
from domain.agent.entities import (
    AgentState,
    RetrievedContext,
    SourceCitation,
)
from domain.agent.exceptions import (
    GraphCompilationError,
    WorkflowExecutionError,
)
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)

REQUIRED_WORKFLOW_NODES: Sequence[str] = (
    "intake",
    "retrieval",
    "generation",
    "refusal",
)

MAX_QUERY_LENGTH = 500
MIN_QUERY_LENGTH = 3


def sanitize_agent_query(raw_query: Optional[str]) -> str:
    """Sanitize and normalize user inquiry input at the intake stage.

    Normalizes POSIX shell-escaped single/double quotes, strips ASCII control
    characters, collapses redundant whitespace, and truncates to `MAX_QUERY_LENGTH`.

    Args:
        raw_query: Raw user input string.

    Returns:
        Sanitized query string.
    """
    if not raw_query:
        return ""
    cleaned = raw_query.replace("'\\''", "'").replace('\\"', '"')
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > MAX_QUERY_LENGTH:
        cleaned = cleaned[:MAX_QUERY_LENGTH].strip()
    return cleaned


def intake_node(state: AgentState) -> AgentState:
    """Single-responsibility intake node for input validation, sanitization, and trace initialization.

    Args:
        state: Incoming AgentState dictionary.

    Returns:
        Updated AgentState with sanitized query, initialized trace_id, node_history, and step_latencies.
    """
    start_ns = time.perf_counter()

    raw_query = state.get("query")
    sanitized_query = sanitize_agent_query(raw_query)

    trace_id = state.get("trace_id") or str(uuid.uuid4())
    raw_top_k = state.get("top_k", 3)
    top_k = max(1, min(20, int(raw_top_k if raw_top_k is not None else 3)))

    raw_min_score = state.get("min_score", DEFAULT_SIMILARITY_THRESHOLD)
    min_score = max(
        0.0,
        min(
            1.0,
            float(
                raw_min_score
                if raw_min_score is not None
                else DEFAULT_SIMILARITY_THRESHOLD
            ),
        ),
    )

    language = (state.get("language") or "en").strip() or "en"
    node_history = list(state.get("node_history") or [])
    node_history.append("intake")

    is_invalid = len(sanitized_query) < MIN_QUERY_LENGTH

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["intake"] = elapsed_ms

    return {
        "query": sanitized_query,
        "language": language,
        "top_k": top_k,
        "min_score": min_score,
        "contexts": list(state.get("contexts") or []),
        "answer": state.get("answer") or "",
        "is_refusal": bool(is_invalid),
        "sources": list(state.get("sources") or []),
        "trace_id": trace_id,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "error": state.get("error"),
    }


def retrieval_node(
    state: AgentState,
    vector_store: VectorStorePort,
    embedding_service: EmbeddingServicePort,
    default_min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> AgentState:
    """Single-responsibility retrieval node reusing EmbeddingServicePort and VectorStorePort.

    Embeds the sanitized query, performs cosine similarity search, and filters candidates
    strictly against the calibrated `min_score` threshold (0.62 default).

    Args:
        state: Current AgentState after intake.
        vector_store: VectorStorePort adapter.
        embedding_service: EmbeddingServicePort adapter.
        default_min_score: Fallback minimum similarity threshold.

    Returns:
        Updated AgentState with threshold-qualified `contexts`, `node_history`, and `step_latencies`.
    """
    start_ns = time.perf_counter()

    query = (state.get("query") or "").strip()
    top_k = int(state.get("top_k", 3))
    min_score = float(state.get("min_score", default_min_score))

    try:
        query_vector = embedding_service.embed_query(query)
        candidates = vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            language=None,
        )
    except KnowledgeBaseUnavailableException:
        raise
    except Exception as exc:
        raise WorkflowExecutionError(
            message="Vector retrieval failed during support agent execution.",
            trace_id=state.get("trace_id"),
        ) from exc

    qualified_contexts: List[RetrievedContext] = [
        ctx for ctx in candidates if ctx.similarity_score >= min_score
    ]

    node_history = list(state.get("node_history") or [])
    node_history.append("retrieval")

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["retrieval"] = elapsed_ms

    return {
        "contexts": qualified_contexts,
        "node_history": node_history,
        "step_latencies": step_latencies,
    }


def generation_node(
    state: AgentState,
    llm_generator: LLMGenerationPort,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
) -> AgentState:
    """Single-responsibility generation node consuming pre-retrieved contexts.

    Strictly separated from retrieval (FR-004): consumes `state['contexts']`, invokes
    grounded synthesis, enforces TrackFlow corporate guardrails, and extracts citations.

    Args:
        state: Current AgentState containing qualified `contexts`.
        llm_generator: LLMGenerationPort implementation.
        guardrail_validator: Optional BusinessGuardrailValidator instance.

    Returns:
        Updated AgentState with `answer`, `is_refusal=False`, `sources`, `node_history`, and `step_latencies`.
    """
    start_ns = time.perf_counter()
    validator = guardrail_validator or BusinessGuardrailValidator()

    query = state.get("query") or ""
    language = state.get("language") or "en"
    contexts: List[RetrievedContext] = list(state.get("contexts") or [])

    try:
        raw_answer = llm_generator.generate_grounded_answer(
            query=query,
            contexts=contexts,
            language=language,
        )
        enforced_answer = validator.enforce(
            query=query,
            answer=raw_answer,
            contexts=contexts,
        )
    except Exception as exc:
        raise WorkflowExecutionError(
            message="Answer generation failed during support agent execution.",
            trace_id=state.get("trace_id"),
        ) from exc

    citations: List[SourceCitation] = [
        SourceCitation(
            source_document=ctx.chunk.source_document,
            section=ctx.chunk.section,
            similarity_score=round(max(0.0, min(1.0, ctx.similarity_score)), 4),
        )
        for ctx in contexts
    ]

    node_history = list(state.get("node_history") or [])
    node_history.append("generation")

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["generation"] = elapsed_ms

    return {
        "answer": enforced_answer,
        "is_refusal": False,
        "sources": citations,
        "node_history": node_history,
        "step_latencies": step_latencies,
    }


def refusal_node(state: AgentState) -> AgentState:
    """Single-responsibility refusal node formatting standardized honest policy refusals.

    Executed when input is blank/short at intake or when zero context chunks satisfy
    the calibrated 0.62 similarity threshold after retrieval.

    Args:
        state: Current AgentState.

    Returns:
        Updated AgentState with standardized refusal `answer`, `is_refusal=True`, and `sources=[]`.
    """
    start_ns = time.perf_counter()

    query = (state.get("query") or "").strip()
    if len(query) < MIN_QUERY_LENGTH:
        refusal_text = STANDARD_REFUSAL_MESSAGE
    else:
        refusal_text = build_refusal_message(query)

    node_history = list(state.get("node_history") or [])
    node_history.append("refusal")

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["refusal"] = elapsed_ms

    return {
        "answer": refusal_text,
        "is_refusal": True,
        "sources": [],
        "node_history": node_history,
        "step_latencies": step_latencies,
    }


def route_after_intake(state: AgentState) -> Literal["retrieval", "refusal"]:
    """Conditional routing edge evaluated immediately after `intake_node`.

    Routes empty, whitespace-only, or short (< 3 chars) queries directly to `refusal`
    without invoking vector search or embeddings (FR-005, SC-002).

    Args:
        state: AgentState emitted by `intake_node`.

    Returns:
        Target node identifier: `'retrieval'` or `'refusal'`.
    """
    query = (state.get("query") or "").strip()
    if len(query) < MIN_QUERY_LENGTH or state.get("is_refusal") is True or state.get("error"):
        return "refusal"
    return "retrieval"


def route_after_retrieval(state: AgentState) -> Literal["generation", "refusal"]:
    """Conditional routing edge evaluated immediately after `retrieval_node`.

    Enforces the calibrated cosine similarity threshold (0.62 default) and routes
    to `refusal` when zero qualifying chunks exist, preventing ungrounded generation.

    Args:
        state: AgentState emitted by `retrieval_node`.

    Returns:
        Target node identifier: `'generation'` or `'refusal'`.
    """
    if state.get("error"):
        return "refusal"
    min_score = float(state.get("min_score", DEFAULT_SIMILARITY_THRESHOLD))
    contexts: List[RetrievedContext] = list(state.get("contexts") or [])
    qualified = [ctx for ctx in contexts if ctx.similarity_score >= min_score]
    if not qualified:
        return "refusal"
    return "generation"


def create_retrieval_node(
    vector_store: VectorStorePort,
    embedding_service: EmbeddingServicePort,
    default_min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument retrieval node function for LangGraph registration."""

    def _bound_retrieval(state: AgentState) -> AgentState:
        return retrieval_node(
            state=state,
            vector_store=vector_store,
            embedding_service=embedding_service,
            default_min_score=default_min_score,
        )

    return _bound_retrieval


def create_generation_node(
    llm_generator: LLMGenerationPort,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument generation node function for LangGraph registration."""

    def _bound_generation(state: AgentState) -> AgentState:
        return generation_node(
            state=state,
            llm_generator=llm_generator,
            guardrail_validator=guardrail_validator,
        )

    return _bound_generation


def compile_and_validate_graph(
    workflow: StateGraph,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    required_nodes: Sequence[str] = REQUIRED_WORKFLOW_NODES,
) -> CompiledStateGraph:
    """Validate structural integrity of a StateGraph at build time and compile it.

    Verifies that:
    1. All required nodes are registered in `workflow.nodes`.
    2. Every registered node is reachable from `START` via direct or conditional edges.
    3. Every registered node has at least one outgoing transition leading toward `END`.

    Args:
        workflow: Uncompiled LangGraph StateGraph instance.
        checkpointer: Optional LangGraph checkpointer (e.g. `MemorySaver`).
        required_nodes: Required node names that must exist in the graph.

    Returns:
        CompiledStateGraph ready for execution.

    Raises:
        GraphCompilationError: If any node is missing, disconnected, or unreachable.
    """
    registered_nodes: Set[str] = set(workflow.nodes.keys())
    missing_nodes = [n for n in required_nodes if n not in registered_nodes]
    if missing_nodes:
        raise GraphCompilationError(
            f"Missing required workflow nodes: {', '.join(missing_nodes)}."
        )

    adjacency: Dict[str, Set[str]] = {
        node_name: set() for node_name in registered_nodes | {START, END}
    }

    for src, dst in getattr(workflow, "edges", set()):
        adjacency.setdefault(src, set()).add(dst)

    branches = getattr(workflow, "branches", {})
    for src, branch_map in branches.items():
        for branch_spec in branch_map.values():
            ends_map = getattr(branch_spec, "ends", None) or {}
            for dst in ends_map.values():
                adjacency.setdefault(src, set()).add(dst)

    # Verify all targets are valid registered nodes or END
    valid_targets = registered_nodes | {END}
    for src, targets in adjacency.items():
        for dst in targets:
            if dst not in valid_targets and dst != START:
                raise GraphCompilationError(
                    f"Node '{src}' routes to unknown target node '{dst}'."
                )

    # BFS from START to ensure every registered node is reachable
    visited: Set[str] = set()
    queue: List[str] = [START]
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for neighbor in adjacency.get(current, set()):
            if neighbor not in visited:
                queue.append(neighbor)

    unreachable_nodes = sorted(registered_nodes - visited)
    if unreachable_nodes:
        raise GraphCompilationError(
            f"Structural validation failed: disconnected or unreachable nodes detected: "
            f"{', '.join(unreachable_nodes)}."
        )

    # Verify every registered node has at least one outgoing edge
    dead_end_nodes = sorted(
        node_name
        for node_name in registered_nodes
        if not adjacency.get(node_name)
    )
    if dead_end_nodes:
        raise GraphCompilationError(
            f"Structural validation failed: nodes without outgoing transitions: "
            f"{', '.join(dead_end_nodes)}."
        )

    try:
        return workflow.compile(checkpointer=checkpointer)
    except Exception as exc:
        raise GraphCompilationError(
            f"LangGraph compilation failed: {exc}"
        ) from exc


def build_support_agent_graph(
    vector_store: VectorStorePort,
    embedding_service: EmbeddingServicePort,
    llm_generator: LLMGenerationPort,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    default_min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> CompiledStateGraph:
    """Assemble, validate, and compile the TrackFlow Support Agent LangGraph state machine.

    Topology:
    - `START` -> `intake`
    - `intake` --(conditional: `route_after_intake`)--> `retrieval` | `refusal`
    - `retrieval` --(conditional: `route_after_retrieval`)--> `generation` | `refusal`
    - `generation` -> `END`
    - `refusal` -> `END`

    Args:
        vector_store: VectorStorePort implementation for semantic search.
        embedding_service: EmbeddingServicePort implementation for query embeddings.
        llm_generator: LLMGenerationPort implementation for grounded synthesis.
        guardrail_validator: Optional BusinessGuardrailValidator instance.
        checkpointer: Optional checkpointer (defaults to `MemorySaver()`).
        default_min_score: Calibrated cosine similarity threshold (defaults to 0.62).

    Returns:
        CompiledStateGraph instance validated at build time.
    """
    resolved_checkpointer = checkpointer if checkpointer is not None else MemorySaver()

    workflow = StateGraph(AgentState)

    workflow.add_node("intake", intake_node)
    workflow.add_node(
        "retrieval",
        create_retrieval_node(
            vector_store=vector_store,
            embedding_service=embedding_service,
            default_min_score=default_min_score,
        ),
    )
    workflow.add_node(
        "generation",
        create_generation_node(
            llm_generator=llm_generator,
            guardrail_validator=guardrail_validator,
        ),
    )
    workflow.add_node("refusal", refusal_node)

    workflow.add_edge(START, "intake")
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "retrieval": "retrieval",
            "refusal": "refusal",
        },
    )
    workflow.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "generation": "generation",
            "refusal": "refusal",
        },
    )
    workflow.add_edge("generation", END)
    workflow.add_edge("refusal", END)

    return compile_and_validate_graph(
        workflow=workflow,
        checkpointer=resolved_checkpointer,
        required_nodes=REQUIRED_WORKFLOW_NODES,
    )


__all__ = [
    "MAX_QUERY_LENGTH",
    "MIN_QUERY_LENGTH",
    "REQUIRED_WORKFLOW_NODES",
    "build_support_agent_graph",
    "compile_and_validate_graph",
    "create_generation_node",
    "create_retrieval_node",
    "generation_node",
    "intake_node",
    "refusal_node",
    "retrieval_node",
    "route_after_intake",
    "route_after_retrieval",
    "sanitize_agent_query",
]
