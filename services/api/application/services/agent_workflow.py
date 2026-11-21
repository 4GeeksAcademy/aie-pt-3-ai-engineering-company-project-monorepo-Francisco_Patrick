"""LangGraph state workflow for the TrackFlow Support Agent.

Implements:
- 7 single-responsibility nodes:
  `intake_node`, `ticket_tool_node`, `inventory_tool_node`, `retrieval_node`,
  `tool_fallback_node`, `generation_node`, `refusal_node`
- Autonomous intent classification and parameter extraction (`classify_and_plan_query`)
  with canonical multi-source ordering (`ticket_tool` -> `inventory_tool` -> `rag`)
- Write/mutation guardrail refusal at intake (`detect_mutation_attempt`)
- 5 deterministic conditional routing edges:
  `route_after_intake`, `route_after_ticket_tool`, `route_after_inventory_tool`,
  `route_after_retrieval`, `route_after_tool_fallback`
- Build-time structural validation and compilation (`compile_and_validate_graph`, `build_support_agent_graph`)
- Per-node latency telemetry and `MemorySaver` state checkpointing.
"""

from pathlib import Path
import json
import re
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from application.services.agent_guardrails import (
    AuthorizationGuardrailValidator,
    InputGuardrailValidator,
    OutputGuardrailValidator,
    TwoTierContextSanitizer,
)
from application.services.guardrail_observability import GuardrailObservabilityService
from application.services.guardrails import BusinessGuardrailValidator
from application.services.knowledge_service import (
    DEFAULT_SIMILARITY_THRESHOLD,
    STANDARD_REFUSAL_MESSAGE,
    build_refusal_message,
)
from data.pipelines.rag_pipeline import (
    generate_answer as rag_generate_answer,
    retrieve as rag_retrieve,
)
from domain.agent.entities import (
    AgentState,
    AuthenticatedSessionContext,
    GuardrailAuditEvent,
    GuardrailEvaluationResult,
    InventoryRecordDTO,
    InventoryToolInput,
    InventoryToolOutput,
    MemoryProposal,
    OperatingCountry,
    RetrievedContext,
    SourceCitation,
    TicketRecordDTO,
    TicketToolInput,
    TicketToolOutput,
)
from domain.agent.exceptions import (
    GraphCompilationError,
    WorkflowExecutionError,
)
from domain.agent.ports import (
    AuthorizationGuardrailPort,
    ContextSanitizerPort,
    GuardrailObservabilityPort,
    InputGuardrailPort,
    InventoryStockToolPort,
    OutputGuardrailPort,
    SupportTicketToolPort,
)
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)

REQUIRED_WORKFLOW_NODES: Sequence[str] = (
    "intake",
    "ticket_tool",
    "inventory_tool",
    "retrieval",
    "tool_fallback",
    "generation",
    "refusal",
)

CANONICAL_SOURCE_ORDER: Sequence[str] = (
    "ticket_tool",
    "inventory_tool",
    "rag",
)

READ_ONLY_MUTATION_REFUSAL_MESSAGE = (
    "TrackFlow Support Agent operational tools are strictly read-only. "
    "I cannot create, modify, transition, close, or delete support tickets "
    "or update warehouse inventory stock records."
)

MAX_QUERY_LENGTH = 500
MIN_QUERY_LENGTH = 3

# --- Regex Patterns for Autonomous Routing & Guardrails ---
_TICKET_MUTATION_PATTERN = re.compile(
    r"(?:^\s*(?:please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+)?)"
    r"\b(?:close|delete|remove|discard|create|open\s+a\s+new|update|modify|change|mark|set|transition|resolve|reopen)\b"
    r"[^?.!]*\b(?:tickets?|incidents?|inc[-_][a-z0-9_-]+)\b",
    re.IGNORECASE,
)

_INVENTORY_MUTATION_PATTERN = re.compile(
    r"(?:^\s*(?:please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+)?)"
    r"\b(?:update|modify|set|change|delete|remove|add|create|adjust|increase|decrease|deduct|restock|dispatch)\b"
    r"[^?.!]*\b(?:stock|inventory|sku|units|inbound\s+order|outbound\s+order)\b",
    re.IGNORECASE,
)

_EXPLICIT_TICKET_ID_PATTERN = re.compile(
    r"\b(INC-[A-Za-z0-9_-]+|inc_[A-Za-z0-9_-]+|TICKET-[A-Za-z0-9_-]+)\b",
    re.IGNORECASE,
)

_GENERIC_TICKET_NUM_PATTERN = re.compile(
    r"\b(?:ticket|incident)\s*(?:#|id|number)?\s*[:=]?\s*([A-Za-z]{2,6}-\d+|inc_[A-Za-z0-9]+)\b",
    re.IGNORECASE,
)

_EXPLICIT_SKU_PATTERN = re.compile(
    r"\b(?:SKU\s*[:#-]?\s*([A-Za-z0-9]+-[A-Za-z0-9_-]+|[A-Za-z]{2,5}\d{2,6})|(TF-\d+|SKU-\d+|PRD-\d+|PROD-\d+))\b",
    re.IGNORECASE,
)

_PRODUCT_ID_PATTERN = re.compile(
    r"\bproduct\s*(?:id|#)\s*[:=]?\s*(\d+)\b",
    re.IGNORECASE,
)

_TICKET_KEYWORDS_PATTERN = re.compile(
    r"\b(?:tickets?|incidents?)\b",
    re.IGNORECASE,
)

_INVENTORY_KEYWORDS_PATTERN = re.compile(
    r"\b(?:in\s+stock|stock\s+levels?|stock\s+availability|current\s+stock|how\s+many\s+units|units\s+are\s+currently\s+in\s+stock|units\s+in\s+stock|low\s+stock|low-stock|warehouse\s+stock|inventory\s+stock|inventory\s+levels?|inventory\s+availability|available\s+units|stock\s+for\s+sku|stock\s+of\s+sku|products?\s+in\s+stock)\b",
    re.IGNORECASE,
)

_POLICY_RAG_KEYWORDS_PATTERN = re.compile(
    r"\b(?:return\s+window|return\s+policy|returns?\s+policy|return\s+shipping|shipping\s+costs?|shipping\s+fees?|"
    r"sla\b|delivery\s+tiers?|delivery\s+time|transit\s+time|storage\s+rates?|storage\s+pricing|monthly\s+storage|"
    r"pallet\s+rate|cubic\s+meter|storage\s+discount|discount\s+approval|miguel\s+torres|"
    r"claims?\s+policy|damaged\s+or\s+lost|lost\s+item|reporting\s+window|company\s+policy|standard\s+policy|"
    r"onboarding|governance|who\s+covers|who\s+approves|pharmaceutical|refrigeration)\b",
    re.IGNORECASE,
)

_KNOWN_BRANCHES = (
    "zaragoza",
    "los_angeles",
    "valencia",
    "central",
    "madrid",
    "barcelona",
    "bilbao",
    "sevilla",
)


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


def detect_mutation_attempt(query: str) -> bool:
    """Return True if the user inquiry attempts to mutate tickets or inventory stock (FR-019)."""
    if not query:
        return False
    if _TICKET_MUTATION_PATTERN.search(query):
        return True
    if _INVENTORY_MUTATION_PATTERN.search(query):
        return True
    return False


def _normalize_ticket_id(raw_id: str) -> str:
    """Normalize extracted ticket identifier casing (`INC-001` vs `inc_a1b2c3`)."""
    stripped = raw_id.strip()
    if stripped.lower().startswith("inc_"):
        return stripped.lower()
    if stripped.lower().startswith("inc-") or stripped.lower().startswith("ticket-"):
        return stripped.upper()
    return stripped


