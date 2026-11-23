"""Abstract port interfaces for the TrackFlow Support Agent domain.

Adheres strictly to Hexagonal Architecture and Monorepo Constitution Principle I & II,
decoupling presentation controllers and LangGraph orchestration from operational
tool adapters (`SupportTicketToolPort`, `InventoryStockToolPort`) and trace storage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from domain.agent.entities import (
    AgentCheckpoint,
    AgentQueryRequest,
    AgentQueryResult,
    AgentTrace,
    AuthenticatedSessionContext,
    ConsolidatedCarrierProfile,
    GuardrailAuditEvent,
    GuardrailEvaluationResult,
    GuardrailSummaryReport,
    InventoryToolInput,
    InventoryToolOutput,
    MemoryAuditLogEntry,
    MemoryCategory,
    MemoryGuardrailVerdict,
    PersistentMemoryRecord,
    RetrievedContext,
    TicketToolInput,
    TicketToolOutput,
    UserIntentClassification,
)


class SupportTicketToolPort(ABC):
    """Strictly read-only port interface for querying live incident tickets (FR-016, FR-019, FR-020)."""

    @abstractmethod
    def query_tickets(self, tool_input: TicketToolInput) -> TicketToolOutput:
        """Query live support incident records matching `tool_input` within a bounded timeout.

        Must be strictly read-only, return at most 20 most-recent records plus `total_matched`,
        and enforce the configured numerical timeout (default 4.0 seconds).

        Args:
            tool_input: Typed TicketToolInput specifying ticket_id or filter criteria.

        Returns:
            TicketToolOutput with status ('success', 'not_found', 'timeout', 'error'),
            up to 20 TicketRecordDTO records, total_matched count, and latency_ms.
        """


class InventoryStockToolPort(ABC):
    """Strictly read-only port interface for querying live warehouse product stock (FR-018, FR-019, FR-020)."""

    @abstractmethod
    def query_inventory(self, tool_input: InventoryToolInput) -> InventoryToolOutput:
        """Query live warehouse product stock projections matching `tool_input` within a bounded timeout.

        Must be strictly read-only, return at most 20 product records plus `total_matched`,
        and enforce the configured numerical timeout (default 4.0 seconds).

        Args:
            tool_input: Typed InventoryToolInput specifying product_id, sku, or search_query.

        Returns:
            InventoryToolOutput with status ('success', 'not_found', 'timeout', 'error'),
            up to 20 InventoryRecordDTO records, total_matched count, and latency_ms.
        """


class TraceRegistryPort(ABC):
    """Port interface for storing and querying structured agent execution traces."""

    @abstractmethod
    def record_trace(self, trace: AgentTrace) -> None:
        """Persist a completed AgentTrace in the registry.

        Args:
            trace: Immutable AgentTrace record for a workflow run.
        """

    @abstractmethod
    def get_trace(self, trace_id: str) -> Optional[AgentTrace]:
        """Retrieve a previously recorded AgentTrace by its identifier.

        Args:
            trace_id: Unique trace UUID string.

        Returns:
            Matching AgentTrace if found, otherwise None.
        """

    @abstractmethod
    def list_traces(self, limit: int = 50) -> List[AgentTrace]:
        """List recent execution traces ordered newest first.

        Args:
            limit: Maximum number of traces to return.

        Returns:
            List of AgentTrace records.
        """

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored traces from the registry."""


class SupportAgentServicePort(ABC):
    """Port interface for executing the compiled Support Agent workflow and inspecting state."""

    @abstractmethod
    def query(self, request: AgentQueryRequest) -> AgentQueryResult:
        """Execute a customer inquiry through the compiled LangGraph workflow.

        Args:
            request: Validated AgentQueryRequest domain object.

        Returns:
            AgentQueryResult with grounded answer, citations, trace_id, and node sequence.
        """

    @abstractmethod
    def get_trace(self, trace_id: str) -> AgentTrace:
        """Retrieve the structured execution trace for a given trace_id.

        Args:
            trace_id: Unique trace identifier.

        Returns:
            AgentTrace instance.

        Raises:
            TraceNotFoundError: When no trace exists for trace_id.
        """

    @abstractmethod
    def get_checkpoints(self, thread_id: str) -> List[AgentCheckpoint]:
        """Retrieve persisted state checkpoints for a thread/trace identifier.

        Args:
            thread_id: Thread or trace identifier used during execution.

        Returns:
            Chronological list of AgentCheckpoint snapshots.
        """

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """Return operational health and compilation status of the agent workflow.

        Returns:
            Dictionary with status, compiled, nodes, and checkpointer.
        """


