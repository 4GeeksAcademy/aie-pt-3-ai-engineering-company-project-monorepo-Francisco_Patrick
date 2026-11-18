"""Pydantic domain schemas and validation models for the TrackFlow MCP Server."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set
from pydantic import BaseModel, ConfigDict, Field


class IncidentStatusEnum(str, Enum):
    """Valid lifecycle states for an Incident Ticket."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"


class IncidentTransitionTargetEnum(str, Enum):
    """Allowed target states when transitioning an existing incident's status."""

    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"


class IncidentCategoryEnum(str, Enum):
    """Problem classification categories in the Incidents Manager (aligned with shared.incidents.enums.IncidentCategory)."""

    WAREHOUSE = "warehouse"
    REVERSE_LOGISTICS = "reverse_logistics"
    LAST_MILE = "last_mile"
    CUSTOMER_EXPERIENCE = "customer_experience"


class IncidentOriginEnum(str, Enum):
    """Reporting source channels in the Incidents Manager (aligned with shared.incidents.enums.IncidentOrigin)."""

    CUSTOMER = "customer"
    BRANCH = "branch"
    INTERNAL = "internal"


class IncidentBranchEnum(str, Enum):
    """Operational branches and warehouses in TrackFlow."""

    ZARAGOZA = "zaragoza"
    LOS_ANGELES = "los_angeles"
    VALENCIA = "valencia"
    CENTRAL = "central"
    MADRID = "madrid"
    BARCELONA = "barcelona"
    BILBAO = "bilbao"
    SEVILLA = "sevilla"


ALLOWED_LIFECYCLE_TRANSITIONS: Dict[str, Set[str]] = {
    IncidentStatusEnum.OPEN.value: {
        IncidentStatusEnum.IN_PROGRESS.value,
        IncidentStatusEnum.DISCARDED.value,
    },
    IncidentStatusEnum.IN_PROGRESS.value: {
        IncidentStatusEnum.RESOLVED.value,
        IncidentStatusEnum.DISCARDED.value,
    },
    IncidentStatusEnum.RESOLVED.value: set(),
    IncidentStatusEnum.DISCARDED.value: set(),
}


def validate_lifecycle_transition(current_status: str, target_status: str) -> tuple[bool, Optional[str]]:
    """Validate whether transitioning from `current_status` to `target_status` is permitted.

    Args:
        current_status: Current status string of the incident.
        target_status: Requested new status string.

    Returns:
        Tuple of `(is_allowed, error_reason)`.
    """
    curr = current_status.strip().lower()
    targ = target_status.strip().lower()

    if curr in (IncidentStatusEnum.RESOLVED.value, IncidentStatusEnum.DISCARDED.value):
        return (
            False,
            f"Incident is in terminal state '{curr}' and cannot be transitioned to '{targ}'.",
        )

    allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(curr, set())
    if targ not in allowed:
        return (
            False,
            f"Cannot transition incident status from '{curr}' to '{targ}'. "
            f"Allowed transitions from '{curr}': {sorted(allowed) if allowed else 'none'}.",
        )
    return (True, None)


class CreateIncidentInput(BaseModel):
    """Input schema for the `create_incident` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Concise summary title of the operational incident",
    )
    description: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Detailed description of the incident context and symptoms",
    )
    category: IncidentCategoryEnum = Field(
        ...,
        description="Incident classification category",
    )
    origin: IncidentOriginEnum = Field(
        ...,
        description="Reporting source channel",
    )
    branch: IncidentBranchEnum = Field(
        ...,
        description="Operational branch or warehouse associated with the incident",
    )


class QueryIncidentsInput(BaseModel):
    """Input schema for the `query_incidents` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: Optional[str] = Field(
        default=None,
        description="Exact incident identifier (e.g., 'INC-001', 'inc_a1b2c3')",
    )
    status: Optional[IncidentStatusEnum] = Field(
        default=None,
        description="Filter incidents by lifecycle status",
    )
    category: Optional[str] = Field(
        default=None,
        description="Filter incidents by category",
    )
    origin: Optional[str] = Field(
        default=None,
        description="Filter incidents by reporting origin",
    )
    branch: Optional[str] = Field(
        default=None,
        description="Filter incidents by branch",
    )


