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
import asyncio
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi.concurrency import run_in_threadpool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from application.services.agent_guardrails import (
    AuthorizationGuardrailValidator,
    InputGuardrailValidator,
    OutputGuardrailValidator,
    TwoTierContextSanitizer,
    wrap_untrusted_content,
)
from application.services.agent_workflow import (
    REQUIRED_WORKFLOW_NODES,
    _format_inventory_records_summary,
    _format_ticket_records_summary,
    _parse_structured_llm_output,
    build_agent_checkpoint_serializer,
    build_support_agent_graph,
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
from application.services.guardrail_observability import GuardrailObservabilityService
from application.services.guardrails import BusinessGuardrailValidator
from application.services.trace_registry import TraceRegistry
from data.pipelines.rag_pipeline import generate_answer as rag_generate_answer
from domain.agent.entities import (
    AgentCheckpoint,
    AgentQueryRequest,
    AgentQueryResult,
    AgentState,
    AgentTrace,
    ChatInterruptedReason,
    ChatMessage,
    ChatThreadState,
    GuardrailAuditEvent,
    InventoryToolOutput,
    MemoryProposal,
    OperatingCountry,
    RetrievedContext,
    SourceCitation,
    TicketToolOutput,
)
from domain.agent.exceptions import (
    ThreadOwnershipMismatchError,
    TraceNotFoundError,
    WorkflowExecutionError,
)
from domain.agent.ports import (
    AgentChatEventBrokerPort,
    AgentChatThreadRepositoryPort,
    AuthorizationGuardrailPort,
    ContextSanitizerPort,
    GuardrailObservabilityPort,
    InputGuardrailPort,
    InventoryStockToolPort,
    OutputGuardrailPort,
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
        input_guard: Optional[InputGuardrailPort] = None,
        authorization_guard: Optional[AuthorizationGuardrailPort] = None,
        context_sanitizer: Optional[ContextSanitizerPort] = None,
        output_guard: Optional[OutputGuardrailPort] = None,
        guardrail_observability: Optional[GuardrailObservabilityPort] = None,
        chat_thread_repository: Optional[AgentChatThreadRepositoryPort] = None,
        chat_event_broker: Optional[AgentChatEventBrokerPort] = None,
        token_stream_delay_seconds: float = 0.015,
    ) -> None:
        """Initialize SupportAgentService and compile the workflow graph at startup."""
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
        self._input_guard: InputGuardrailPort = input_guard or InputGuardrailValidator()
        self._authorization_guard: AuthorizationGuardrailPort = (
            authorization_guard or AuthorizationGuardrailValidator()
        )
        self._context_sanitizer: ContextSanitizerPort = (
            context_sanitizer or TwoTierContextSanitizer()
        )
        self._output_guard: OutputGuardrailPort = (
            output_guard or OutputGuardrailValidator()
        )
        self._guardrail_observability: GuardrailObservabilityPort = (
            guardrail_observability or GuardrailObservabilityService()
        )
        if chat_thread_repository is None:
            from infrastructure.adapters.tinydb_chat_thread_repository import (
                TinyDBAgentChatThreadRepository,
            )

            self._chat_thread_repository: AgentChatThreadRepositoryPort = (
                TinyDBAgentChatThreadRepository()
            )
        else:
            self._chat_thread_repository = chat_thread_repository

        if chat_event_broker is None:
            from infrastructure.messaging.agent_chat_event_broker import (
                get_agent_chat_event_broker_singleton,
            )

            self._chat_event_broker: AgentChatEventBrokerPort = (
                get_agent_chat_event_broker_singleton()
            )
        else:
            self._chat_event_broker = chat_event_broker

        self._token_stream_delay_seconds = max(0.0, float(token_stream_delay_seconds))
        self._checkpointer: BaseCheckpointSaver = (
            checkpointer
            if checkpointer is not None
            else MemorySaver(serde=build_agent_checkpoint_serializer())
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
                input_guard=self._input_guard,
                authorization_guard=self._authorization_guard,
                context_sanitizer=self._context_sanitizer,
                output_guard=self._output_guard,
                observability=self._guardrail_observability,
            )
        )

    @property
    def guardrail_observability(self) -> GuardrailObservabilityPort:
        """Return the active GuardrailObservabilityPort instance."""
        return self._guardrail_observability

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

    @property
    def chat_thread_repository(self) -> AgentChatThreadRepositoryPort:
        """Return the active AgentChatThreadRepositoryPort instance."""
        return self._chat_thread_repository

    @property
    def chat_event_broker(self) -> AgentChatEventBrokerPort:
        """Return the active AgentChatEventBrokerPort instance."""
        return self._chat_event_broker

    @staticmethod
    def tokenize_for_streaming(text: str) -> List[str]:
        """Split synthesized assistant text into natural progressive token chunks (preserving whitespace)."""
        if not text:
            return []
        tokens = re.findall(r"\S+\s*|\s+", text)
        return [tok for tok in tokens if tok]

    def get_or_create_thread_state(
        self,
        thread_id: str,
        session_id: str,
        owner_user_id: str,
        owner_email: Optional[str] = None,
    ) -> ChatThreadState:
        """Load or initialize a ChatThreadState bound to `owner_user_id`, raising ThreadOwnershipMismatchError on mismatch."""
        cleaned_thread = (thread_id or "").strip() or str(uuid.uuid4())
        cleaned_session = (session_id or "").strip() or cleaned_thread
        cleaned_owner = str(owner_user_id).strip()

        existing = self._chat_thread_repository.get_thread(cleaned_thread)
        if existing is not None:
            if existing.owner_user_id and existing.owner_user_id != cleaned_owner:
                raise ThreadOwnershipMismatchError(
                    thread_id=cleaned_thread,
                    requester_user_id=cleaned_owner,
                )
            self._chat_event_broker.sync_sequence_id(
                cleaned_thread, existing.latest_sequence_id
            )
            return existing

        now = datetime.now(timezone.utc)
        pending = (
            self._memory_service.get_pending_proposal(cleaned_thread)
            if self._memory_service is not None
            and hasattr(self._memory_service, "get_pending_proposal")
            else None
        )
        checkpoints = self.get_checkpoints(cleaned_thread)
        latest_cp = checkpoints[-1].checkpoint_id if checkpoints else None
        initial_thread = ChatThreadState(
            thread_id=cleaned_thread,
            session_id=cleaned_session,
            owner_user_id=cleaned_owner,
            owner_email=owner_email,
            messages=[],
            pending_proposal=pending if isinstance(pending, MemoryProposal) else None,
            session_context=None,
            latest_checkpoint_id=latest_cp,
            latest_sequence_id=self._chat_event_broker.get_latest_sequence_id(
                cleaned_thread
            ),
            created_at=now,
            updated_at=now,
        )
        return self._chat_thread_repository.save_thread(initial_thread)

    def get_thread_history(
        self,
        thread_id: str,
        requester_user_id: str,
        session_id: Optional[str] = None,
    ) -> Tuple[ChatThreadState, int]:
        """Return persisted thread history and checkpoint count, validating per-user thread ownership."""
        cleaned_thread = (thread_id or "").strip()
        cleaned_requester = str(requester_user_id).strip()
        existing = self._chat_thread_repository.get_thread(cleaned_thread)
        if existing is not None:
            if existing.owner_user_id and existing.owner_user_id != cleaned_requester:
                raise ThreadOwnershipMismatchError(
                    thread_id=cleaned_thread,
                    requester_user_id=cleaned_requester,
                )
            thread_state = existing
        else:
            thread_state = self.get_or_create_thread_state(
                thread_id=cleaned_thread,
                session_id=session_id or cleaned_thread,
                owner_user_id=cleaned_requester,
            )

        checkpoints = self.get_checkpoints(cleaned_thread)
        latest_cp = (
            checkpoints[-1].checkpoint_id
            if checkpoints
            else thread_state.latest_checkpoint_id
        )
        pending = (
            self._memory_service.get_pending_proposal(cleaned_thread)
            if self._memory_service is not None
            and hasattr(self._memory_service, "get_pending_proposal")
            else None
        )
        resolved_pending = (
            pending
            if isinstance(pending, MemoryProposal)
            else thread_state.pending_proposal
        )
        latest_seq = max(
            thread_state.latest_sequence_id,
            self._chat_event_broker.get_latest_sequence_id(cleaned_thread),
        )
        self._chat_event_broker.sync_sequence_id(cleaned_thread, latest_seq)

        reconciled = ChatThreadState(
            thread_id=thread_state.thread_id,
            session_id=session_id or thread_state.session_id,
            owner_user_id=thread_state.owner_user_id,
            owner_email=thread_state.owner_email,
            messages=list(thread_state.messages),
            pending_proposal=resolved_pending,
            session_context=thread_state.session_context,
            latest_checkpoint_id=latest_cp,
            latest_sequence_id=latest_seq,
            created_at=thread_state.created_at,
            updated_at=thread_state.updated_at,
        )
        if (
            reconciled.latest_checkpoint_id != thread_state.latest_checkpoint_id
            or reconciled.latest_sequence_id != thread_state.latest_sequence_id
        ):
            reconciled = self._chat_thread_repository.save_thread(reconciled)
        return (reconciled, len(checkpoints))

    def rehydrate_thread(
        self,
        thread_id: str,
        session_id: str,
        owner_user_id: str,
        owner_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a session_rehydrated event payload from durable TinyDB history and LangGraph checkpoints."""
        self.get_or_create_thread_state(
            thread_id=thread_id,
            session_id=session_id,
            owner_user_id=owner_user_id,
            owner_email=owner_email,
        )
        thread_state, checkpoint_count = self.get_thread_history(
            thread_id=thread_id,
            requester_user_id=owner_user_id,
            session_id=session_id,
        )
        return {
            "owner_user_id": thread_state.owner_user_id,
            "messages": [m.to_dict() for m in thread_state.messages],
            "pending_proposal": (
                thread_state.pending_proposal.to_dict()
                if thread_state.pending_proposal is not None
                else None
            ),
            "latest_checkpoint_id": thread_state.latest_checkpoint_id,
            "checkpoint_count": checkpoint_count,
        }

    def _prepare_pre_generation_state(
        self,
        request: AgentQueryRequest,
        thread_id: str,
        trace_id: str,
        conversation_history: List[Dict[str, Any]],
    ) -> Tuple[AgentState, str, List[SourceCitation], Optional[Dict[str, Any]]]:
        """Execute pre-stream workflow stages (Layer 1-3 guardrails, memory recall, tools, RAG, and candidate synthesis)."""
        effective_min_score = (
            request.min_score
            if request.min_score is not None
            else self.config.similarity_threshold
        )
        state: AgentState = {
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
            "session_context": request.session_context,
            "resolved_country": (
                request.session_context.primary_operating_country
                if request.session_context is not None
                else None
            ),
            "guardrail_action": "allow",
            "guardrail_failure_category": "none",
            "guardrail_reason_code": None,
            "guardrail_message": None,
            "casual_redirect_required": False,
            "guardrail_events": [],
        }
        if conversation_history:
            state["conversation_history"] = conversation_history  # type: ignore[typeddict-unknown-key]

        # 1. Intake node (Layer 1 Input Guardrail + Layer 2 Auth Guardrail + Memory Proposal Resolution & Recall)
        state.update(
            intake_node(
                state=state,
                memory_service=self._memory_service,
                input_guard=self._input_guard,
                authorization_guard=self._authorization_guard,
                observability=self._guardrail_observability,
            )
        )
        next_node = route_after_intake(state)

        while next_node not in ("generation", "refusal", "__end__"):
            if next_node == "ticket_tool":
                state.update(
                    ticket_tool_node(
                        state=state,
                        ticket_tool=self._ticket_tool,
                        context_sanitizer=self._context_sanitizer,
                        observability=self._guardrail_observability,
                        authorization_guard=self._authorization_guard,
                    )
                )
                next_node = route_after_ticket_tool(state)
            elif next_node == "inventory_tool":
                state.update(
                    inventory_tool_node(
                        state=state,
                        inventory_tool=self._inventory_tool,
                        context_sanitizer=self._context_sanitizer,
                        observability=self._guardrail_observability,
                        authorization_guard=self._authorization_guard,
                    )
                )
                next_node = route_after_inventory_tool(state)
            elif next_node == "retrieval":
                state.update(
                    retrieval_node(
                        state=state,
                        vector_store=self._vector_store,
                        embedding_service=self._embedding_service,
                        default_min_score=self.config.similarity_threshold,
                        context_sanitizer=self._context_sanitizer,
                        observability=self._guardrail_observability,
                    )
                )
                next_node = route_after_retrieval(state)
            elif next_node == "tool_fallback":
                state.update(tool_fallback_node(state))
                routed = route_after_tool_fallback(state)
                next_node = "generation" if routed == "generation" else "__end__"
            else:
                break

        if next_node == "refusal":
            state.update(
                refusal_node(
                    state=state,
                    output_guard=self._output_guard,
                    observability=self._guardrail_observability,
                )
            )
            return (state, str(state.get("answer") or ""), [], None)

        if next_node == "__end__":
            return (state, str(state.get("answer") or ""), [], None)

        # Synthesize candidate answer text before token-by-token streaming
        query = state.get("query") or ""
        language = state.get("language") or "en"
        contexts: List[RetrievedContext] = list(state.get("contexts") or [])
        ticket_out = state.get("ticket_tool_output")
        inv_out = state.get("inventory_tool_output")
        fallback_messages: List[str] = list(state.get("fallback_messages") or [])
        recalled_memories: List[str] = list(state.get("recalled_memories") or [])
        proposal_resolution: Optional[Dict[str, Any]] = state.get("proposal_resolution")
        casual_redirect_required = bool(state.get("casual_redirect_required", False))
        guardrail_message = state.get("guardrail_message")

        segments: List[str] = []
        citations: List[SourceCitation] = []
        structured_llm_candidate: Optional[Dict[str, Any]] = None

        pure_proposal_turn = False
        if proposal_resolution is not None:
            ack_text = proposal_resolution.get("acknowledgment_text")
            intent = proposal_resolution.get("classified_intent")
            has_residual = bool(proposal_resolution.get("residual_query"))
            if ack_text and (
                intent in ("approve", "reject", "edit")
                or (intent == "unrelated_or_ambiguous" and not has_residual)
            ):
                segments.append(str(ack_text))
            if not has_residual:
                pure_proposal_turn = True

        if casual_redirect_required and guardrail_message:
            segments.append(str(guardrail_message))
        else:
            if recalled_memories and not pure_proposal_turn:
                recalled_text = (
                    "Operational Memory Context (Confirmed Cross-Session Rules):\n"
                    + "\n".join(
                        f"- {mem} ( recommend using local carrier alternatives accordingly )"
                        for mem in recalled_memories
                    )
                )
                segments.append(recalled_text)

            if not pure_proposal_turn:
                if (
                    ticket_out is not None
                    and ticket_out.status == "success"
                    and ticket_out.records
                ):
                    segments.append(
                        _format_ticket_records_summary(
                            ticket_out,
                            query=query,
                            language=language,
                        )
                    )
                if inv_out is not None and inv_out.status == "success" and inv_out.records:
                    segments.append(_format_inventory_records_summary(inv_out))
                if fallback_messages:
                    segments.append(" ".join(fallback_messages))

                if contexts or not segments:
                    enforced_rag_answer, rag_citations = rag_generate_answer(
                        question=query,
                        context=contexts,
                        llm_generator=self._llm_generator,
                        guardrail_validator=self._guardrails,
                        language=language,
                    )
                    parsed_answer, parsed_candidate = _parse_structured_llm_output(
                        enforced_rag_answer
                    )
                    if parsed_candidate is not None:
                        structured_llm_candidate = parsed_candidate
                        enforced_rag_answer = self._guardrails.enforce(
                            query=query,
                            answer=parsed_answer,
                            contexts=contexts,
                        )
                    segments.append(enforced_rag_answer)
                    citations = list(rag_citations)

        candidate_answer = "\n\n".join(seg for seg in segments if seg).strip()
        node_history = list(state.get("node_history") or [])
        if "generation" not in node_history:
            node_history.append("generation")
        state["node_history"] = node_history
        return (state, candidate_answer, citations, structured_llm_candidate)

    async def stream_query(
        self,
        request: AgentQueryRequest,
        owner_user_id: str,
        owner_email: Optional[str] = None,
        session_id: Optional[str] = None,
        user_turn_id: Optional[str] = None,
        assistant_turn_id: Optional[str] = None,
        abort_event: Optional[asyncio.Event] = None,
        broker: Optional[AgentChatEventBrokerPort] = None,
        thread_repository: Optional[AgentChatThreadRepositoryPort] = None,
        chunk_delay_seconds: Optional[float] = None,
    ) -> ChatMessage:
        """Stream an assistant response token-by-token over `AgentChatEventBrokerPort` with cooperative cancellation.

        Sequencing (FR-004..FR-010, Clarifications 2 & 3):
        1. Validates thread ownership and persists the incoming user `ChatMessage`.
        2. Emits `generation_started` and creates an in-flight `streaming` assistant `ChatMessage`.
        3. Runs Layer 1-3 intake, operational tools, and RAG retrieval.
        4. Streams progressive `token_chunk` events, checking `abort_event.is_set()` before every emission.
        5. If cancelled or `abort_event` is set at any point, immediately stops (0 trailing chunks),
           persists the partial accumulated text with `status="interrupted"`, and emits `generation_interrupted`.
        6. Once all tokens stream without interruption, runs Layer 4 `OutputGuardrailPort.validate_output()`,
           evaluates single-turn memory proposals, records the `AgentTrace` and LangGraph checkpoint,
           persists the completed assistant `ChatMessage`, and emits `generation_completed`.
        """
        start_ns = time.perf_counter()
        active_broker = broker or self._chat_event_broker
        active_repo = thread_repository or self._chat_thread_repository
        trace_id = str(uuid.uuid4())
        resolved_thread_id = (
            request.thread_id.strip()
            if request.thread_id and request.thread_id.strip()
            else trace_id
        )
        resolved_session_id = (
            (session_id or "").strip()
            or (
                request.session_context.session_id
                if request.session_context and request.session_context.session_id
                else ""
            )
            or resolved_thread_id
        )
        resolved_user_turn_id = (
            user_turn_id.strip()
            if user_turn_id and user_turn_id.strip()
            else f"usr_{uuid.uuid4().hex[:12]}"
        )
        resolved_assistant_turn_id = (
            assistant_turn_id.strip()
            if assistant_turn_id and assistant_turn_id.strip()
            else f"turn_{uuid.uuid4().hex[:12]}"
        )
        effective_delay = (
            max(0.0, float(chunk_delay_seconds))
            if chunk_delay_seconds is not None
            else self._token_stream_delay_seconds
        )

        # Ensure thread exists and is owned by owner_user_id
        thread_state = self.get_or_create_thread_state(
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            owner_user_id=owner_user_id,
            owner_email=owner_email,
        )
        prior_history = [
            {"role": m.role, "content": m.content, "status": m.status}
            for m in thread_state.messages
        ]

        now_start = datetime.now(timezone.utc)
        user_msg = ChatMessage(
            turn_id=resolved_user_turn_id,
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            role="user",
            content=request.query.strip(),
            status="completed",
            created_at=now_start,
            updated_at=now_start,
        )
        active_repo.append_or_update_message(
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            owner_user_id=owner_user_id,
            owner_email=owner_email,
            message=user_msg,
        )

        # Emit generation_started
        started_event = active_broker.publish(
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            event_name="generation_started",
            payload={
                "turn_id": resolved_assistant_turn_id,
                "user_turn_id": resolved_user_turn_id,
                "query": request.query.strip(),
            },
        )
        streaming_placeholder = ChatMessage(
            turn_id=resolved_assistant_turn_id,
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            role="assistant",
            content="",
            status="streaming",
            parent_user_turn_id=resolved_user_turn_id,
            trace_id=trace_id,
            created_at=now_start,
            updated_at=now_start,
        )
        active_repo.append_or_update_message(
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            owner_user_id=owner_user_id,
            owner_email=owner_email,
            message=streaming_placeholder,
            latest_sequence_id=started_event.sequence_id,
        )

        accumulated_parts: List[str] = []
        state: AgentState = {}
        finalization_lock = threading.RLock()
        turn_finalized = False
        interrupted_result: Optional[ChatMessage] = None

        def _resolve_abort_reason() -> ChatInterruptedReason:
            if hasattr(active_broker, "get_abort_reason"):
                reason = active_broker.get_abort_reason(resolved_thread_id)
                if reason in (
                    "client_interrupt",
                    "redirect_new_message",
                    "client_disconnect",
                ):
                    return reason
            return "client_interrupt"

        def _persist_and_publish_interrupted(
            reason: ChatInterruptedReason,
        ) -> ChatMessage:
            nonlocal turn_finalized, interrupted_result
            with finalization_lock:
                if turn_finalized and interrupted_result is not None:
                    return interrupted_result
                turn_finalized = True

                partial_text = "".join(accumulated_parts)
                now_abort = datetime.now(timezone.utc)
                elapsed_abort_ms = max(
                    0.01, round((time.perf_counter() - start_ns) * 1000.0, 3)
                )
                interrupted_event = active_broker.publish(
                    thread_id=resolved_thread_id,
                    session_id=resolved_session_id,
                    event_name="generation_interrupted",
                    payload={
                        "turn_id": resolved_assistant_turn_id,
                        "partial_content": partial_text,
                        "status": "interrupted",
                        "reason": reason,
                    },
                )
                interrupted_msg = ChatMessage(
                    turn_id=resolved_assistant_turn_id,
                    thread_id=resolved_thread_id,
                    session_id=resolved_session_id,
                    role="assistant",
                    content=partial_text,
                    status="interrupted",
                    parent_user_turn_id=resolved_user_turn_id,
                    interrupted_reason=reason,
                    is_refusal=bool(state.get("is_refusal", False)),
                    fallback_triggered=bool(state.get("fallback_triggered", False)),
                    trace_id=trace_id,
                    node_sequence=list(state.get("node_history") or []),
                    execution_time_ms=elapsed_abort_ms,
                    sources=[],
                    sources_consulted=[
                        str(s) for s in (state.get("sources_consulted") or [])
                    ],
                    tool_calls=[],
                    memory_proposal=None,
                    recalled_memories=[
                        str(m) for m in (state.get("recalled_memories") or [])
                    ],
                    guardrail_interventions=[
                        ev
                        for ev in (state.get("guardrail_events") or [])
                        if isinstance(ev, GuardrailAuditEvent)
                    ],
                    resolved_country=(
                        state.get("resolved_country")
                        if state.get("resolved_country") in ("US", "ES")
                        else None
                    ),
                    created_at=now_start,
                    updated_at=now_abort,
                )
                active_repo.append_or_update_message(
                    thread_id=resolved_thread_id,
                    session_id=resolved_session_id,
                    owner_user_id=owner_user_id,
                    owner_email=owner_email,
                    message=interrupted_msg,
                    latest_sequence_id=interrupted_event.sequence_id,
                )
                interrupted_result = interrupted_msg
                return interrupted_msg

        if hasattr(active_broker, "register_abort_finalizer"):
            getattr(active_broker, "register_abort_finalizer")(
                resolved_thread_id,
                resolved_assistant_turn_id,
                _persist_and_publish_interrupted,
            )

        try:
            if turn_finalized or (abort_event is not None and abort_event.is_set()):
                return _persist_and_publish_interrupted(_resolve_abort_reason())

            state, candidate_answer, citations, structured_llm_candidate = (
                await run_in_threadpool(
                    self._prepare_pre_generation_state,
                    request,
                    resolved_thread_id,
                    trace_id,
                    prior_history,
                )
            )

            if turn_finalized or (abort_event is not None and abort_event.is_set()):
                return _persist_and_publish_interrupted(_resolve_abort_reason())

            tokens = self.tokenize_for_streaming(candidate_answer)
            for chunk_index, token_delta in enumerate(tokens):
                with finalization_lock:
                    if turn_finalized or (
                        abort_event is not None and abort_event.is_set()
                    ):
                        return _persist_and_publish_interrupted(
                            _resolve_abort_reason()
                        )

                    accumulated_parts.append(token_delta)
                    accumulated_text = "".join(accumulated_parts)
                    active_broker.publish(
                        thread_id=resolved_thread_id,
                        session_id=resolved_session_id,
                        event_name="token_chunk",
                        payload={
                            "turn_id": resolved_assistant_turn_id,
                            "chunk_index": chunk_index,
                            "delta": token_delta,
                            "accumulated_content": accumulated_text,
                        },
                    )
                if effective_delay > 0:
                    await asyncio.sleep(effective_delay)

            if turn_finalized or (abort_event is not None and abort_event.is_set()):
                return _persist_and_publish_interrupted(_resolve_abort_reason())

        except asyncio.CancelledError:
            return _persist_and_publish_interrupted(_resolve_abort_reason())

        with finalization_lock:
            if turn_finalized or (abort_event is not None and abort_event.is_set()):
                return _persist_and_publish_interrupted(_resolve_abort_reason())
            turn_finalized = True

        # Post-stream Layer 4 Output Guardrail validation before generation_completed (Clarification 3, FR-006)
        final_answer = "".join(accumulated_parts).strip() or candidate_answer
        sanitized_query = str(state.get("query") or request.query)
        language = str(state.get("language") or request.language or "en")
        session_ctx = state.get("session_context")
        casual_redirect_required = bool(state.get("casual_redirect_required", False))
        guardrail_action = state.get("guardrail_action")
        guardrail_events: List[GuardrailAuditEvent] = [
            ev
            for ev in (state.get("guardrail_events") or [])
            if isinstance(ev, GuardrailAuditEvent)
        ]
        is_refusal = bool(state.get("is_refusal", False))
        memory_proposal: Optional[MemoryProposal] = None
        proposal_resolution = state.get("proposal_resolution")
        if proposal_resolution and proposal_resolution.get("status") == "edited":
            updated_prop = proposal_resolution.get("updated_proposal")
            if isinstance(updated_prop, MemoryProposal):
                memory_proposal = updated_prop

        if not is_refusal:
            output_eval = self._output_guard.validate_output(
                query=sanitized_query,
                candidate_answer=final_answer,
                session_context=session_ctx,
                casual_redirect_required=casual_redirect_required,
                language=language,
            )
            if self._guardrail_observability is not None:
                ev = self._guardrail_observability.record_evaluation(
                    result=output_eval,
                    session_id=resolved_session_id,
                    raw_preview=final_answer,
                    trace_id=trace_id,
                )
                if ev is not None:
                    guardrail_events.append(ev)

            is_output_blocked = output_eval.action == "block"
            if output_eval.sanitized_text is not None:
                final_answer = output_eval.sanitized_text
            if is_output_blocked:
                is_refusal = True
                citations = []

            should_suppress_memory_proposal = bool(
                is_output_blocked
                or casual_redirect_required
                or guardrail_action in ("block", "redirect", "deflect", "clarify")
            )
            if should_suppress_memory_proposal:
                memory_proposal = None
                if (
                    is_output_blocked
                    and self._memory_service is not None
                    and hasattr(self._memory_service, "discard_pending_proposal")
                ):
                    self._memory_service.discard_pending_proposal(
                        thread_id=resolved_thread_id,
                        reason=output_eval.reason_code or "output_guardrail_block",
                    )
            elif self._memory_service is not None and proposal_resolution is None:
                candidate_proposal, final_answer = (
                    self._memory_service.evaluate_turn_for_proposal(
                        user_message=sanitized_query,
                        base_answer=final_answer,
                        thread_id=resolved_thread_id,
                        language=language,
                        llm_candidate=structured_llm_candidate,
                    )
                )
                if candidate_proposal is not None:
                    memory_proposal = candidate_proposal

        state["answer"] = final_answer
        state["is_refusal"] = is_refusal
        state["sources"] = list(citations)
        state["memory_proposal"] = memory_proposal
        state["guardrail_events"] = guardrail_events

        node_sequence: List[str] = list(state.get("node_history") or [])
        sources_consulted: List[str] = [
            str(s) for s in (state.get("sources_consulted") or [])
        ]
        fallback_triggered = bool(state.get("fallback_triggered", False))
        tool_calls: List[Dict[str, Any]] = []
        ticket_out = state.get("ticket_tool_output")
        if isinstance(ticket_out, TicketToolOutput):
            tool_calls.append(ticket_out.to_trace_summary())
        inv_out = state.get("inventory_tool_output")
        if isinstance(inv_out, InventoryToolOutput):
            tool_calls.append(inv_out.to_trace_summary())

        step_latencies: Dict[str, float] = {
            str(k): float(v)
            for k, v in (state.get("step_latencies") or {}).items()
        }
        elapsed_ms = round((time.perf_counter() - start_ns) * 1000.0, 3)
        step_sum_ms = round(sum(step_latencies.values()), 3)
        total_duration_ms = max(elapsed_ms, step_sum_ms, 0.01)

        node_outputs: Dict[str, Dict[str, Any]] = {
            str(k): dict(v)
            for k, v in (state.get("node_outputs") or {}).items()
            if isinstance(v, dict)
        }
        try:
            self._compiled_graph.update_state(
                {"configurable": {"thread_id": resolved_thread_id}},  # type: ignore[arg-type]
                state,
            )
        except Exception:
            pass

        checkpoints = self.get_checkpoints(resolved_thread_id)
        latest_cp_id = checkpoints[-1].checkpoint_id if checkpoints else None
        trace = AgentTrace(
            trace_id=trace_id,
            query=sanitized_query,
            node_sequence=node_sequence,
            step_latencies=step_latencies,
            total_duration_ms=total_duration_ms,
            is_refusal=is_refusal,
            final_answer=final_answer,
            source_count=len(citations),
            sources_consulted=sources_consulted,
            fallback_triggered=fallback_triggered,
            tool_calls=tool_calls,
            node_outputs=node_outputs,
            created_at=datetime.now(timezone.utc),
            checkpoints=checkpoints,
        )
        self._trace_registry.record_trace(trace)

        recalled_memories: List[str] = [
            str(m) for m in (state.get("recalled_memories") or [])
        ]
        resolved_country_raw = state.get("resolved_country")
        resolved_country: Optional[OperatingCountry] = (
            resolved_country_raw
            if resolved_country_raw in ("US", "ES")
            else None
        )

        now_complete = datetime.now(timezone.utc)
        completed_msg = ChatMessage(
            turn_id=resolved_assistant_turn_id,
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            role="assistant",
            content=final_answer,
            status="completed",
            parent_user_turn_id=resolved_user_turn_id,
            interrupted_reason=None,
            is_refusal=is_refusal,
            fallback_triggered=fallback_triggered,
            trace_id=trace_id,
            node_sequence=node_sequence,
            execution_time_ms=total_duration_ms,
            sources=list(citations),
            sources_consulted=sources_consulted,
            tool_calls=tool_calls,
            memory_proposal=memory_proposal,
            recalled_memories=recalled_memories,
            guardrail_interventions=guardrail_events,
            resolved_country=resolved_country,
            created_at=now_start,
            updated_at=now_complete,
        )

        completed_event = active_broker.publish(
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            event_name="generation_completed",
            payload={
                "turn_id": resolved_assistant_turn_id,
                "query": sanitized_query,
                "content": final_answer,
                "status": "completed",
                "is_refusal": is_refusal,
                "fallback_triggered": fallback_triggered,
                "trace_id": trace_id,
                "node_sequence": node_sequence,
                "execution_time_ms": total_duration_ms,
                "sources": [
                    {
                        "source_document": s.source_document,
                        "section": s.section,
                        "similarity_score": round(float(s.similarity_score), 4),
                    }
                    for s in citations
                ],
                "sources_consulted": sources_consulted,
                "tool_calls": [dict(tc) for tc in tool_calls],
                "memory_proposal": (
                    memory_proposal.to_dict()
                    if memory_proposal is not None
                    else None
                ),
                "recalled_memories": recalled_memories,
                "guardrail_interventions": [
                    ev.to_dict() for ev in guardrail_events
                ],
                "resolved_country": resolved_country,
            },
        )
        active_repo.append_or_update_message(
            thread_id=resolved_thread_id,
            session_id=resolved_session_id,
            owner_user_id=owner_user_id,
            owner_email=owner_email,
            message=completed_msg,
            pending_proposal=memory_proposal,
            latest_checkpoint_id=latest_cp_id,
            latest_sequence_id=completed_event.sequence_id,
        )
        return completed_msg

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
            "session_context": request.session_context,
            "resolved_country": (
                request.session_context.primary_operating_country
                if request.session_context is not None
                else None
            ),
            "guardrail_action": "allow",
            "guardrail_failure_category": "none",
            "guardrail_reason_code": None,
            "guardrail_message": None,
            "casual_redirect_required": False,
            "guardrail_events": [],
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
        guardrail_interventions: List[GuardrailAuditEvent] = [
            ev
            for ev in (final_state.get("guardrail_events") or [])
            if isinstance(ev, GuardrailAuditEvent)
        ]
        resolved_country_raw = final_state.get("resolved_country")
        resolved_country: Optional[OperatingCountry] = (
            resolved_country_raw
            if resolved_country_raw in ("US", "ES")
            else None
        )

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
            guardrail_interventions=guardrail_interventions,
            resolved_country=resolved_country,
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
