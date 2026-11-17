"""Thread-safe in-memory registry for storing and querying Support Agent execution traces.

Provides deterministic, offline-capable observability for every agent workflow run
(FR-008, SC-001) so QA engineers, pipeline evaluations, and diagnostic endpoints can
inspect visited node sequences, step latencies, and output states.
"""

import threading
from collections import OrderedDict
from typing import List, Optional

from domain.agent.entities import AgentTrace
from domain.agent.ports import TraceRegistryPort


class TraceRegistry(TraceRegistryPort):
    """Thread-safe bounded in-memory store for AgentTrace audit records."""

    def __init__(self, max_entries: int = 1000) -> None:
        """Initialize the trace registry.

        Args:
            max_entries: Maximum number of traces retained before evicting oldest entries.
        """
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1.")
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._traces: "OrderedDict[str, AgentTrace]" = OrderedDict()

    def record_trace(self, trace: AgentTrace) -> None:
        """Record a completed AgentTrace in a thread-safe manner.

        Args:
            trace: Immutable AgentTrace record.
        """
        with self._lock:
            if trace.trace_id in self._traces:
                self._traces.move_to_end(trace.trace_id)
            self._traces[trace.trace_id] = trace
            while len(self._traces) > self._max_entries:
                self._traces.popitem(last=False)

    def get_trace(self, trace_id: str) -> Optional[AgentTrace]:
        """Retrieve an AgentTrace by its trace_id.

        Args:
            trace_id: Unique execution trace UUID string.

        Returns:
            Matching AgentTrace or None if not found.
        """
        with self._lock:
            return self._traces.get(trace_id)

    def list_traces(self, limit: int = 50) -> List[AgentTrace]:
        """Return up to `limit` most recent traces ordered newest first.

        Args:
            limit: Maximum number of traces to return.

        Returns:
            List of AgentTrace instances.
        """
        if limit < 1:
            return []
        with self._lock:
            items = list(self._traces.values())
        items.reverse()
        return items[:limit]

    def clear(self) -> None:
        """Clear all recorded traces from memory."""
        with self._lock:
            self._traces.clear()


__all__ = ["TraceRegistry"]