def _extract_ticket_tool_input(query: str) -> TicketToolInput:
    """Extract typed TicketToolInput criteria from a natural-language question."""
    explicit_match = _EXPLICIT_TICKET_ID_PATTERN.search(query)
    if explicit_match:
        return TicketToolInput(ticket_id=_normalize_ticket_id(explicit_match.group(1)))

    generic_match = _GENERIC_TICKET_NUM_PATTERN.search(query)
    if generic_match:
        return TicketToolInput(ticket_id=_normalize_ticket_id(generic_match.group(1)))

    lowered = query.lower()

    status: Optional[str] = None
    if re.search(r"\bin[\s_-]+progress\b", lowered):
        status = "in_progress"
    elif re.search(r"\bopen\b", lowered):
        status = "open"
    elif re.search(r"\bresolved\b", lowered):
        status = "resolved"
    elif re.search(r"\bdiscarded\b", lowered):
        status = "discarded"

    category: Optional[str] = None
    if re.search(r"\breverse[\s_-]+logistics\b", lowered):
        category = "reverse_logistics"
    elif re.search(r"\blast[\s_-]+mile\b", lowered):
        category = "last_mile"
    elif re.search(r"\bcustomer[\s_-]+experience\b", lowered):
        category = "customer_experience"
    else:
        for cat in ("warehouse", "delay", "damage", "billing", "stock", "system", "other"):
            if re.search(rf"\b{cat}(?:ed|s)?\b", lowered):
                # Avoid setting category="warehouse" if "originating from warehouse" was meant for origin, unless warehouse category is asked
                if cat == "warehouse" and re.search(r"\boriginating\s+from\s+warehouse\b", lowered):
                    continue
                category = cat
                break

    origin: Optional[str] = None
    for orig in ("customer", "branch", "internal", "warehouse", "carrier", "partner"):
        if orig == "branch" and re.search(r"\bbranch\s+[a-z_]+\b|\b[a-z_]+\s+branch\b", lowered):
            continue
        if re.search(rf"\b{orig}s?\b", lowered):
            origin = orig
            break

    branch: Optional[str] = None
    if "los angeles" in lowered or "los_angeles" in lowered:
        branch = "los_angeles"
    else:
        for br in _KNOWN_BRANCHES:
            if re.search(rf"\b{br}\b", lowered):
                branch = br
                break

    return TicketToolInput(
        ticket_id=None,
        status=status,
        category=category,
        origin=origin,
        branch=branch,
        limit=20,
    )


def _extract_inventory_tool_input(query: str) -> InventoryToolInput:
    """Extract typed InventoryToolInput criteria from a natural-language question."""
    sku_match = _EXPLICIT_SKU_PATTERN.search(query)
    extracted_sku: Optional[str] = None
    if sku_match:
        raw_sku = sku_match.group(1) or sku_match.group(2)
        if raw_sku:
            extracted_sku = raw_sku.strip().upper()

    prod_id_match = _PRODUCT_ID_PATTERN.search(query)
    extracted_pid: Optional[int] = None
    if prod_id_match:
        try:
            extracted_pid = int(prod_id_match.group(1))
        except ValueError:
            extracted_pid = None

    lowered = query.lower()
    low_stock_only = bool(
        re.search(r"\b(?:low[\s_-]+stock|below\s+threshold|under\s+threshold)\b", lowered)
        and extracted_sku is None
        and extracted_pid is None
    )

    search_query: Optional[str] = None
    if extracted_sku is None and extracted_pid is None and not low_stock_only:
        for_match = re.search(
            r"\b(?:stock|units|availability|inventory)\s+(?:for|of)\s+([A-Za-z0-9 _-]+?)(?:\s+(?:are|is|in\s+stock|currently|right\s+now)|\?|$)",
            query,
            re.IGNORECASE,
        )
        if for_match:
            candidate = for_match.group(1).strip()
            if candidate and candidate.lower() not in ("sku", "product", "products", "all"):
                search_query = candidate

    return InventoryToolInput(
        product_id=extracted_pid,
        sku=extracted_sku,
        search_query=search_query,
        low_stock_only=low_stock_only,
        limit=20,
    )


def classify_and_plan_query(
    query: str,
) -> Tuple[List[str], Optional[TicketToolInput], Optional[InventoryToolInput]]:
    """Autonomously classify user inquiry intent and extract tool parameters (FR-024, FR-025).

    Orders selected sources canonically as a subset of `["ticket_tool", "inventory_tool", "rag"]`.

    Args:
        query: Sanitized natural-language user question.

    Returns:
        Tuple of `(selected_sources, ticket_tool_input, inventory_tool_input)`.
    """
    if not query or len(query.strip()) < MIN_QUERY_LENGTH:
        return ([], None, None)

    has_ticket_id = bool(
        _EXPLICIT_TICKET_ID_PATTERN.search(query)
        or _GENERIC_TICKET_NUM_PATTERN.search(query)
    )
    has_ticket_keyword = bool(_TICKET_KEYWORDS_PATTERN.search(query))
    needs_ticket_tool = has_ticket_id or has_ticket_keyword

    has_sku_or_pid = bool(
        _EXPLICIT_SKU_PATTERN.search(query) or _PRODUCT_ID_PATTERN.search(query)
    )
    has_inventory_keyword = bool(_INVENTORY_KEYWORDS_PATTERN.search(query))
    needs_inventory_tool = has_sku_or_pid or has_inventory_keyword

    has_policy_keyword = bool(_POLICY_RAG_KEYWORDS_PATTERN.search(query))
    needs_rag = has_policy_keyword or (not needs_ticket_tool and not needs_inventory_tool)

    selected_sources: List[str] = []
    ticket_input: Optional[TicketToolInput] = None
    inventory_input: Optional[InventoryToolInput] = None

    if needs_ticket_tool:
        selected_sources.append("ticket_tool")
        ticket_input = _extract_ticket_tool_input(query)

    if needs_inventory_tool:
        selected_sources.append("inventory_tool")
        inventory_input = _extract_inventory_tool_input(query)

    if needs_rag:
        selected_sources.append("rag")

    return (selected_sources, ticket_input, inventory_input)


