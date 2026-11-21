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


class ToolExecutionTimeoutError(AgentDomainException):
    """Raised when an operational tool call exceeds its configured numerical timeout."""

    def __init__(
        self,
        tool_name: str,
        timeout_seconds: float,
        message: Optional[str] = None,
    ) -> None:
        """Initialize tool execution timeout error."""
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        resolved_msg = (
            message
            or f"Operational tool '{tool_name}' timed out after {timeout_seconds:.1f} seconds."
        )
        super().__init__(resolved_msg)


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


class MemoryNotFoundError(EntityNotFoundError):
    """Raised when a persistent memory record, carrier profile, or pending proposal cannot be found."""

    def __init__(
        self,
        entity_id: str,
        entity_name: str = "AgentMemory",
        message: Optional[str] = None,
    ) -> None:
        """Initialize memory not found error."""
        resolved_msg = message or f"{entity_name} '{entity_id}' was not found."
        super().__init__(message=resolved_msg, entity_name=entity_name, entity_id=entity_id)


class MemoryGuardrailViolationError(AgentDomainException):
    """Raised when a candidate memory violates TrackFlow anti-poisoning or sensitive data guardrails."""

    def __init__(
        self,
        violation_code: str,
        reason: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize memory guardrail violation error."""
        self.violation_code = violation_code
        self.reason = reason
        resolved_msg = message or f"Memory guardrail violation [{violation_code}]: {reason}"
        super().__init__(resolved_msg)


class MemoryStorageError(AgentDomainException):
    """Raised when reading or writing to the dedicated agent memory store fails."""

    def __init__(
        self,
        message: str = "An error occurred while accessing persistent agent memory storage.",
    ) -> None:
        """Initialize memory storage error."""
        super().__init__(message)


__all__ = [
    "AgentDomainException",
    "GraphCompilationError",
    "MemoryGuardrailViolationError",
    "MemoryNotFoundError",
    "MemoryStorageError",
    "StateValidationError",
    "ToolExecutionTimeoutError",
    "TraceNotFoundError",
    "WorkflowExecutionError",
]