class AgentMemoryRepositoryPort(ABC):
    """Port interface for storing, querying, and consolidating persistent agent memories (FR-006, FR-007)."""

    @abstractmethod
    def save_memory(self, record: PersistentMemoryRecord) -> PersistentMemoryRecord:
        """Persist or update an approved operational memory record.

        Args:
            record: PersistentMemoryRecord domain object to store.

        Returns:
            The stored PersistentMemoryRecord with assigned identifiers.
        """

    @abstractmethod
    def get_memory(self, memory_id: str) -> Optional[PersistentMemoryRecord]:
        """Retrieve a persistent memory record by its identifier.

        Args:
            memory_id: Unique UUID string.

        Returns:
            PersistentMemoryRecord if found and active, otherwise None.
        """

    @abstractmethod
    def search_memories(
        self,
        category: Optional[MemoryCategory] = None,
        target_entity: Optional[str] = None,
        country_code: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PersistentMemoryRecord]:
        """Search active memories by category, target entity, or country.

        Args:
            category: Optional functional category filter.
            target_entity: Optional entity filter (carrier, region, client ID).
            country_code: Optional ISO country code filter ("ES", "US").
            active_only: Whether to exclude expired or inactive items.

        Returns:
            List of matching PersistentMemoryRecord items.
        """

    @abstractmethod
    def get_consolidated_carrier_profile(
        self,
        carrier: str,
        country_code: str,
    ) -> Optional[ConsolidatedCarrierProfile]:
        """Retrieve the consolidated profile of active operational rules for a carrier and country.

        Args:
            carrier: Carrier name (e.g. "SEUR", "FedEx").
            country_code: ISO country code ("ES", "US").

        Returns:
            ConsolidatedCarrierProfile if records exist, otherwise None.
        """

    @abstractmethod
    def evict_expired(self, cutoff_time: datetime) -> int:
        """Evict or mark inactive any records whose expires_at is older than cutoff_time.

        Args:
            cutoff_time: UTC threshold timestamp.

        Returns:
            Count of evicted records.
        """


class MemoryAuditLogRepositoryPort(ABC):
    """Port interface for persisting and querying immutable memory lifecycle audit logs (FR-014)."""

    @abstractmethod
    def record_entry(self, entry: MemoryAuditLogEntry) -> None:
        """Append an immutable audit entry to the audit log store.

        Args:
            entry: MemoryAuditLogEntry domain object.
        """

    @abstractmethod
    def list_entries(
        self,
        proposal_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryAuditLogEntry]:
        """Query audit log entries ordered newest first.

        Args:
            proposal_id: Optional filter for a specific proposal lifecycle.
            event_type: Optional filter by event type ("proposed", "approved", "rejected", etc.).
            limit: Maximum records to return.

        Returns:
            List of MemoryAuditLogEntry records.
        """


class MemoryGuardrailPort(ABC):
    """Port interface for evaluating candidate memories against enterprise guardrails (FR-005, FR-017)."""

    @abstractmethod
    def validate_candidate(
        self,
        content: str,
        category: str,
        target_entity: str,
    ) -> MemoryGuardrailVerdict:
        """Validate candidate memory content against forbidden categories.

        Args:
            content: Candidate summary / text.
            category: Proposed category.
            target_entity: Carrier or entity identifier.

        Returns:
            MemoryGuardrailVerdict with allowed=True or allowed=False with violation details.
        """


class UserIntentClassifierPort(ABC):
    """Port interface for classifying user follow-up intent regarding active memory proposals (FR-011)."""

    @abstractmethod
    def classify(
        self,
        user_message: str,
        proposal_summary: str,
    ) -> UserIntentClassification:
        """Classify user response into approve, reject, edit, or unrelated_or_ambiguous.

        Args:
            user_message: The follow-up conversational text from the user.
            proposal_summary: The summary of the pending proposal being evaluated.

        Returns:
            UserIntentClassification containing intent, confidence, optional refined_rule,
            and optional residual_query.
        """


