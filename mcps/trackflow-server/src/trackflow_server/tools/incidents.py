"""MCP tools for TrackFlow Incident Ticket Management (`create_incident`, `query_incidents`, `transition_incident_status`)."""

from typing import Annotated, Any, Dict, Literal, Optional

from fastmcp import FastMCP
from pydantic import Field, ValidationError

from trackflow_server.app import get_upstream_client
from trackflow_server.clients.upstream_client import MAX_RETURNED_RECORDS
from trackflow_server.models.errors import (
    LifecycleTransitionDisallowedError,
    ResourceNotFoundError,
    ToolValidationError,
)
from trackflow_server.models.schemas import (
    CreateIncidentInput,
    IncidentStatusEnum,
    QueryIncidentsInput,
    QueryIncidentsResponse,
    TransitionIncidentStatusInput,
)

IncidentCategoryLiteral = Literal[
    "warehouse",
    "delay",
    "damage",
    "billing",
    "stock",
    "system",
    "reverse_logistics",
    "last_mile",
    "customer_experience",
    "other",
]

IncidentOriginLiteral = Literal[
    "customer",
    "branch",
    "internal",
    "warehouse",
    "carrier",
    "partner",
]

IncidentBranchLiteral = Literal[
    "zaragoza",
    "los_angeles",
    "valencia",
    "central",
    "madrid",
    "barcelona",
    "bilbao",
    "sevilla",
]

IncidentStatusLiteral = Literal[
    "open",
    "in_progress",
    "resolved",
    "discarded",
]

IncidentTransitionLiteral = Literal[
    "in_progress",
    "resolved",
    "discarded",
]


async def create_incident_tool(
    title: str,
    description: str,
    category: str,
    origin: str,
    branch: str,
    **extra_kwargs: Any,
) -> Dict[str, Any]:
    """Create a new operational incident ticket in the central Incidents Manager.

    Returns the created incident record in 'open' status with its assigned ID and timestamps.
    """
    try:
        validated = CreateIncidentInput(
            title=title,
            description=description,
            category=category,  # type: ignore[arg-type]
            origin=origin,  # type: ignore[arg-type]
            branch=branch,  # type: ignore[arg-type]
            **extra_kwargs,
        )
    except ValidationError as exc:
        raise ToolValidationError(
            f"Invalid parameters for create_incident: {exc.errors()}",
            details={"validation_errors": exc.errors()},
        ) from exc

    client = get_upstream_client()
    created = await client.create_incident(validated)
    return created.model_dump()


async def query_incidents_tool(
    ticket_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    origin: Optional[str] = None,
    branch: Optional[str] = None,
    **extra_kwargs: Any,
) -> Dict[str, Any]:
    """Query operational incident records by unique ID or search filters (status, category, origin, branch).

    Results are ordered by recency and capped at 20 items.
    """
    try:
        validated = QueryIncidentsInput(
            ticket_id=ticket_id,
            status=status,  # type: ignore[arg-type]
            category=category,
            origin=origin,
            branch=branch,
            **extra_kwargs,
        )
    except ValidationError as exc:
        raise ToolValidationError(
            f"Invalid filter parameters for query_incidents: {exc.errors()}",
            details={"validation_errors": exc.errors()},
        ) from exc

    criteria = validated.model_dump(exclude_none=True)
    client = get_upstream_client()

    if validated.ticket_id:
        record = await client.get_incident(validated.ticket_id)
        # Validate against any additional filters supplied alongside ticket_id
        if validated.status and record.status.lower() != validated.status.value.lower():
            raise ResourceNotFoundError(
                f"Incident '{validated.ticket_id}' does not match filter status='{validated.status.value}'.",
                details={"ticket_id": validated.ticket_id, "status": validated.status.value},
            )
        if validated.category and record.category.lower() != validated.category.lower():
            raise ResourceNotFoundError(
                f"Incident '{validated.ticket_id}' does not match filter category='{validated.category}'.",
                details={"ticket_id": validated.ticket_id, "category": validated.category},
            )
        if validated.origin and record.origin.lower() != validated.origin.lower():
            raise ResourceNotFoundError(
                f"Incident '{validated.ticket_id}' does not match filter origin='{validated.origin}'.",
                details={"ticket_id": validated.ticket_id, "origin": validated.origin},
            )
        if validated.branch and record.branch.lower() != validated.branch.lower():
            raise ResourceNotFoundError(
                f"Incident '{validated.ticket_id}' does not match filter branch='{validated.branch}'.",
                details={"ticket_id": validated.ticket_id, "branch": validated.branch},
            )
        response = QueryIncidentsResponse(
            status="success",
            records=[record],
            total_matched=1,
            queried_criteria=criteria,
        )
        return response.model_dump()

    records = await client.list_incidents(
        status=validated.status.value if validated.status else None,
        category=validated.category,
        origin=validated.origin,
        branch=validated.branch,
    )
    total_matched = len(records)
    capped = records[:MAX_RETURNED_RECORDS]
    response = QueryIncidentsResponse(
        status="success" if total_matched > 0 else "not_found",
        records=capped,
        total_matched=total_matched,
        queried_criteria=criteria,
    )
    return response.model_dump()


