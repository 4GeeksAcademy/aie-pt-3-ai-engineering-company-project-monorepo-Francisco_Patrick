"""Application service coordinating compiled Support Agent execution, tracing, and checkpointing.

Implements `SupportAgentServicePort` (T024):
- Compiles the LangGraph workflow at initialization time (fail-fast structural validation)
- Invokes the compiled graph with a thread-scoped `RunnableConfig` for state checkpointing
- Constructs an immutable `AgentTrace` record with node sequences and step latencies
- Persists every execution trace into `TraceRegistryPort` for post-hoc auditability.
"""

from datetime import datetime, timezone
import time
import uuid
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from application.services.agent_workflow import (
    REQUIRED_WORKFLOW_NODES,
    build_support_agent_graph,
)
from application.services.guardrails import BusinessGuardrailValidator
from application.services.trace_registry import TraceRegistry
from domain.agent.entities import (
    AgentCheckpoint,
    AgentQueryRequest,
    AgentQueryResult,
    AgentState,
    AgentTrace,
    SourceCitation,
)
from domain.agent.exceptions import (
    TraceNotFoundError,
    WorkflowExecutionError,
)
from domain.agent.ports import (
    SupportAgentServicePort,
    TraceRegistryPort,
)
from domain.knowledge.entities import KnowledgeRuntimeConfig
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)


