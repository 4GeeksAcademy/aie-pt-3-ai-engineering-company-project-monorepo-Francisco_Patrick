"""Domain exceptions for the TrackFlow Support Agent workflow."""

from typing import Optional

from domain.common.exceptions import DomainException, EntityNotFoundError


class AgentDomainException(DomainException):
    """Base exception for Support Agent domain operations."""

    def __init__(self, message: str = "An agent workflow operation failed.") -> None:
        """Initialize agent domain exception."""
        super().__init__(message)


class GraphCompilationError(AgentDomainException):
    """Raised at build/startup time when the LangGraph state graph is structurally invalid."""

    def __init__(
        self,
        message: str = "Failed to compile the support agent state graph due to structural misconfiguration.",
    ) -> None:
        """Initialize graph compilation error."""
        super().__init__(message)


class WorkflowExecutionError(AgentDomainException):
    """Raised when an unhandled runtime error occurs during agent graph execution."""

    def __init__(
        self,
        message: str = "An internal error occurred while processing the agent workflow.",
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize workflow execution error with optional trace correlation ID."""
        self.trace_id = trace_id
        super().__init__(message)


class StateValidationError(AgentDomainException):
    """Raised when the agent state payload violates domain contract invariants."""

    def __init__(
        self,
        message: str = "Agent state validation failed.",
    ) -> None:
        """Initialize state validation error."""
        super().__init__(message)


class TraceNotFoundError(EntityNotFoundError):
    """Raised when an execution trace cannot be found by trace_id."""

    def __init__(
        self,
        trace_id: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize trace not found error."""
        resolved_msg = message or f"Execution trace '{trace_id}' was not found."
        super().__init__(message=resolved_msg, entity_name="AgentTrace", entity_id=trace_id)


__all__ = [
    "AgentDomainException",
    "GraphCompilationError",
    "StateValidationError",
    "TraceNotFoundError",
    "WorkflowExecutionError",
]
