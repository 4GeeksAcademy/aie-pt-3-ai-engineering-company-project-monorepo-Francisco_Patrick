"""Abstract port interfaces for the TrackFlow Support Agent domain.

Adheres strictly to Hexagonal Architecture and Monorepo Constitution Principle I & II,
decoupling presentation controllers and LangGraph orchestration from operational
tool adapters (`SupportTicketToolPort`, `InventoryStockToolPort`) and trace storage.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from domain.agent.entities import (
    AgentCheckpoint,
    AgentQueryRequest,
    AgentQueryResult,
    AgentTrace,
    InventoryToolInput,
    InventoryToolOutput,
    TicketToolInput,
    TicketToolOutput,
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


__all__ = [
    "InventoryStockToolPort",
    "SupportAgentServicePort",
    "SupportTicketToolPort",
    "TraceRegistryPort",
]
