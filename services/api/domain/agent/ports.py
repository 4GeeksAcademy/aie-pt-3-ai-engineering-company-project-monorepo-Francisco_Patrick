"""Abstract port interfaces for the TrackFlow Support Agent domain.

Adheres strictly to Hexagonal Architecture and Monorepo Constitution Principle I & II,
decoupling presentation controllers and LangGraph orchestration from operational
tool adapters (`SupportTicketToolPort`, `InventoryStockToolPort`) and trace storage.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.agent.entities import (
    AgentCheckpoint,
    AgentQueryRequest,
    AgentQueryResult,
    AgentTrace,
    ConsolidatedCarrierProfile,
    InventoryToolInput,
    InventoryToolOutput,
    MemoryAuditLogEntry,
    MemoryCategory,
    MemoryGuardrailVerdict,
    PersistentMemoryRecord,
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


__all__ = [
    "AgentMemoryRepositoryPort",
    "InventoryStockToolPort",
    "MemoryAuditLogRepositoryPort",
    "MemoryGuardrailPort",
    "SupportAgentServicePort",
    "SupportTicketToolPort",
    "TraceRegistryPort",
    "UserIntentClassifierPort",
]
