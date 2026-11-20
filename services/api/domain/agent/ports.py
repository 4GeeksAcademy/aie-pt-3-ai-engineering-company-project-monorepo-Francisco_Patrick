"""Abstract port interfaces for the TrackFlow Support Agent domain.

Adheres strictly to Hexagonal Architecture and Monorepo Constitution Principle I & II,
decoupling presentation controllers from workflow internals and trace storage.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from domain.agent.entities import (
    AgentCheckpoint,
    AgentQueryRequest,
    AgentQueryResult,
    AgentTrace,
)


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
    "SupportAgentServicePort",
    "TraceRegistryPort",
]
