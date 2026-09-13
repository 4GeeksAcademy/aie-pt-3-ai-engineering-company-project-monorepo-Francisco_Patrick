from fastapi import APIRouter, Depends, status, Query as QueryParam
from typing import List, Dict, Any, Optional
from domain.schemas.incident_schema import IncidentCreateSchema, IncidentResponseSchema, IncidentStatusUpdateSchema
from application.services.incident_service import IncidentService
from presentation.dependencies import get_incident_service_dep
from domain.exceptions import IncidentNotFoundError

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

@router.get("/summary", response_model=Dict[str, Any])
def get_incident_summary(
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> Dict[str, Any]:
    """Returns aggregated summary metrics of incidents grouped by status, category, origin, and branch."""
    return incident_service.get_summary()

@router.get("", response_model=List[IncidentResponseSchema])
def list_incidents(
    status: Optional[str] = QueryParam(None),
    origin: Optional[str] = QueryParam(None),
    branch: Optional[str] = QueryParam(None),
    category: Optional[str] = QueryParam(None),
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> List[IncidentResponseSchema]:
    """Lists all recorded incidents with optional filters."""
    incidents = incident_service.list_all_incidents(
        status=status, origin=origin, branch=branch, category=category
    )
    return [IncidentResponseSchema(**inc.to_dict()) for inc in incidents]

@router.post("", response_model=IncidentResponseSchema, status_code=status.HTTP_201_CREATED)
def create_incident(
    schema: IncidentCreateSchema,
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> IncidentResponseSchema:
    """Creates a new incident record from form entry."""
    created = incident_service.create_incident(schema)
    return IncidentResponseSchema(**created.to_dict())

@router.get("/{incident_id}", response_model=IncidentResponseSchema)
def get_incident_by_id(
    incident_id: str,
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> IncidentResponseSchema:
    """Returns the detail of a single incident."""
    incident = incident_service.get_incident_by_id(incident_id)
    if not incident:
        raise IncidentNotFoundError(f"Incident with ID '{incident_id}' was not found.")
    return IncidentResponseSchema(**incident.to_dict())

@router.patch("/{incident_id}/status", response_model=IncidentResponseSchema)
def update_incident_status(
    incident_id: str,
    schema: IncidentStatusUpdateSchema,
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> IncidentResponseSchema:
    """Updates only the status of an incident adhering to lifecycle transition rules."""
    updated = incident_service.update_incident_status(incident_id, schema.status)
    return IncidentResponseSchema(**updated.to_dict())