def intake_node(
    state: AgentState,
    memory_service: Optional[Any] = None,
    input_guard: Optional[InputGuardrailPort] = None,
    authorization_guard: Optional[AuthorizationGuardrailPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> AgentState:
    """Single-responsibility intake node for input validation, sanitization, guardrail evaluation, memory intent resolution, recall, autonomous routing, and trace initialization.

    Args:
        state: Incoming AgentState dictionary.
        memory_service: Optional AgentMemoryService for pending proposal resolution and cross-session memory recall.
        input_guard: Optional InputGuardrailPort enforcing anti-jailbreak, personal task refusal, and casual trivia redirect.
        authorization_guard: Optional AuthorizationGuardrailPort enforcing session-scoped order authorization and US/Spain policy separation.
        observability: Optional GuardrailObservabilityPort for recording guardrail triggers.

    Returns:
        Updated AgentState with sanitized query, canonical `selected_sources`, extracted tool inputs,
        `recalled_memories`, `proposal_resolution`, guardrail state, initialized `trace_id`, `node_history`, and `step_latencies`.
    """
    start_ns = time.perf_counter()

    raw_query = state.get("query")
    sanitized_query = sanitize_agent_query(raw_query)

    trace_id = state.get("trace_id") or str(uuid.uuid4())
    thread_id = state.get("thread_id") or trace_id
    session_context: Optional[AuthenticatedSessionContext] = state.get("session_context")
    session_id = (
        session_context.session_id
        if session_context and session_context.session_id
        else thread_id
    )
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

    resolved_input_guard = input_guard or InputGuardrailValidator()
    resolved_auth_guard = authorization_guard or AuthorizationGuardrailValidator()
    guardrail_events: List[GuardrailAuditEvent] = list(
        state.get("guardrail_events") or []
    )

    # 1. Layer 1 & Layer 2 Guardrail Evaluation BEFORE resolving pending memory proposals (FR-001, FR-003..FR-008)
    input_eval = resolved_input_guard.evaluate_input(
        query=sanitized_query,
        language=language,
    )
    if observability is not None:
        ev = observability.record_evaluation(
            result=input_eval,
            session_id=session_id,
            raw_preview=sanitized_query,
            trace_id=trace_id,
        )
        if ev is not None:
            guardrail_events.append(ev)

    auth_eval: Optional[GuardrailEvaluationResult] = None
    if input_eval.action != "block":
        auth_eval = resolved_auth_guard.evaluate_authorization_and_policy(
            query=sanitized_query,
            session_context=session_context,
            language=language,
        )
        if observability is not None:
            ev = observability.record_evaluation(
                result=auth_eval,
                session_id=session_id,
                raw_preview=sanitized_query,
                trace_id=trace_id,
            )
            if ev is not None:
                guardrail_events.append(ev)

    resolved_country: Optional[OperatingCountry] = (
        auth_eval.resolved_country
        if auth_eval is not None and auth_eval.resolved_country
        else (
            session_context.primary_operating_country
            if session_context is not None
            else state.get("resolved_country")
        )
    )

    active_block_eval: Optional[GuardrailEvaluationResult] = None
    if input_eval.action == "block":
        active_block_eval = input_eval
    elif auth_eval is not None and auth_eval.action == "block":
        active_block_eval = auth_eval

    is_guardrail_block = active_block_eval is not None
    casual_redirect_required = bool(
        not is_guardrail_block and input_eval.action == "redirect"
    )
    guardrail_action = (
        "block"
        if is_guardrail_block
        else ("redirect" if casual_redirect_required else "allow")
    )
    guardrail_failure_category = (
        active_block_eval.failure_category
        if active_block_eval is not None
        else (
            input_eval.failure_category
            if casual_redirect_required
            else "none"
        )
    )
    guardrail_reason_code = (
        active_block_eval.reason_code
        if active_block_eval is not None
        else (
            input_eval.reason_code
            if casual_redirect_required
            else None
        )
    )
    guardrail_message = (
        active_block_eval.message
        if active_block_eval is not None
        else (
            input_eval.message
            if casual_redirect_required
            else None
        )
    )

    # Discard active pending memory proposal if the user's turn triggers a guardrail block (FR-001)
    if is_guardrail_block and memory_service is not None and hasattr(memory_service, "discard_pending_proposal"):
        memory_service.discard_pending_proposal(
            thread_id=thread_id,
            reason=guardrail_reason_code or "guardrail_block",
        )

    # 2. Evaluate pending memory proposal if active on this thread and turn was not blocked or casual-redirected
    proposal_resolution: Optional[Dict[str, Any]] = state.get("proposal_resolution")
    effective_query = sanitized_query
    if (
        not is_guardrail_block
        and not casual_redirect_required
        and memory_service is not None
        and len(sanitized_query) >= 2
    ):
        pending = memory_service.get_pending_proposal(thread_id)
        if pending is not None:
            proposal_resolution = memory_service.resolve_pending_proposal(
                thread_id=thread_id,
                user_message=sanitized_query,
            )
            if proposal_resolution is not None:
                residual = proposal_resolution.get("residual_query")
                if residual:
                    effective_query = sanitize_agent_query(str(residual))

    is_invalid = (
        len(sanitized_query) < MIN_QUERY_LENGTH
        and proposal_resolution is None
        and not is_guardrail_block
        and not casual_redirect_required
    )
    is_mutation = (
        False
        if is_invalid or proposal_resolution is not None or is_guardrail_block
        else detect_mutation_attempt(effective_query)
    )
    is_refusal = bool(is_invalid or is_mutation or is_guardrail_block)

    sources_consulted = list(state.get("sources_consulted") or [])
    recalled_memories: List[str] = list(state.get("recalled_memories") or [])

    if is_refusal:
        selected_sources: List[str] = []
        ticket_input: Optional[TicketToolInput] = None
        inventory_input: Optional[InventoryToolInput] = None
    elif casual_redirect_required:
        # Casual small talk / general logistics trivia routes directly to generation with pre-built redirected answer
        selected_sources = []
        ticket_input = None
        inventory_input = None
    else:
        # 3. Cross-session memory recall (T028, FR-006, FR-007)
        if memory_service is not None and not recalled_memories:
            recalled_memories = memory_service.recall_relevant_memories(effective_query)
            if recalled_memories and "agent_memory" not in sources_consulted:
                sources_consulted.append("agent_memory")

        # If this turn purely resolved a pending proposal with no residual operational question,
        # skip tool/RAG lookups and route straight to generation.
        if (
            proposal_resolution is not None
            and not proposal_resolution.get("residual_query")
        ):
            selected_sources = []
            ticket_input = None
            inventory_input = None
        else:
            selected_sources, ticket_input, inventory_input = classify_and_plan_query(
                effective_query
            )
            # Preserve caller-supplied tool inputs when explicitly pre-populated in unit tests
            if state.get("ticket_tool_input") is not None:
                ticket_input = state.get("ticket_tool_input")
            if state.get("inventory_tool_input") is not None:
                inventory_input = state.get("inventory_tool_input")
            if state.get("selected_sources"):
                raw_selected = list(state.get("selected_sources") or [])
                selected_sources = [
                    src for src in CANONICAL_SOURCE_ORDER if src in raw_selected
                ] or selected_sources

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["intake"] = elapsed_ms

    node_outputs: Dict[str, Dict[str, Any]] = dict(state.get("node_outputs") or {})
    node_outputs["intake"] = {
        "query": sanitized_query,
        "effective_query": effective_query,
        "language": language,
        "top_k": top_k,
        "min_score": min_score,
        "is_valid": not is_invalid,
        "is_mutation_attempt": is_mutation,
        "guardrail_action": guardrail_action,
        "guardrail_failure_category": guardrail_failure_category,
        "guardrail_reason_code": guardrail_reason_code,
        "resolved_country": resolved_country,
        "casual_redirect_required": casual_redirect_required,
        "selected_sources": list(selected_sources),
        "ticket_tool_input": ticket_input.to_dict() if ticket_input else None,
        "inventory_tool_input": inventory_input.to_dict() if inventory_input else None,
        "recalled_memories_count": len(recalled_memories),
        "proposal_resolution": (
            {
                "status": proposal_resolution.get("status"),
                "classified_intent": proposal_resolution.get("classified_intent"),
                "resulting_action": proposal_resolution.get("resulting_action"),
            }
            if proposal_resolution
            else None
        ),
    }

    return {
        "query": sanitized_query,
        "thread_id": thread_id,
        "language": language,
        "top_k": top_k,
        "min_score": min_score,
        "selected_sources": selected_sources,
        "sources_consulted": sources_consulted,
        "ticket_tool_input": ticket_input,
        "ticket_tool_output": state.get("ticket_tool_output"),
        "inventory_tool_input": inventory_input,
        "inventory_tool_output": state.get("inventory_tool_output"),
        "contexts": list(state.get("contexts") or []),
        "fallback_triggered": bool(state.get("fallback_triggered", False)),
        "fallback_messages": list(state.get("fallback_messages") or []),
        "answer": state.get("answer") or "",
        "is_refusal": is_refusal,
        "sources": list(state.get("sources") or []),
        "trace_id": trace_id,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "node_outputs": node_outputs,
        "error": state.get("error"),
        "pending_proposal": state.get("pending_proposal"),
        "memory_proposal": state.get("memory_proposal"),
        "recalled_memories": recalled_memories,
        "proposal_resolution": proposal_resolution,
        "session_context": session_context,
        "resolved_country": resolved_country,
        "guardrail_action": guardrail_action,
        "guardrail_failure_category": guardrail_failure_category,
        "guardrail_reason_code": guardrail_reason_code,
        "guardrail_message": guardrail_message,
        "casual_redirect_required": casual_redirect_required,
        "guardrail_events": guardrail_events,
    }


def ticket_tool_node(
    state: AgentState,
    ticket_tool: SupportTicketToolPort,
    context_sanitizer: Optional[ContextSanitizerPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> AgentState:
    """Single-responsibility node executing the read-only Support Ticket Query Tool (`ticket_tool`).

    Args:
        state: Current AgentState containing `ticket_tool_input`.
        ticket_tool: SupportTicketToolPort adapter.
        context_sanitizer: Optional ContextSanitizerPort enforcing two-tier anti-injection on tool payloads.
        observability: Optional GuardrailObservabilityPort for recording security events.

    Returns:
        Updated AgentState with sanitized `ticket_tool_output`, `"ticket_tool"` appended to `sources_consulted`,
        and `fallback_triggered` updated if status != "success".
    """
    start_ns = time.perf_counter()

    tool_input = state.get("ticket_tool_input")
    if tool_input is None:
        tool_input = _extract_ticket_tool_input(state.get("query") or "")

    try:
        output: TicketToolOutput = ticket_tool.query_tickets(tool_input)
    except Exception:
        elapsed_err = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
        output = TicketToolOutput(
            status="error",
            records=[],
            total_matched=0,
            latency_ms=elapsed_err,
            error_message="Support ticket service encountered an unexpected error.",
            queried_criteria=tool_input.to_dict(),
        )

    sanitizer = context_sanitizer or TwoTierContextSanitizer()
    guardrail_events: List[GuardrailAuditEvent] = list(
        state.get("guardrail_events") or []
    )
    session_ctx = state.get("session_context")
    session_id = (
        session_ctx.session_id
        if session_ctx and session_ctx.session_id
        else (state.get("thread_id") or state.get("trace_id") or "default")
    )
    if output.records:
        raw_preview = " ".join(f"{r.title} {r.description}" for r in output.records)
        output, interventions = sanitizer.sanitize_ticket_output(output)
        if observability is not None:
            for item in interventions:
                ev = observability.record_evaluation(
                    result=item,
                    session_id=session_id,
                    raw_preview=raw_preview,
                    trace_id=state.get("trace_id"),
                )
                if ev is not None:
                    guardrail_events.append(ev)

    sources_consulted = list(state.get("sources_consulted") or [])
    if "ticket_tool" not in sources_consulted:
        sources_consulted.append("ticket_tool")

    node_history = list(state.get("node_history") or [])
    node_history.append("ticket_tool")

    fallback_triggered = bool(state.get("fallback_triggered", False)) or (
        output.status != "success"
    )

    elapsed_ms = max(
        0.01,
        round((time.perf_counter() - start_ns) * 1000.0, 3),
        round(output.latency_ms, 3),
    )
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["ticket_tool"] = elapsed_ms

    node_outputs: Dict[str, Dict[str, Any]] = dict(state.get("node_outputs") or {})
    node_outputs["ticket_tool"] = {
        "status": output.status,
        "total_matched": output.total_matched,
        "returned_count": len(output.records),
        "latency_ms": elapsed_ms,
        "error_message": output.error_message,
        "queried_criteria": output.queried_criteria,
        "records": [r.to_dict() for r in output.records],
    }

    return {
        "ticket_tool_input": tool_input,
        "ticket_tool_output": output,
        "sources_consulted": sources_consulted,
        "fallback_triggered": fallback_triggered,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "node_outputs": node_outputs,
        "guardrail_events": guardrail_events,
    }


def inventory_tool_node(
    state: AgentState,
    inventory_tool: InventoryStockToolPort,
    context_sanitizer: Optional[ContextSanitizerPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> AgentState:
    """Single-responsibility node executing the read-only Inventory Stock Query Tool (`inventory_tool`).

    Args:
        state: Current AgentState containing `inventory_tool_input`.
        inventory_tool: InventoryStockToolPort adapter.
        context_sanitizer: Optional ContextSanitizerPort enforcing two-tier anti-injection on tool payloads.
        observability: Optional GuardrailObservabilityPort for recording security events.

    Returns:
        Updated AgentState with sanitized `inventory_tool_output`, `"inventory_tool"` appended to `sources_consulted`,
        and `fallback_triggered` updated if status != "success".
    """
    start_ns = time.perf_counter()

    tool_input = state.get("inventory_tool_input")
    if tool_input is None:
        tool_input = _extract_inventory_tool_input(state.get("query") or "")

    try:
        output: InventoryToolOutput = inventory_tool.query_inventory(tool_input)
    except Exception:
        elapsed_err = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
        output = InventoryToolOutput(
            status="error",
            records=[],
            total_matched=0,
            latency_ms=elapsed_err,
            error_message="Inventory stock service encountered an unexpected error.",
            queried_criteria=tool_input.to_dict(),
        )

    sanitizer = context_sanitizer or TwoTierContextSanitizer()
    guardrail_events: List[GuardrailAuditEvent] = list(
        state.get("guardrail_events") or []
    )
    session_ctx = state.get("session_context")
    session_id = (
        session_ctx.session_id
        if session_ctx and session_ctx.session_id
        else (state.get("thread_id") or state.get("trace_id") or "default")
    )
    if output.records:
        raw_preview = " ".join(f"{r.name} {r.description}" for r in output.records)
        output, interventions = sanitizer.sanitize_inventory_output(output)
        if observability is not None:
            for item in interventions:
                ev = observability.record_evaluation(
                    result=item,
                    session_id=session_id,
                    raw_preview=raw_preview,
                    trace_id=state.get("trace_id"),
                )
                if ev is not None:
                    guardrail_events.append(ev)

    sources_consulted = list(state.get("sources_consulted") or [])
    if "inventory_tool" not in sources_consulted:
        sources_consulted.append("inventory_tool")

    node_history = list(state.get("node_history") or [])
    node_history.append("inventory_tool")

    fallback_triggered = bool(state.get("fallback_triggered", False)) or (
        output.status != "success"
    )

    elapsed_ms = max(
        0.01,
        round((time.perf_counter() - start_ns) * 1000.0, 3),
        round(output.latency_ms, 3),
    )
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["inventory_tool"] = elapsed_ms

    node_outputs: Dict[str, Dict[str, Any]] = dict(state.get("node_outputs") or {})
    node_outputs["inventory_tool"] = {
        "status": output.status,
        "total_matched": output.total_matched,
        "returned_count": len(output.records),
        "latency_ms": elapsed_ms,
        "error_message": output.error_message,
        "queried_criteria": output.queried_criteria,
        "records": [r.to_dict() for r in output.records],
    }

    return {
        "inventory_tool_input": tool_input,
        "inventory_tool_output": output,
        "sources_consulted": sources_consulted,
        "fallback_triggered": fallback_triggered,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "node_outputs": node_outputs,
        "guardrail_events": guardrail_events,
    }


def retrieval_node(
    state: AgentState,
    vector_store: VectorStorePort,
    embedding_service: EmbeddingServicePort,
    default_min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
    context_sanitizer: Optional[ContextSanitizerPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> AgentState:
    """Single-responsibility retrieval node reusing `retrieve()` from `data.pipelines.rag_pipeline`.

    Embeds the sanitized query, performs cosine similarity search, filters candidates
    strictly against the calibrated `min_score` threshold (0.62 default), applies two-tier
    prompt-injection sanitization on retrieved chunks (FR-009), and records `"rag"` in `sources_consulted`.
    """
    start_ns = time.perf_counter()

    query = (state.get("query") or "").strip()
    top_k = int(state.get("top_k", 3))
    min_score = float(state.get("min_score", default_min_score))

    try:
        qualified_contexts: List[RetrievedContext] = rag_retrieve(
            question=query,
            vector_store=vector_store,
            embedding_service=embedding_service,
            top_k=top_k,
            min_score=min_score,
        )
    except KnowledgeBaseUnavailableException:
        raise
    except Exception as exc:
        raise WorkflowExecutionError(
            message="Vector retrieval failed during support agent execution.",
            trace_id=state.get("trace_id"),
        ) from exc

    sanitizer = context_sanitizer or TwoTierContextSanitizer()
    guardrail_events: List[GuardrailAuditEvent] = list(
        state.get("guardrail_events") or []
    )
    session_ctx = state.get("session_context")
    session_id = (
        session_ctx.session_id
        if session_ctx and session_ctx.session_id
        else (state.get("thread_id") or state.get("trace_id") or "default")
    )
    if qualified_contexts:
        raw_preview = " ".join(c.chunk.text for c in qualified_contexts)
        qualified_contexts, interventions = sanitizer.sanitize_rag_contexts(
            qualified_contexts
        )
        if observability is not None:
            for item in interventions:
                ev = observability.record_evaluation(
                    result=item,
                    session_id=session_id,
                    raw_preview=raw_preview,
                    trace_id=state.get("trace_id"),
                )
                if ev is not None:
                    guardrail_events.append(ev)

    sources_consulted = list(state.get("sources_consulted") or [])
    if "rag" not in sources_consulted:
        sources_consulted.append("rag")

    node_history = list(state.get("node_history") or [])
    node_history.append("retrieval")

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["retrieval"] = elapsed_ms

    node_outputs: Dict[str, Dict[str, Any]] = dict(state.get("node_outputs") or {})
    node_outputs["retrieval"] = {
        "context_count": len(qualified_contexts),
        "retrieved_chunks": [
            {
                "source_document": ctx.chunk.source_document,
                "section": ctx.chunk.section,
                "similarity_score": round(ctx.similarity_score, 4),
            }
            for ctx in qualified_contexts
        ],
    }

    return {
        "contexts": qualified_contexts,
        "sources_consulted": sources_consulted,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "node_outputs": node_outputs,
        "guardrail_events": guardrail_events,
    }


def _build_ticket_fallback_notice(
    ticket_input: Optional[TicketToolInput],
    ticket_output: TicketToolOutput,
) -> str:
    """Build an honest, non-hallucinating inability-to-confirm notice for a failed/missing ticket lookup."""
    ticket_id = (
        ticket_input.ticket_id
        if ticket_input and ticket_input.ticket_id
        else ticket_output.queried_criteria.get("ticket_id")
    )
    if ticket_output.status == "not_found":
        if ticket_id:
            return (
                f"I couldn't confirm the status of ticket '{ticket_id}' right now "
                f"because no matching incident record was found in the Incident Manager."
            )
        return (
            "I couldn't confirm matching support tickets right now because no "
            "incident records matched the requested criteria in the Incident Manager."
        )
    if ticket_output.status == "timeout":
        if ticket_id:
            return (
                f"I couldn't confirm the status of ticket '{ticket_id}' right now "
                f"because the Incident Manager request timed out."
            )
        return (
            "I couldn't confirm the status of that ticket right now because "
            "the Incident Manager request timed out."
        )
    if ticket_id:
        return (
            f"I couldn't confirm the status of ticket '{ticket_id}' right now "
            f"because the Incident Manager service is temporarily unavailable."
        )
    return (
        "I couldn't confirm the status of that ticket right now because "
        "the Incident Manager service is temporarily unavailable."
    )


def _build_inventory_fallback_notice(
    inventory_input: Optional[InventoryToolInput],
    inventory_output: InventoryToolOutput,
) -> str:
    """Build an honest, non-hallucinating inability-to-confirm notice for a failed/missing inventory lookup."""
    sku = (
        inventory_input.sku
        if inventory_input and inventory_input.sku
        else inventory_output.queried_criteria.get("sku")
    )
    product_id = (
        inventory_input.product_id
        if inventory_input and inventory_input.product_id is not None
        else inventory_output.queried_criteria.get("product_id")
    )
    if sku:
        target = f"SKU '{sku}'"
    elif product_id is not None:
        target = f"product ID '{product_id}'"
    else:
        target = "that product"

    if inventory_output.status == "not_found":
        return (
            f"I couldn't confirm the stock availability for {target} right now "
            f"because no matching product record was found in the Inventory Manager."
        )
    if inventory_output.status == "timeout":
        return (
            f"I couldn't confirm the stock availability for {target} right now "
            f"because the Inventory Manager request timed out."
        )
    return (
        f"I couldn't confirm the stock availability for {target} right now "
        f"because the Inventory Manager service is temporarily unavailable."
    )


def tool_fallback_node(state: AgentState) -> AgentState:
    """Single-responsibility error recovery node (`tool_fallback`) for operational tools (FR-023).

    Constructs honest inability-to-confirm notices (`fallback_messages`) when any operational
    tool times out, raises a service error, or returns `not_found`. When no partial context
    exists (no qualifying RAG chunks and no other succeeded tool), populates the final `answer`
    directly and terminates cleanly without hallucination.

    Args:
        state: Current AgentState.

    Returns:
        Updated AgentState with `fallback_triggered=True`, `fallback_messages`, and `answer` (if terminal).
    """
    start_ns = time.perf_counter()

    fallback_messages: List[str] = list(state.get("fallback_messages") or [])
    ticket_out = state.get("ticket_tool_output")
    ticket_in = state.get("ticket_tool_input")
    if ticket_out is not None and ticket_out.status != "success":
        msg = _build_ticket_fallback_notice(ticket_in, ticket_out)
        if msg not in fallback_messages:
            fallback_messages.append(msg)

    inv_out = state.get("inventory_tool_output")
    inv_in = state.get("inventory_tool_input")
    if inv_out is not None and inv_out.status != "success":
        msg = _build_inventory_fallback_notice(inv_in, inv_out)
        if msg not in fallback_messages:
            fallback_messages.append(msg)

    if not fallback_messages:
        fallback_messages.append(
            "I couldn't confirm the requested live operational record right now."
        )

    min_score = float(state.get("min_score", DEFAULT_SIMILARITY_THRESHOLD))
    contexts: List[RetrievedContext] = list(state.get("contexts") or [])
    has_qualified_rag = any(ctx.similarity_score >= min_score for ctx in contexts)
    has_succeeded_ticket = ticket_out is not None and ticket_out.status == "success"
    has_succeeded_inv = inv_out is not None and inv_out.status == "success"
    has_partial_success = has_qualified_rag or has_succeeded_ticket or has_succeeded_inv

    combined_fallback_text = " ".join(fallback_messages)
    answer = state.get("answer") or ""
    if not has_partial_success:
        answer = combined_fallback_text

    node_history = list(state.get("node_history") or [])
    node_history.append("tool_fallback")

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["tool_fallback"] = elapsed_ms

    node_outputs: Dict[str, Dict[str, Any]] = dict(state.get("node_outputs") or {})
    node_outputs["tool_fallback"] = {
        "fallback_triggered": True,
        "fallback_messages": list(fallback_messages),
        "has_partial_success": has_partial_success,
        "answer": answer if not has_partial_success else None,
    }

    return {
        "fallback_triggered": True,
        "fallback_messages": fallback_messages,
        "answer": answer,
        "is_refusal": False,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "node_outputs": node_outputs,
    }


def _format_ticket_records_summary(output: TicketToolOutput) -> str:
    """Format live TicketRecordDTO items into a grounded natural-language summary."""
    records: List[TicketRecordDTO] = output.records
    if len(records) == 1:
        r = records[0]
        return (
            f"Support ticket {r.id} ('{r.title}') currently has status '{r.status}', "
            f"category '{r.category}', origin '{r.origin}', and branch '{r.branch}' "
            f"(created_at: {r.created_at}, updated_at: {r.updated_at}). "
            f"Description: {r.description}"
        )

    header = (
        f"Found {output.total_matched} matching support incident(s) "
        f"(showing {len(records)} most recent):"
    )
    lines = [header]
    for r in records:
        lines.append(
            f"- {r.id} ('{r.title}'): status='{r.status}', category='{r.category}', "
            f"origin='{r.origin}', branch='{r.branch}', updated_at='{r.updated_at}'."
        )
    return "\n".join(lines)


def _format_inventory_records_summary(output: InventoryToolOutput) -> str:
    """Format live InventoryRecordDTO items into a grounded natural-language summary."""
    records: List[InventoryRecordDTO] = output.records
    if len(records) == 1:
        r = records[0]
        threshold_state = (
            "low stock (at or below minimum threshold)"
            if r.is_low_stock
            else "in stock (above minimum threshold)"
        )
        return (
            f"SKU {r.sku} ('{r.name}', product ID {r.id}, warehouse '{r.warehouse_id}') "
            f"currently has {r.stock} units in stock (minimum threshold: {r.min_threshold} units; "
            f"status: {threshold_state})."
        )

    header = (
        f"Found {output.total_matched} matching inventory product(s) "
        f"(showing {len(records)}):"
    )
    lines = [header]
    for r in records:
        threshold_flag = "LOW STOCK" if r.is_low_stock else "OK"
        lines.append(
            f"- SKU {r.sku} ('{r.name}', ID {r.id}): {r.stock} units in stock "
            f"(min_threshold: {r.min_threshold}, status: {threshold_flag})."
        )
    return "\n".join(lines)


def _parse_structured_llm_output(
    raw_output: Any,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Parse single-call LLM output into `(answer_text, optional_memory_candidate_dict)` (AC-3.2).

    Supports:
    - Plain text string responses -> `(raw_text, None)`
    - JSON string responses containing `{"answer": "...", "memory_proposal": {...}}` or `"memory_candidate"`
    - Dict responses containing `{"answer": "...", "memory_proposal": {...}}` or `"memory_candidate"`
    """
    if isinstance(raw_output, dict):
        answer_text = str(raw_output.get("answer") or "").strip()
        candidate = raw_output.get("memory_proposal") or raw_output.get("memory_candidate")
        return (
            answer_text,
            dict(candidate) if isinstance(candidate, dict) else None,
        )

    if not isinstance(raw_output, str):
        return (str(raw_output or ""), None)

    stripped = raw_output.strip()
    # Unwrap optional markdown json fence
    if stripped.startswith("```"):
        fence_match = re.match(
            r"^```(?:json)?\s*(\{.*\})\s*```$",
            stripped,
            re.DOTALL | re.IGNORECASE,
        )
        if fence_match:
            stripped = fence_match.group(1).strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and "answer" in parsed:
                answer_text = str(parsed.get("answer") or "").strip()
                candidate = parsed.get("memory_proposal") or parsed.get("memory_candidate")
                return (
                    answer_text,
                    dict(candidate) if isinstance(candidate, dict) else None,
                )
        except Exception:
            pass

    return (raw_output, None)


def generation_node(
    state: AgentState,
    llm_generator: LLMGenerationPort,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
    memory_service: Optional[Any] = None,
    output_guard: Optional[OutputGuardrailPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> AgentState:
    """Single-responsibility generation node synthesizing grounded answers from pre-retrieved contexts, live operational tool outputs, and recalled operational memories.

    Enforces post-generation output guardrails (`OutputGuardrailPort`, FR-010) and suppresses new
    memory proposals on blocked or casual-redirected turns (FR-001).
    """
    start_ns = time.perf_counter()
    validator = guardrail_validator or BusinessGuardrailValidator()
    resolved_output_guard = output_guard or OutputGuardrailValidator()

    query = state.get("query") or ""
    language = state.get("language") or "en"
    thread_id = state.get("thread_id") or state.get("trace_id")
    session_ctx: Optional[AuthenticatedSessionContext] = state.get("session_context")
    session_id = (
        session_ctx.session_id
        if session_ctx and session_ctx.session_id
        else (thread_id or "default")
    )
    contexts: List[RetrievedContext] = list(state.get("contexts") or [])
    ticket_out = state.get("ticket_tool_output")
    inv_out = state.get("inventory_tool_output")
    fallback_messages: List[str] = list(state.get("fallback_messages") or [])
    recalled_memories: List[str] = list(state.get("recalled_memories") or [])
    proposal_resolution: Optional[Dict[str, Any]] = state.get("proposal_resolution")
    casual_redirect_required = bool(state.get("casual_redirect_required", False))
    guardrail_action = state.get("guardrail_action")
    guardrail_message = state.get("guardrail_message")
    guardrail_events: List[GuardrailAuditEvent] = list(
        state.get("guardrail_events") or []
    )

    segments: List[str] = []
    citations: List[SourceCitation] = []
    memory_proposal: Optional[MemoryProposal] = state.get("memory_proposal")
    structured_llm_candidate: Optional[Dict[str, Any]] = None

    # 1. Include proposal disposition acknowledgment if a pending proposal was resolved in this turn
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
        if proposal_resolution.get("status") == "edited":
            memory_proposal = proposal_resolution.get("updated_proposal")
        if not has_residual:
            pure_proposal_turn = True

    if casual_redirect_required and guardrail_message:
        segments.append(str(guardrail_message))
    else:
        # 2. Include recalled cross-session operational memories (T028, US3)
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
            if ticket_out is not None and ticket_out.status == "success" and ticket_out.records:
                segments.append(_format_ticket_records_summary(ticket_out))

            if inv_out is not None and inv_out.status == "success" and inv_out.records:
                segments.append(_format_inventory_records_summary(inv_out))

            if fallback_messages:
                segments.append(" ".join(fallback_messages))

            if contexts:
                try:
                    enforced_rag_answer, rag_citations = rag_generate_answer(
                        question=query,
                        context=contexts,
                        llm_generator=llm_generator,
                        guardrail_validator=validator,
                        language=language,
                    )
                    parsed_answer, parsed_candidate = _parse_structured_llm_output(
                        enforced_rag_answer
                    )
                    if parsed_candidate is not None:
                        structured_llm_candidate = parsed_candidate
                        enforced_rag_answer = validator.enforce(
                            query=query,
                            answer=parsed_answer,
                            contexts=contexts,
                        )
                    segments.append(enforced_rag_answer)
                    citations = list(rag_citations)
                except Exception as exc:
                    raise WorkflowExecutionError(
                        message="Answer generation failed during support agent execution.",
                        trace_id=state.get("trace_id"),
                    ) from exc
            elif not segments:
                # Defensive fallback if generation_node is invoked directly with empty state
                try:
                    enforced_rag_answer, rag_citations = rag_generate_answer(
                        question=query,
                        context=contexts,
                        llm_generator=llm_generator,
                        guardrail_validator=validator,
                        language=language,
                    )
                    parsed_answer, parsed_candidate = _parse_structured_llm_output(
                        enforced_rag_answer
                    )
                    if parsed_candidate is not None:
                        structured_llm_candidate = parsed_candidate
                        enforced_rag_answer = validator.enforce(
                            query=query,
                            answer=parsed_answer,
                            contexts=contexts,
                        )
                    segments.append(enforced_rag_answer)
                    citations = list(rag_citations)
                except Exception as exc:
                    raise WorkflowExecutionError(
                        message="Answer generation failed during support agent execution.",
                        trace_id=state.get("trace_id"),
                    ) from exc

    final_answer = "\n\n".join(seg for seg in segments if seg).strip()

    # 3. Layer 4: Post-Generation Output Guardrail Validation (FR-010)
    output_eval = resolved_output_guard.validate_output(
        query=query,
        candidate_answer=final_answer,
        session_context=session_ctx,
        casual_redirect_required=casual_redirect_required,
        language=language,
    )
    if observability is not None:
        ev = observability.record_evaluation(
            result=output_eval,
            session_id=session_id,
            raw_preview=final_answer,
            trace_id=state.get("trace_id"),
        )
        if ev is not None:
            guardrail_events.append(ev)

    is_output_blocked = output_eval.action == "block"
    if output_eval.sanitized_text is not None:
        final_answer = output_eval.sanitized_text

    # 4. Single-call memory candidate evaluation — suppressed on any blocked or casual-redirected turn (FR-001)
    should_suppress_memory_proposal = bool(
        is_output_blocked
        or casual_redirect_required
        or guardrail_action in ("block", "redirect")
    )
    if should_suppress_memory_proposal:
        memory_proposal = None
        if is_output_blocked and memory_service is not None and hasattr(memory_service, "discard_pending_proposal"):
            memory_service.discard_pending_proposal(
                thread_id=thread_id,
                reason=output_eval.reason_code or "output_guardrail_block",
            )
    elif memory_service is not None and proposal_resolution is None:
        candidate_proposal, final_answer = memory_service.evaluate_turn_for_proposal(
            user_message=query,
            base_answer=final_answer,
            thread_id=thread_id,
            language=language,
            llm_candidate=structured_llm_candidate,
        )
        if candidate_proposal is not None:
            memory_proposal = candidate_proposal

    node_history = list(state.get("node_history") or [])
    node_history.append("generation")

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["generation"] = elapsed_ms

    node_outputs: Dict[str, Dict[str, Any]] = dict(state.get("node_outputs") or {})
    node_outputs["generation"] = {
        "answer": final_answer,
        "is_refusal": is_output_blocked,
        "output_guard_action": output_eval.action,
        "output_guard_reason_code": output_eval.reason_code,
        "source_count": 0 if is_output_blocked else len(citations),
        "sources": (
            []
            if is_output_blocked
            else [
                {
                    "source_document": c.source_document,
                    "section": c.section,
                    "similarity_score": c.similarity_score,
                }
                for c in citations
            ]
        ),
        "memory_proposal": memory_proposal.to_dict() if memory_proposal else None,
        "recalled_memories": list(recalled_memories),
    }

    return {
        "answer": final_answer,
        "is_refusal": is_output_blocked,
        "sources": [] if is_output_blocked else citations,
        "memory_proposal": memory_proposal,
        "recalled_memories": recalled_memories,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "node_outputs": node_outputs,
        "guardrail_events": guardrail_events,
    }


def refusal_node(
    state: AgentState,
    output_guard: Optional[OutputGuardrailPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> AgentState:
    """Single-responsibility refusal node formatting standardized policy, guardrail, or read-only mutation refusals.

    Executed when input is blocked by `InputGuardrailPort` or `AuthorizationGuardrailPort`,
    when input is blank/short at intake, when a prompt attempts a disallowed write
    mutation on tickets/inventory, or when zero context chunks satisfy the calibrated
    0.62 similarity threshold after retrieval.
    """
    start_ns = time.perf_counter()

    query = (state.get("query") or "").strip()
    language = state.get("language") or "en"
    intake_out = (state.get("node_outputs") or {}).get("intake") or {}
    is_mutation = bool(
        intake_out.get("is_mutation_attempt") or detect_mutation_attempt(query)
    )
    guardrail_action = state.get("guardrail_action")
    guardrail_msg = state.get("guardrail_message")
    guardrail_events: List[GuardrailAuditEvent] = list(
        state.get("guardrail_events") or []
    )

    if guardrail_action == "block" and guardrail_msg:
        refusal_text = str(guardrail_msg)
    elif len(query) < MIN_QUERY_LENGTH:
        refusal_text = STANDARD_REFUSAL_MESSAGE
    elif is_mutation:
        refusal_text = READ_ONLY_MUTATION_REFUSAL_MESSAGE
    else:
        refusal_text = build_refusal_message(query)

    # Validate refusal text through OutputGuardrailPort to ensure zero sensitive leaks
    resolved_output_guard = output_guard or OutputGuardrailValidator()
    out_eval = resolved_output_guard.validate_output(
        query=query,
        candidate_answer=refusal_text,
        session_context=state.get("session_context"),
        casual_redirect_required=False,
        language=language,
    )
    if out_eval.sanitized_text:
        refusal_text = out_eval.sanitized_text
    if observability is not None and out_eval.action != "allow":
        session_ctx = state.get("session_context")
        session_id = (
            session_ctx.session_id
            if session_ctx and session_ctx.session_id
            else (state.get("thread_id") or state.get("trace_id") or "default")
        )
        ev = observability.record_evaluation(
            result=out_eval,
            session_id=session_id,
            raw_preview=refusal_text,
            trace_id=state.get("trace_id"),
        )
        if ev is not None:
            guardrail_events.append(ev)

    node_history = list(state.get("node_history") or [])
    node_history.append("refusal")

    elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
    step_latencies = dict(state.get("step_latencies") or {})
    step_latencies["refusal"] = elapsed_ms

    node_outputs: Dict[str, Dict[str, Any]] = dict(state.get("node_outputs") or {})
    node_outputs["refusal"] = {
        "answer": refusal_text,
        "is_refusal": True,
        "is_mutation_refusal": is_mutation,
        "guardrail_reason_code": state.get("guardrail_reason_code"),
        "source_count": 0,
    }

    return {
        "answer": refusal_text,
        "is_refusal": True,
        "sources": [],
        "memory_proposal": None,
        "node_history": node_history,
        "step_latencies": step_latencies,
        "node_outputs": node_outputs,
        "guardrail_events": guardrail_events,
    }


def route_after_intake(
    state: AgentState,
) -> Literal["ticket_tool", "inventory_tool", "retrieval", "generation", "refusal"]:
    """Conditional routing edge evaluated immediately after `intake_node`.

    Routes empty/short queries, guardrail blocks, and write-mutation attempts directly to `refusal`,
    routes casual small talk / general logistics trivia (`casual_redirect_required=True`) and pure
    proposal resolution turns directly to `generation`, and otherwise transitions to the first planned
    source in `selected_sources` following canonical order (`ticket_tool` -> `inventory_tool` -> `retrieval`).
    """
    query = (state.get("query") or "").strip()
    proposal_resolution = state.get("proposal_resolution")
    if (
        (len(query) < MIN_QUERY_LENGTH and proposal_resolution is None)
        or state.get("is_refusal") is True
        or state.get("guardrail_action") == "block"
        or state.get("error")
        or (
            proposal_resolution is None
            and detect_mutation_attempt(query)
        )
    ):
        return "refusal"

    if state.get("casual_redirect_required") is True:
        return "generation"

    selected = list(state.get("selected_sources") or [])
    if not selected:
        proposal_resolution = state.get("proposal_resolution")
        if (
            proposal_resolution is not None
            and not proposal_resolution.get("residual_query")
        ):
            return "generation"
        return "retrieval"

    if "ticket_tool" in selected:
        return "ticket_tool"
    if "inventory_tool" in selected:
        return "inventory_tool"
    return "retrieval"


def route_after_ticket_tool(
    state: AgentState,
) -> Literal["inventory_tool", "retrieval", "tool_fallback", "generation"]:
    """Conditional routing edge evaluated immediately after `ticket_tool_node`.

    Advances along the canonical plan (`ticket_tool` -> `inventory_tool` -> `retrieval`).
    When no further sources remain, routes to `tool_fallback` if the tool degraded/failed/not_found,
    or to `generation` if it succeeded.

    Args:
        state: AgentState emitted by `ticket_tool_node`.

    Returns:
        Target node identifier.
    """
    selected = list(state.get("selected_sources") or [])
    if "inventory_tool" in selected:
        return "inventory_tool"
    if "rag" in selected:
        return "retrieval"

    ticket_out = state.get("ticket_tool_output")
    if (
        state.get("fallback_triggered") is True
        or ticket_out is None
        or ticket_out.status != "success"
    ):
        return "tool_fallback"
    return "generation"


def route_after_inventory_tool(
    state: AgentState,
) -> Literal["retrieval", "tool_fallback", "generation"]:
    """Conditional routing edge evaluated immediately after `inventory_tool_node`.

    Advances to `retrieval` if `"rag"` is in `selected_sources`; otherwise routes to
    `tool_fallback` if any consulted operational tool failed/timed out/not_found, or
    to `generation` when all consulted tools succeeded.

    Args:
        state: AgentState emitted by `inventory_tool_node`.

    Returns:
        Target node identifier.
    """
    selected = list(state.get("selected_sources") or [])
    if "rag" in selected:
        return "retrieval"

    inv_out = state.get("inventory_tool_output")
    if (
        state.get("fallback_triggered") is True
        or inv_out is None
        or inv_out.status != "success"
    ):
        return "tool_fallback"
    return "generation"


def route_after_retrieval(
    state: AgentState,
) -> Literal["tool_fallback", "generation", "refusal"]:
    """Conditional routing edge evaluated immediately after `retrieval_node`.

    - If a prior operational tool triggered fallback (`fallback_triggered=True`), routes
      to `tool_fallback` so the honest inability-to-confirm notice is recorded before
      partial hybrid generation.
    - Else if >= 1 chunk meets `min_score` (0.62) OR a prior operational tool succeeded,
      routes to `generation`.
    - Else routes to `refusal`.

    Args:
        state: AgentState emitted by `retrieval_node`.

    Returns:
        Target node identifier: `'tool_fallback'`, `'generation'`, or `'refusal'`.
    """
    if state.get("error"):
        return "refusal"
    if state.get("fallback_triggered") is True:
        return "tool_fallback"

    min_score = float(state.get("min_score", DEFAULT_SIMILARITY_THRESHOLD))
    contexts: List[RetrievedContext] = list(state.get("contexts") or [])
    qualified = [ctx for ctx in contexts if ctx.similarity_score >= min_score]

    ticket_out = state.get("ticket_tool_output")
    inv_out = state.get("inventory_tool_output")
    has_succeeded_tool = (
        ticket_out is not None and ticket_out.status == "success"
    ) or (inv_out is not None and inv_out.status == "success")
    has_memory_context = bool(
        state.get("proposal_resolution") or state.get("recalled_memories")
    )

    if not qualified and not has_succeeded_tool and not has_memory_context:
        return "refusal"
    return "generation"


def route_after_tool_fallback(
    state: AgentState,
) -> str:
    """Conditional routing edge evaluated immediately after `tool_fallback_node`.

    If partial context exists (qualifying RAG chunks or another succeeded tool in a
    hybrid query), transitions to `generation` for graceful partial answer synthesis;
    otherwise terminates at `END` with the honest inability-to-confirm response.

    Args:
        state: AgentState emitted by `tool_fallback_node`.

    Returns:
        `'generation'` or `END`.
    """
    min_score = float(state.get("min_score", DEFAULT_SIMILARITY_THRESHOLD))
    contexts: List[RetrievedContext] = list(state.get("contexts") or [])
    qualified = [ctx for ctx in contexts if ctx.similarity_score >= min_score]

    ticket_out = state.get("ticket_tool_output")
    inv_out = state.get("inventory_tool_output")
    has_succeeded_tool = (
        ticket_out is not None and ticket_out.status == "success"
    ) or (inv_out is not None and inv_out.status == "success")

    if qualified or has_succeeded_tool:
        return "generation"
    return END


def create_ticket_tool_node(
    ticket_tool: SupportTicketToolPort,
    context_sanitizer: Optional[ContextSanitizerPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument ticket_tool node function for LangGraph registration."""

    def _bound_ticket_tool(state: AgentState) -> AgentState:
        return ticket_tool_node(
            state=state,
            ticket_tool=ticket_tool,
            context_sanitizer=context_sanitizer,
            observability=observability,
        )

    return _bound_ticket_tool


def create_inventory_tool_node(
    inventory_tool: InventoryStockToolPort,
    context_sanitizer: Optional[ContextSanitizerPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument inventory_tool node function for LangGraph registration."""

    def _bound_inventory_tool(state: AgentState) -> AgentState:
        return inventory_tool_node(
            state=state,
            inventory_tool=inventory_tool,
            context_sanitizer=context_sanitizer,
            observability=observability,
        )

    return _bound_inventory_tool


def create_retrieval_node(
    vector_store: VectorStorePort,
    embedding_service: EmbeddingServicePort,
    default_min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
    context_sanitizer: Optional[ContextSanitizerPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument retrieval node function for LangGraph registration."""

    def _bound_retrieval(state: AgentState) -> AgentState:
        return retrieval_node(
            state=state,
            vector_store=vector_store,
            embedding_service=embedding_service,
            default_min_score=default_min_score,
            context_sanitizer=context_sanitizer,
            observability=observability,
        )

    return _bound_retrieval


def create_intake_node(
    memory_service: Optional[Any] = None,
    input_guard: Optional[InputGuardrailPort] = None,
    authorization_guard: Optional[AuthorizationGuardrailPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument intake node function for LangGraph registration."""

    def _bound_intake(state: AgentState) -> AgentState:
        return intake_node(
            state=state,
            memory_service=memory_service,
            input_guard=input_guard,
            authorization_guard=authorization_guard,
            observability=observability,
        )

    return _bound_intake


def create_generation_node(
    llm_generator: LLMGenerationPort,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
    memory_service: Optional[Any] = None,
    output_guard: Optional[OutputGuardrailPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument generation node function for LangGraph registration."""

    def _bound_generation(state: AgentState) -> AgentState:
        return generation_node(
            state=state,
            llm_generator=llm_generator,
            guardrail_validator=guardrail_validator,
            memory_service=memory_service,
            output_guard=output_guard,
            observability=observability,
        )

    return _bound_generation


def create_refusal_node(
    output_guard: Optional[OutputGuardrailPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> Callable[[AgentState], AgentState]:
    """Create a bound single-argument refusal node function for LangGraph registration."""

    def _bound_refusal(state: AgentState) -> AgentState:
        return refusal_node(
            state=state,
            output_guard=output_guard,
            observability=observability,
        )

    return _bound_refusal


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
    ticket_tool: Optional[SupportTicketToolPort] = None,
    inventory_tool: Optional[InventoryStockToolPort] = None,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    default_min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
    memory_service: Optional[Any] = None,
    input_guard: Optional[InputGuardrailPort] = None,
    authorization_guard: Optional[AuthorizationGuardrailPort] = None,
    context_sanitizer: Optional[ContextSanitizerPort] = None,
    output_guard: Optional[OutputGuardrailPort] = None,
    observability: Optional[GuardrailObservabilityPort] = None,
) -> CompiledStateGraph:
    """Assemble, validate, and compile the 7-node TrackFlow Support Agent LangGraph state machine."""
    resolved_checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    if ticket_tool is None:
        from infrastructure.adapters.mcp_ticket_tool_adapter import (
            McpTicketToolAdapter,
        )

        resolved_ticket_tool: SupportTicketToolPort = McpTicketToolAdapter()
    else:
        resolved_ticket_tool = ticket_tool

    if inventory_tool is None:
        from infrastructure.adapters.inventory_stock_tool_adapter import (
            InventoryStockQueryToolAdapter,
        )

        resolved_inventory_tool: InventoryStockToolPort = InventoryStockQueryToolAdapter()
    else:
        resolved_inventory_tool = inventory_tool

    workflow = StateGraph(AgentState)

    workflow.add_node(
        "intake",
        create_intake_node(
            memory_service=memory_service,
            input_guard=input_guard,
            authorization_guard=authorization_guard,
            observability=observability,
        ),
    )
    workflow.add_node(
        "ticket_tool",
        create_ticket_tool_node(
            ticket_tool=resolved_ticket_tool,
            context_sanitizer=context_sanitizer,
            observability=observability,
        ),
    )
    workflow.add_node(
        "inventory_tool",
        create_inventory_tool_node(
            inventory_tool=resolved_inventory_tool,
            context_sanitizer=context_sanitizer,
            observability=observability,
        ),
    )
    workflow.add_node(
        "retrieval",
        create_retrieval_node(
            vector_store=vector_store,
            embedding_service=embedding_service,
            default_min_score=default_min_score,
            context_sanitizer=context_sanitizer,
            observability=observability,
        ),
    )
    workflow.add_node("tool_fallback", tool_fallback_node)
    workflow.add_node(
        "generation",
        create_generation_node(
            llm_generator=llm_generator,
            guardrail_validator=guardrail_validator,
            memory_service=memory_service,
            output_guard=output_guard,
            observability=observability,
        ),
    )
    workflow.add_node(
        "refusal",
        create_refusal_node(
            output_guard=output_guard,
            observability=observability,
        ),
    )

    workflow.add_edge(START, "intake")
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "ticket_tool": "ticket_tool",
            "inventory_tool": "inventory_tool",
            "retrieval": "retrieval",
            "generation": "generation",
            "refusal": "refusal",
        },
    )
    workflow.add_conditional_edges(
        "ticket_tool",
        route_after_ticket_tool,
        {
            "inventory_tool": "inventory_tool",
            "retrieval": "retrieval",
            "tool_fallback": "tool_fallback",
            "generation": "generation",
        },
    )
    workflow.add_conditional_edges(
        "inventory_tool",
        route_after_inventory_tool,
        {
            "retrieval": "retrieval",
            "tool_fallback": "tool_fallback",
            "generation": "generation",
        },
    )
    workflow.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "tool_fallback": "tool_fallback",
            "generation": "generation",
            "refusal": "refusal",
        },
    )
    workflow.add_conditional_edges(
        "tool_fallback",
        route_after_tool_fallback,
        {
            "generation": "generation",
            END: END,
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
    "CANONICAL_SOURCE_ORDER",
    "MAX_QUERY_LENGTH",
    "MIN_QUERY_LENGTH",
    "READ_ONLY_MUTATION_REFUSAL_MESSAGE",
    "REQUIRED_WORKFLOW_NODES",
    "build_support_agent_graph",
    "classify_and_plan_query",
    "compile_and_validate_graph",
    "create_generation_node",
    "create_inventory_tool_node",
    "create_retrieval_node",
    "create_ticket_tool_node",
    "detect_mutation_attempt",
    "generation_node",
    "intake_node",
    "inventory_tool_node",
    "refusal_node",
    "retrieval_node",
    "route_after_intake",
    "route_after_inventory_tool",
    "route_after_retrieval",
    "route_after_ticket_tool",
    "route_after_tool_fallback",
    "sanitize_agent_query",
    "ticket_tool_node",
    "tool_fallback_node",
]