async def transition_incident_status_tool(
    ticket_id: str,
    status: str,
    **extra_kwargs: Any,
) -> Dict[str, Any]:
    """Transition the lifecycle status of an existing incident ticket.

    Strictly validates transitions against the Incidents Manager state machine via
    `PATCH /api/incidents/{id}/status`.
    """
    normalized_status = (status or "").strip().lower()
    if normalized_status == IncidentStatusEnum.OPEN.value:
        raise LifecycleTransitionDisallowedError(
            "Cannot transition an existing incident back to 'open' status.",
            ticket_id=ticket_id,
            target_status=normalized_status,
        )

    try:
        validated = TransitionIncidentStatusInput(
            ticket_id=ticket_id,
            status=normalized_status,  # type: ignore[arg-type]
            **extra_kwargs,
        )
    except ValidationError as exc:
        raise ToolValidationError(
            f"Invalid parameters for transition_incident_status: {exc.errors()}",
            details={"validation_errors": exc.errors()},
        ) from exc

    client = get_upstream_client()
    updated = await client.transition_incident_status(
        ticket_id=validated.ticket_id,
        target_status=validated.status.value,
    )
    return updated.model_dump()


def register_incident_tools(mcp: FastMCP) -> None:
    """Register `create_incident`, `query_incidents`, and `transition_incident_status` on the FastMCP server."""

    @mcp.tool(
        name="create_incident",
        description=(
            "Create a new operational incident ticket in the central Incidents Manager. "
            "Returns the created incident record in 'open' status. "
            "Required OAuth scope: 'incidents:write'."
        ),
    )
    async def create_incident(
        title: Annotated[
            str,
            Field(
                min_length=3,
                max_length=200,
                description="Concise summary title of the operational incident",
            ),
        ],
        description: Annotated[
            str,
            Field(
                min_length=5,
                max_length=2000,
                description="Detailed description of the incident context and symptoms",
            ),
        ],
        category: Annotated[
            IncidentCategoryLiteral,
            Field(description="Incident classification category"),
        ],
        origin: Annotated[
            IncidentOriginLiteral,
            Field(description="Reporting source channel"),
        ],
        branch: Annotated[
            IncidentBranchLiteral,
            Field(description="Operational branch or warehouse associated with the incident"),
        ],
    ) -> Dict[str, Any]:
        return await create_incident_tool(
            title=title,
            description=description,
            category=category,
            origin=origin,
            branch=branch,
        )

    @mcp.tool(
        name="query_incidents",
        description=(
            "Query operational incident records by unique ID or search filters "
            "(status, category, origin, branch). Results are ordered by recency and "
            "capped at 20 items. Required OAuth scope: 'incidents:read'."
        ),
    )
    async def query_incidents(
        ticket_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Exact incident identifier (e.g., 'INC-001', 'inc_a1b2c3')",
            ),
        ] = None,
        status: Annotated[
            Optional[IncidentStatusLiteral],
            Field(
                default=None,
                description="Filter incidents by lifecycle status",
            ),
        ] = None,
        category: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filter incidents by category",
            ),
        ] = None,
        origin: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filter incidents by reporting origin",
            ),
        ] = None,
        branch: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filter incidents by branch",
            ),
        ] = None,
    ) -> Dict[str, Any]:
        return await query_incidents_tool(
            ticket_id=ticket_id,
            status=status,
            category=category,
            origin=origin,
            branch=branch,
        )

    @mcp.tool(
        name="transition_incident_status",
        description=(
            "Transition the lifecycle status of an existing incident ticket. "
            "Strictly validates transitions against the Incidents Manager state machine "
            "via PATCH /api/incidents/{id}/status. Required OAuth scope: 'incidents:lifecycle'."
        ),
    )
    async def transition_incident_status(
        ticket_id: Annotated[
            str,
            Field(description="Exact identifier of the incident to update"),
        ],
        status: Annotated[
            IncidentTransitionLiteral,
            Field(description="Target lifecycle status to transition to"),
        ],
    ) -> Dict[str, Any]:
        return await transition_incident_status_tool(
            ticket_id=ticket_id,
            status=status,
        )


__all__ = [
    "create_incident_tool",
    "query_incidents_tool",
    "register_incident_tools",
    "transition_incident_status_tool",
]