class SupportAgentService(SupportAgentServicePort):
    """Application service orchestrating the compiled LangGraph Support Agent."""

    def __init__(
        self,
        vector_store: VectorStorePort,
        embedding_service: EmbeddingServicePort,
        llm_generator: LLMGenerationPort,
        trace_registry: Optional[TraceRegistryPort] = None,
        guardrail_validator: Optional[BusinessGuardrailValidator] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        config: Optional[KnowledgeRuntimeConfig] = None,
        compiled_graph: Optional[CompiledStateGraph] = None,
    ) -> None:
        """Initialize SupportAgentService and compile the workflow graph at startup.

        Args:
            vector_store: VectorStorePort implementation.
            embedding_service: EmbeddingServicePort implementation.
            llm_generator: LLMGenerationPort implementation.
            trace_registry: Optional TraceRegistryPort (defaults to new TraceRegistry).
            guardrail_validator: Optional BusinessGuardrailValidator instance.
            checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver).
            config: Optional KnowledgeRuntimeConfig loaded from .env.
            compiled_graph: Optional pre-compiled graph override.
        """
        self.config = config or KnowledgeRuntimeConfig.from_env()
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_generator = llm_generator
        self._trace_registry: TraceRegistryPort = trace_registry or TraceRegistry()
        self._guardrails = guardrail_validator or BusinessGuardrailValidator()
        self._checkpointer: BaseCheckpointSaver = (
            checkpointer if checkpointer is not None else MemorySaver()
        )
        self._compiled_graph: CompiledStateGraph = (
            compiled_graph
            if compiled_graph is not None
            else build_support_agent_graph(
                vector_store=self._vector_store,
                embedding_service=self._embedding_service,
                llm_generator=self._llm_generator,
                guardrail_validator=self._guardrails,
                checkpointer=self._checkpointer,
                default_min_score=self.config.similarity_threshold,
            )
        )

    @property
    def compiled_graph(self) -> CompiledStateGraph:
        """Return the compiled LangGraph state machine."""
        return self._compiled_graph

    @property
    def trace_registry(self) -> TraceRegistryPort:
        """Return the active TraceRegistryPort instance."""
        return self._trace_registry

    def query(self, request: AgentQueryRequest) -> AgentQueryResult:
        """Execute a customer inquiry through the compiled LangGraph workflow.

        Args:
            request: Validated AgentQueryRequest domain object.

        Returns:
            AgentQueryResult with grounded answer, citations, trace_id, and node sequence.

        Raises:
            KnowledgeBaseUnavailableException: When vector database is unreachable.
            WorkflowExecutionError: When an unhandled runtime fault occurs inside a node.
        """
        start_ns = time.perf_counter()
        trace_id = (
            request.thread_id.strip()
            if request.thread_id and request.thread_id.strip()
            else str(uuid.uuid4())
        )
        effective_min_score = (
            request.min_score
            if request.min_score is not None
            else self.config.similarity_threshold
        )

        initial_state: AgentState = {
            "query": request.query,
            "language": request.language or "en",
            "top_k": request.top_k,
            "min_score": effective_min_score,
            "contexts": [],
            "answer": "",
            "is_refusal": False,
            "sources": [],
            "trace_id": trace_id,
            "node_history": [],
            "step_latencies": {},
            "error": None,
        }
        run_config: Dict[str, Any] = {"configurable": {"thread_id": trace_id}}

        try:
            final_state: Dict[str, Any] = self._compiled_graph.invoke(
                initial_state,
                config=run_config,  # type: ignore[arg-type]
            )
        except KnowledgeBaseUnavailableException:
            raise
        except WorkflowExecutionError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(
                message="An internal error occurred while processing the agent workflow.",
                trace_id=trace_id,
            ) from exc

        node_sequence: List[str] = list(final_state.get("node_history") or [])
        step_latencies: Dict[str, float] = {
            str(k): float(v)
            for k, v in (final_state.get("step_latencies") or {}).items()
        }
        elapsed_ms = round((time.perf_counter() - start_ns) * 1000.0, 3)
        step_sum_ms = round(sum(step_latencies.values()), 3)
        total_duration_ms = max(elapsed_ms, step_sum_ms, 0.01)

        sanitized_query = str(final_state.get("query") or request.query)
        final_answer = str(final_state.get("answer") or "")
        is_refusal = bool(final_state.get("is_refusal", False))
        sources: List[SourceCitation] = list(final_state.get("sources") or [])

        checkpoints = self.get_checkpoints(trace_id)
        trace = AgentTrace(
            trace_id=trace_id,
            query=sanitized_query,
            node_sequence=node_sequence,
            step_latencies=step_latencies,
            total_duration_ms=total_duration_ms,
            is_refusal=is_refusal,
            final_answer=final_answer,
            source_count=len(sources),
            created_at=datetime.now(timezone.utc),
            checkpoints=checkpoints,
        )
        self._trace_registry.record_trace(trace)

        return AgentQueryResult(
            query=sanitized_query,
            answer=final_answer,
            is_refusal=is_refusal,
            sources=sources,
            trace_id=trace_id,
            node_sequence=node_sequence,
            execution_time_ms=total_duration_ms,
        )

    def get_trace(self, trace_id: str) -> AgentTrace:
        """Retrieve a recorded AgentTrace by its trace_id.

        Args:
            trace_id: Unique trace UUID string.

        Returns:
            Matching AgentTrace record.

        Raises:
            TraceNotFoundError: When no trace exists for `trace_id`.
        """
        trace = self._trace_registry.get_trace(trace_id)
        if trace is None:
            raise TraceNotFoundError(trace_id=trace_id)
        return trace

    def get_checkpoints(self, thread_id: str) -> List[AgentCheckpoint]:
        """Inspect and return state checkpoints persisted by the checkpointer for `thread_id`.

        Args:
            thread_id: Thread or trace identifier.

        Returns:
            Chronological list of AgentCheckpoint snapshots.
        """
        config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        snapshots: List[AgentCheckpoint] = []
        try:
            history = list(
                self._compiled_graph.get_state_history(config)  # type: ignore[arg-type]
            )
        except Exception:
            return []

        for snapshot in reversed(history):
            cp_cfg = snapshot.config.get("configurable", {}) if snapshot.config else {}
            checkpoint_id = str(cp_cfg.get("checkpoint_id") or "")
            parent_cfg = (
                snapshot.parent_config.get("configurable", {})
                if snapshot.parent_config
                else {}
            )
            parent_id = (
                str(parent_cfg.get("checkpoint_id"))
                if parent_cfg.get("checkpoint_id")
                else None
            )
            values = dict(snapshot.values) if isinstance(snapshot.values, dict) else {}
            node_hist = values.get("node_history") or []
            current_node = str(node_hist[-1]) if node_hist else "__start__"
            created_at_str = str(getattr(snapshot, "created_at", "") or "")

            snapshots.append(
                AgentCheckpoint(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=parent_id,
                    node=current_node,
                    state_delta={
                        "query": values.get("query", ""),
                        "node_history": list(node_hist),
                        "is_refusal": bool(values.get("is_refusal", False)),
                        "context_count": len(values.get("contexts") or []),
                        "source_count": len(values.get("sources") or []),
                    },
                    timestamp=created_at_str,
                )
            )
        return snapshots

    def get_health(self) -> Dict[str, Any]:
        """Return operational health and compilation status of the agent workflow.

        Returns:
            Dictionary with status, compiled, nodes, and checkpointer name.
        """
        raw_name = type(self._checkpointer).__name__
        checkpointer_name = (
            "MemorySaver"
            if raw_name in ("InMemorySaver", "MemorySaver")
            else raw_name
        )
        return {
            "status": "healthy",
            "compiled": self._compiled_graph is not None,
            "nodes": list(REQUIRED_WORKFLOW_NODES),
            "checkpointer": checkpointer_name,
        }


__all__ = ["SupportAgentService"]
