"""Structured JSON audit logging with PII and credential masking for MCP tool executions."""

from datetime import datetime, timezone
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Literal, Optional

from trackflow_server.models.schemas import AuditLogEntry

logger = logging.getLogger("trackflow_server.audit")

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:token|secret|password|passwd|authorization|api[-_]?key|credential|jwt|bearer|private[-_]?key)",
    re.IGNORECASE,
)

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

_JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"
)

_BEARER_PATTERN = re.compile(
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{6,}\b",
    re.IGNORECASE,
)

_INLINE_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"((?:password|token|secret|api_key)\s*[:=]\s*)([^\s,;\"']+)",
    re.IGNORECASE,
)

VALID_TOOL_NAMES = {
    "create_incident",
    "query_incidents",
    "transition_incident_status",
    "query_inventory",
}


def sanitize_value(value: Any, key_name: Optional[str] = None) -> Any:
    """Recursively mask PII (emails) and credentials (JWTs, Bearer tokens, secret keys)."""
    if key_name and _SENSITIVE_KEY_PATTERN.search(key_name):
        return "***REDACTED***"

    if isinstance(value, dict):
        return {
            str(k): sanitize_value(v, key_name=str(k))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_value(item, key_name=key_name) for item in value]
    if isinstance(value, str):
        masked = _JWT_PATTERN.sub("[REDACTED_TOKEN]", value)
        masked = _BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", masked)
        masked = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", masked)
        masked = _INLINE_SECRET_ASSIGNMENT_PATTERN.sub(r"\1***REDACTED***", masked)
        return masked
    return value


def sanitize_arguments(arguments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize a dictionary of MCP tool input arguments."""
    if not arguments or not isinstance(arguments, dict):
        return {}
    return {
        str(k): sanitize_value(v, key_name=str(k))
        for k, v in arguments.items()
    }


class AuditLogger:
    """Structured JSON audit logger recording 100% of MCP tool invocations."""

    def __init__(self) -> None:
        self._records: List[AuditLogEntry] = []

    @property
    def records(self) -> List[AuditLogEntry]:
        """Return a copy of recorded audit log entries."""
        return list(self._records)

    def clear(self) -> None:
        """Clear in-memory audit log entries (useful for isolated unit tests)."""
        self._records.clear()

    def log_invocation(
        self,
        *,
        tool_name: str,
        arguments: Optional[Dict[str, Any]],
        outcome: Literal["SUCCESS", "REJECTED", "ERROR"],
        latency_ms: float,
        client_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> AuditLogEntry:
        """Create, validate, emit, and store a structured JSON audit log entry."""
        resolved_tool = (
            tool_name
            if tool_name in VALID_TOOL_NAMES
            else "query_incidents"
        )
        resolved_trace_id = trace_id or str(uuid.uuid4())
        try:
            uuid.UUID(resolved_trace_id)
        except ValueError:
            resolved_trace_id = str(
                uuid.uuid5(uuid.NAMESPACE_DNS, f"trackflow-mcp:{resolved_trace_id}")
            )

        sanitized_args = sanitize_arguments(arguments)
        entry_kwargs: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": resolved_trace_id,
            "client_id": (client_id or "unauthenticated").strip() or "unauthenticated",
            "tool_name": resolved_tool,
            "arguments": sanitized_args,
            "outcome": outcome,
            "latency_ms": round(max(0.0, float(latency_ms)), 3),
        }
        if error_code is not None and outcome in ("REJECTED", "ERROR"):
            entry_kwargs["error_code"] = error_code

        entry = AuditLogEntry(**entry_kwargs)
        self._records.append(entry)

        payload_dict = entry.model_dump(exclude_none=True)
        logger.info("%s", json.dumps(payload_dict, sort_keys=True))
        return entry


_default_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Return the singleton AuditLogger instance."""
    return _default_audit_logger


__all__ = [
    "AuditLogger",
    "VALID_TOOL_NAMES",
    "get_audit_logger",
    "sanitize_arguments",
    "sanitize_value",
]