class InputGuardrailPort(ABC):
    """Pre-execution input guardrail port enforcing system authority and domain scope (FR-003..FR-006)."""

    @abstractmethod
    def evaluate_input(
        self,
        query: str,
        language: str = "en",
        conversation_history: Optional[Sequence[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GuardrailEvaluationResult:
        """Evaluate user query against security (jailbreak) and content (scope) guardrails with conversational continuity support."""


class AuthorizationGuardrailPort(ABC):
    """Guardrail port enforcing session-scoped order authorization and US/Spain policy separation (FR-007, FR-008)."""

    @abstractmethod
    def evaluate_authorization_and_policy(
        self,
        query: str,
        session_context: Optional[AuthenticatedSessionContext] = None,
        language: str = "en",
    ) -> GuardrailEvaluationResult:
        """Verify order ownership against `session_context` and prevent cross-country policy mixing."""


class ContextSanitizerPort(ABC):
    """Two-tier external content sanitizer isolating RAG chunks and tool payloads from system authority (FR-009)."""

    @abstractmethod
    def sanitize_text_chunk(
        self,
        text: str,
        source_label: str,
    ) -> GuardrailEvaluationResult:
        """Apply two-tier defense to an external text snippet."""

    @abstractmethod
    def sanitize_rag_contexts(
        self,
        contexts: List[RetrievedContext],
    ) -> Tuple[List[RetrievedContext], List[GuardrailEvaluationResult]]:
        """Sanitize a list of RetrievedContext chunks, dropping quarantined Tier-2 chunks."""

    @abstractmethod
    def sanitize_ticket_output(
        self,
        output: TicketToolOutput,
    ) -> Tuple[TicketToolOutput, List[GuardrailEvaluationResult]]:
        """Sanitize descriptions/titles inside TicketToolOutput records."""

    @abstractmethod
    def sanitize_inventory_output(
        self,
        output: InventoryToolOutput,
    ) -> Tuple[InventoryToolOutput, List[GuardrailEvaluationResult]]:
        """Sanitize descriptions/names inside InventoryToolOutput records."""


class OutputGuardrailPort(ABC):
    """Post-generation output guardrail port validating structure, security, and restricted domain content (FR-010)."""

    @abstractmethod
    def validate_output(
        self,
        query: str,
        candidate_answer: str,
        session_context: Optional[AuthenticatedSessionContext] = None,
        casual_redirect_required: bool = False,
        language: str = "en",
    ) -> GuardrailEvaluationResult:
        """Inspect and enforce guardrails on a candidate response before delivery."""


class GuardrailObservabilityPort(ABC):
    """Port interface for logging guardrail interventions and querying aggregated trigger summaries (FR-011, FR-012)."""

    @abstractmethod
    def record_evaluation(
        self,
        result: GuardrailEvaluationResult,
        session_id: str,
        raw_preview: str,
        trace_id: Optional[str] = None,
    ) -> Optional[GuardrailAuditEvent]:
        """Record a guardrail evaluation outcome and create a redacted audit event on intervention."""

    @abstractmethod
    def get_summary(
        self,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> GuardrailSummaryReport:
        """Aggregate trigger counts by failure type ('structural', 'content', 'security') and layer."""

    @abstractmethod
    def list_events(
        self,
        session_id: Optional[str] = None,
        failure_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[GuardrailAuditEvent]:
        """List recorded GuardrailAuditEvent entries ordered newest first."""

    @abstractmethod
    def clear(self) -> None:
        """Reset counters and stored events (used for deterministic test isolation)."""


__all__ = [
    "AgentMemoryRepositoryPort",
    "AuthorizationGuardrailPort",
    "ContextSanitizerPort",
    "GuardrailObservabilityPort",
    "InputGuardrailPort",
    "InventoryStockToolPort",
    "MemoryAuditLogRepositoryPort",
    "MemoryGuardrailPort",
    "OutputGuardrailPort",
    "SupportAgentServicePort",
    "SupportTicketToolPort",
    "TraceRegistryPort",
    "UserIntentClassifierPort",
]
