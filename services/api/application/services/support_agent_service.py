"""Application service coordinating compiled Support Agent execution, tool wiring, tracing, and checkpointing.

Implements `SupportAgentServicePort` (T036, T037):
- Compiles the 7-node LangGraph workflow at initialization time (fail-fast structural validation)
- Wires `SupportTicketToolPort` and `InventoryStockToolPort` into the compiled state graph
- Invokes the compiled graph with a thread-scoped `RunnableConfig` for state checkpointing
- Constructs an immutable `AgentTrace` record with node sequences, `sources_consulted`,
  `fallback_triggered`, `tool_calls`, and step latencies
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
    InventoryToolOutput,
    MemoryProposal,
    SourceCitation,
    TicketToolOutput,
)
from domain.agent.exceptions import (
    TraceNotFoundError,
    WorkflowExecutionError,
)
from domain.agent.ports import (
    InventoryStockToolPort,
    SupportAgentServicePort,
    SupportTicketToolPort,
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
        ticket_tool: Optional[SupportTicketToolPort] = None,
        inventory_tool: Optional[InventoryStockToolPort] = None,
        trace_registry: Optional[TraceRegistryPort] = None,
        guardrail_validator: Optional[BusinessGuardrailValidator] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        config: Optional[KnowledgeRuntimeConfig] = None,
        compiled_graph: Optional[CompiledStateGraph] = None,
        memory_service: Optional[Any] = None,
    ) -> None:
        """Initialize SupportAgentService and compile the workflow graph at startup.

        Args:
            vector_store: VectorStorePort implementation.
            embedding_service: EmbeddingServicePort implementation.
            llm_generator: LLMGenerationPort implementation.
            ticket_tool: Optional SupportTicketToolPort implementation.
            inventory_tool: Optional InventoryStockToolPort implementation.
            trace_registry: Optional TraceRegistryPort (defaults to new TraceRegistry).
            guardrail_validator: Optional BusinessGuardrailValidator instance.
            checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver).
            config: Optional KnowledgeRuntimeConfig loaded from .env.
            compiled_graph: Optional pre-compiled graph override.
            memory_service: Optional AgentMemoryService orchestrating persistent operational memory.
        """
        self.config = config or KnowledgeRuntimeConfig.from_env()
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_generator = llm_generator
        if ticket_tool is None:
            from infrastructure.adapters.mcp_ticket_tool_adapter import (
                McpTicketToolAdapter,
            )

            self._ticket_tool: SupportTicketToolPort = McpTicketToolAdapter(
                config=self.config
            )
        else:
            self._ticket_tool = ticket_tool

        if inventory_tool is None:
            from infrastructure.adapters.inventory_stock_tool_adapter import (
                InventoryStockQueryToolAdapter,
            )

            self._inventory_tool: InventoryStockToolPort = (
                InventoryStockQueryToolAdapter(config=self.config)
            )
        else:
            self._inventory_tool = inventory_tool

        if memory_service is None:
            from application.services.memory_guardrails import MemoryGuardrailValidator
            from application.services.memory_service import (
                AgentMemoryService,
                UserIntentClassifier,
            )
            from infrastructure.persistence.tinydb.agent_memory_repository import (
                TinyDBAgentMemoryRepository,
            )
            from infrastructure.persistence.tinydb.memory_audit_log_repository import (
                TinyDBMemoryAuditLogRepository,
            )

            self._memory_service: Any = AgentMemoryService(
                memory_repository=TinyDBAgentMemoryRepository(),
                audit_repository=TinyDBMemoryAuditLogRepository(),
                guardrail_validator=MemoryGuardrailValidator(),
                intent_classifier=UserIntentClassifier(),
            )
        else:
            self._memory_service = memory_service

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
                ticket_tool=self._ticket_tool,
                inventory_tool=self._inventory_tool,
                guardrail_validator=self._guardrails,
                checkpointer=self._checkpointer,
                default_min_score=self.config.similarity_threshold,
                memory_service=self._memory_service,
            )
        )

    @property
    def memory_service(self) -> Any:
        """Return the active AgentMemoryService instance."""
        return self._memory_service

    @property
    def compiled_graph(self) -> CompiledStateGraph:
        """Return the compiled LangGraph state machine."""
        return self._compiled_graph

    @property
    def trace_registry(self) -> TraceRegistryPort:
        """Return the active TraceRegistryPort instance."""
        return self._trace_registry

    @property
    def ticket_tool(self) -> SupportTicketToolPort:
        """Return the wired SupportTicketToolPort instance."""
        return self._ticket_tool

    @property
    def inventory_tool(self) -> InventoryStockToolPort:
        """Return the wired InventoryStockToolPort instance."""
        return self._inventory_tool

    def query(self, request: AgentQueryRequest) -> AgentQueryResult:
        """Execute a customer inquiry through the compiled LangGraph workflow.

        Args:
            request: Validated AgentQueryRequest domain object.

        Returns:
            AgentQueryResult with grounded answer, citations, trace_id, node sequence,
            sources_consulted, fallback_triggered, and tool_calls.

        Raises:
            KnowledgeBaseUnavailableException: When vector database is unreachable.
            WorkflowExecutionError: When an unhandled runtime fault occurs inside a node.
        """
        start_ns = time.perf_counter()
        trace_id = str(uuid.uuid4())
        thread_id = (
            request.thread_id.strip()
            if request.thread_id and request.thread_id.strip()
            else trace_id
        )
        effective_min_score = (
            request.min_score
            if request.min_score is not None
            else self.config.similarity_threshold
        )

        initial_state: AgentState = {
            "query": request.query,
            "thread_id": thread_id,
            "language": request.language or "en",
            "top_k": request.top_k,
            "min_score": effective_min_score,
            "selected_sources": [],
            "sources_consulted": [],
            "ticket_tool_input": None,
            "ticket_tool_output": None,
            "inventory_tool_input": None,
            "inventory_tool_output": None,
            "contexts": [],
            "fallback_triggered": False,
            "fallback_messages": [],
            "answer": "",
            "is_refusal": False,
            "sources": [],
            "trace_id": trace_id,
            "node_history": [],
            "step_latencies": {},
            "node_outputs": {},
            "error": None,
            "pending_proposal": None,
            "memory_proposal": None,
            "recalled_memories": [],
            "proposal_resolution": None,
        }
        run_config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}

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
        sources_consulted: List[str] = [
            str(s) for s in (final_state.get("sources_consulted") or [])
        ]
        fallback_triggered = bool(final_state.get("fallback_triggered", False))

        tool_calls: List[Dict[str, Any]] = []
        ticket_out = final_state.get("ticket_tool_output")
        if isinstance(ticket_out, TicketToolOutput):
            tool_calls.append(ticket_out.to_trace_summary())
        inv_out = final_state.get("inventory_tool_output")
        if isinstance(inv_out, InventoryToolOutput):
            tool_calls.append(inv_out.to_trace_summary())

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
        node_outputs: Dict[str, Dict[str, Any]] = {
            str(k): dict(v)
            for k, v in (final_state.get("node_outputs") or {}).items()
            if isinstance(v, dict)
        }

        checkpoints = self.get_checkpoints(thread_id)
        trace = AgentTrace(
            trace_id=trace_id,
            query=sanitized_query,
            node_sequence=node_sequence,
            step_latencies=step_latencies,
            total_duration_ms=total_duration_ms,
            is_refusal=is_refusal,
            final_answer=final_answer,
            source_count=len(sources),
            sources_consulted=sources_consulted,
            fallback_triggered=fallback_triggered,
            tool_calls=tool_calls,
            node_outputs=node_outputs,
            created_at=datetime.now(timezone.utc),
            checkpoints=checkpoints,
        )
        self._trace_registry.record_trace(trace)

        memory_proposal_raw = final_state.get("memory_proposal")
        memory_proposal: Optional[MemoryProposal] = (
            memory_proposal_raw
            if isinstance(memory_proposal_raw, MemoryProposal)
            else None
        )
        recalled_memories: List[str] = [
            str(m) for m in (final_state.get("recalled_memories") or [])
        ]

        return AgentQueryResult(
            query=sanitized_query,
            answer=final_answer,
            is_refusal=is_refusal,
            sources=sources,
            trace_id=trace_id,
            node_sequence=node_sequence,
            execution_time_ms=total_duration_ms,
            fallback_triggered=fallback_triggered,
            sources_consulted=sources_consulted,
            tool_calls=tool_calls,
            memory_proposal=memory_proposal,
            recalled_memories=recalled_memories,
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
                        "sources_consulted": list(values.get("sources_consulted") or []),
                        "fallback_triggered": bool(values.get("fallback_triggered", False)),
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