class TransitionIncidentStatusInput(BaseModel):
    """Input schema for the `transition_incident_status` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(
        ...,
        min_length=1,
        description="Exact identifier of the incident to update",
    )
    status: IncidentTransitionTargetEnum = Field(
        ...,
        description="Target lifecycle status to transition to",
    )


class IncidentTicketModel(BaseModel):
    """Domain projection of an Incident Ticket conforming to the Incidents Manager model."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    description: str
    status: str
    category: str
    origin: str
    branch: str
    created_at: str
    updated_at: str


class QueryIncidentsResponse(BaseModel):
    """Structured response returned by `query_incidents`."""

    status: Literal["success", "not_found"] = "success"
    records: List[IncidentTicketModel] = Field(default_factory=list)
    total_matched: int = 0
    queried_criteria: Dict[str, Any] = Field(default_factory=dict)


class QueryInventoryInput(BaseModel):
    """Input schema for the strictly read-only `query_inventory` MCP tool."""

    model_config = ConfigDict(extra="forbid")

    sku: Optional[str] = Field(
        default=None,
        description="Stock Keeping Unit code (e.g. 'TF-001')",
    )
    product_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Numerical product ID",
    )
    query: Optional[str] = Field(
        default=None,
        description="Free text query matching product name or description",
    )


class InventoryProductModel(BaseModel):
    """Domain projection of an Inventory Product record."""

    model_config = ConfigDict(extra="ignore")

    id: int
    sku: str
    name: str
    description: str = ""
    stock: int = Field(ge=0)
    min_threshold: int = Field(ge=0)
    is_low_stock: bool
    warehouse_id: str = "central"


class QueryInventoryResponse(BaseModel):
    """Structured response returned by `query_inventory`."""

    status: Literal["success", "not_found"] = "success"
    records: List[InventoryProductModel] = Field(default_factory=list)
    total_matched: int = 0
    queried_criteria: Dict[str, Any] = Field(default_factory=dict)


class OAuthSecurityContext(BaseModel):
    """Validated OAuth 2.1 security context extracted from caller's Bearer JWT."""

    client_id: str
    subject: str
    issuer: str
    audience: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    expires_at: Optional[int] = None


class ProtectedResourceMetadata(BaseModel):
    """OAuth 2.0 Protected Resource Metadata (RFC 9728)."""

    resource: str
    authorization_servers: List[str]
    scopes_supported: List[str] = Field(
        default_factory=lambda: [
            "incidents:read",
            "incidents:write",
            "incidents:lifecycle",
            "inventory:read",
        ]
    )
    bearer_methods_supported: List[str] = Field(default_factory=lambda: ["header"])
    resource_documentation: Optional[str] = None


class AuditLogEntry(BaseModel):
    """Structured audit log entry emitted per MCP tool invocation."""

    model_config = ConfigDict(extra="forbid")

    timestamp: str
    trace_id: str
    client_id: str
    tool_name: Literal[
        "create_incident",
        "query_incidents",
        "transition_incident_status",
        "query_inventory",
    ]
    arguments: Dict[str, Any]
    outcome: Literal["SUCCESS", "REJECTED", "ERROR"]
    error_code: Optional[
        Literal[
            "AUTHENTICATION_REQUIRED",
            "INSUFFICIENT_SCOPE",
            "INVENTORY_MUTATION_REJECTED",
            "VALIDATION_ERROR",
            "LIFECYCLE_TRANSITION_DISALLOWED",
            "RESOURCE_NOT_FOUND",
            "UPSTREAM_UNAVAILABLE",
        ]
    ] = None
    latency_ms: float = Field(ge=0.0)


__all__ = [
    "ALLOWED_LIFECYCLE_TRANSITIONS",
    "AuditLogEntry",
    "CreateIncidentInput",
    "IncidentBranchEnum",
    "IncidentCategoryEnum",
    "IncidentOriginEnum",
    "IncidentStatusEnum",
    "IncidentTicketModel",
    "IncidentTransitionTargetEnum",
    "InventoryProductModel",
    "OAuthSecurityContext",
    "ProtectedResourceMetadata",
    "QueryIncidentsInput",
    "QueryIncidentsResponse",
    "QueryInventoryInput",
    "QueryInventoryResponse",
    "TransitionIncidentStatusInput",
    "validate_lifecycle_transition",
]
