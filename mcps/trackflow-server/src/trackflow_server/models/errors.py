"""Canonical error taxonomy and domain exceptions for the TrackFlow MCP Server."""

from enum import Enum
from typing import Any, Dict, Optional


class McpErrorCode(str, Enum):
    """Standardized error codes returned across the TrackFlow MCP Server."""

    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    INVENTORY_MUTATION_REJECTED = "INVENTORY_MUTATION_REJECTED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    LIFECYCLE_TRANSITION_DISALLOWED = "LIFECYCLE_TRANSITION_DISALLOWED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"


ERROR_METADATA: Dict[McpErrorCode, tuple[int, int]] = {
    McpErrorCode.AUTHENTICATION_REQUIRED: (401, -32001),
    McpErrorCode.INSUFFICIENT_SCOPE: (403, -32003),
    McpErrorCode.INVENTORY_MUTATION_REJECTED: (403, -32003),
    McpErrorCode.VALIDATION_ERROR: (422, -32602),
    McpErrorCode.LIFECYCLE_TRANSITION_DISALLOWED: (400, -32004),
    McpErrorCode.RESOURCE_NOT_FOUND: (404, -32005),
    McpErrorCode.UPSTREAM_UNAVAILABLE: (503, -32002),
}


class TrackFlowMcpError(Exception):
    """Base categorized error for all TrackFlow MCP Server operations."""

    def __init__(
        self,
        error_code: McpErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        http_status, rpc_code = ERROR_METADATA.get(error_code, (500, -32000))
        self.http_status = http_status
        self.rpc_code = rpc_code

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error to a structured dictionary safe for clients."""
        payload: Dict[str, Any] = {
            "status": "error",
            "error_code": self.error_code.value,
            "http_status": self.http_status,
            "rpc_code": self.rpc_code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class AuthenticationRequiredError(TrackFlowMcpError):
    """Raised when a request lacks a valid or unexpired OAuth 2.1 Bearer token."""

    def __init__(
        self,
        message: str = "Valid OAuth 2.1 Bearer authentication token is required.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(McpErrorCode.AUTHENTICATION_REQUIRED, message, details)


class InsufficientScopeError(TrackFlowMcpError):
    """Raised when the caller's token lacks the required scope for a tool."""

    def __init__(
        self,
        required_scope: str,
        granted_scopes: Optional[list[str]] = None,
        tool_name: Optional[str] = None,
    ) -> None:
        granted = granted_scopes or []
        target = f" for tool '{tool_name}'" if tool_name else ""
        msg = (
            f"Insufficient OAuth scope{target}: required '{required_scope}', "
            f"granted {granted}."
        )
        super().__init__(
            McpErrorCode.INSUFFICIENT_SCOPE,
            msg,
            details={
                "required_scope": required_scope,
                "granted_scopes": granted,
                "tool_name": tool_name,
            },
        )


class InventoryMutationRejectedError(TrackFlowMcpError):
    """Raised when any caller attempts to write, update, adjust, or mutate inventory."""

    def __init__(
        self,
        message: str = (
            "Inventory access via MCP is strictly read-only. "
            "Any attempt to create, update, adjust, or delete stock records is prohibited."
        ),
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(McpErrorCode.INVENTORY_MUTATION_REJECTED, message, details)


class ToolValidationError(TrackFlowMcpError):
    """Raised when tool arguments fail schema or domain validation."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(McpErrorCode.VALIDATION_ERROR, message, details)


class LifecycleTransitionDisallowedError(TrackFlowMcpError):
    """Raised when an incident status transition violates the lifecycle state machine."""

    def __init__(
        self,
        message: str,
        ticket_id: Optional[str] = None,
        current_status: Optional[str] = None,
        target_status: Optional[str] = None,
    ) -> None:
        details: Dict[str, Any] = {}
        if ticket_id:
            details["ticket_id"] = ticket_id
        if current_status:
            details["current_status"] = current_status
        if target_status:
            details["target_status"] = target_status
        super().__init__(McpErrorCode.LIFECYCLE_TRANSITION_DISALLOWED, message, details)


class ResourceNotFoundError(TrackFlowMcpError):
    """Raised when a requested incident ticket or inventory SKU does not exist."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(McpErrorCode.RESOURCE_NOT_FOUND, message, details)


class UpstreamUnavailableError(TrackFlowMcpError):
    """Raised when the upstream Incidents or Inventory API times out or is unreachable."""

    def __init__(
        self,
        message: str = "Upstream TrackFlow service timed out or is temporarily unavailable.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(McpErrorCode.UPSTREAM_UNAVAILABLE, message, details)


__all__ = [
    "AuthenticationRequiredError",
    "ERROR_METADATA",
    "InsufficientScopeError",
    "InventoryMutationRejectedError",
    "LifecycleTransitionDisallowedError",
    "McpErrorCode",
    "ResourceNotFoundError",
    "ToolValidationError",
    "TrackFlowMcpError",
    "UpstreamUnavailableError",
]
