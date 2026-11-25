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


class GuardrailBlockedError(AgentDomainException):
    """Raised when an input, context, or output guardrail deterministically blocks an operation (FR-003)."""

    def __init__(
        self,
        layer: str,
        failure_category: str,
        reason_code: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize guardrail blocked error."""
        self.layer = layer
        self.failure_category = failure_category
        self.reason_code = reason_code
        resolved_msg = (
            message
            or f"Guardrail intervention on layer '{layer}' [{failure_category}:{reason_code}]."
        )
        super().__init__(resolved_msg)


class UnauthorizedOrderAccessError(GuardrailBlockedError):
    """Raised when a session attempts to query an order or tracking ID outside its authorized scope (FR-007)."""

    def __init__(
        self,
        order_id: str,
        session_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Initialize unauthorized order access error."""
        self.order_id = order_id
        self.session_id = session_id
        resolved_msg = (
            message
            or f"Session is not authorized to access tracking or details for order '{order_id}'."
        )
        super().__init__(
            layer="authorization_guard",
            failure_category="security",
            reason_code="UNAUTHORIZED_ORDER_ACCESS",
            message=resolved_msg,
        )


class ThreadOwnershipMismatchError(AgentDomainException):
    """Raised when an authenticated operator attempts to access or bind a conversation thread owned by another user (FR-003)."""

    def __init__(
        self,
        thread_id: str,
        requester_user_id: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize thread ownership mismatch error."""
        self.thread_id = thread_id
        self.requester_user_id = requester_user_id
        resolved_msg = (
            message
            or f"Conversation thread '{thread_id}' is bound to a different operator account."
        )
        super().__init__(resolved_msg)


__all__ = [
    "AgentDomainException",
    "GraphCompilationError",
    "GuardrailBlockedError",
    "MemoryGuardrailViolationError",
    "MemoryNotFoundError",
    "MemoryStorageError",
    "StateValidationError",
    "ThreadOwnershipMismatchError",
    "ToolExecutionTimeoutError",
    "TraceNotFoundError",
    "UnauthorizedOrderAccessError",
    "WorkflowExecutionError",
]
