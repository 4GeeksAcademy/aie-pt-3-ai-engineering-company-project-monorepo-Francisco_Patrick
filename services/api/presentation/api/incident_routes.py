from fastapi import APIRouter, Depends, status
from typing import List, Dict, Any
from domain.schemas.incident_schema import IncidentCreateSchema, IncidentResponseSchema
from application.services.incident_service import IncidentService
from presentation.dependencies import get_incident_service_dep

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

@router.get("/summary", response_model=Dict[str, Any])
def get_incident_summary(
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> Dict[str, Any]:
    """Returns aggregated summary metrics of incidents grouped by status and category."""
    return incident_service.get_summary()

@router.get("", response_model=List[IncidentResponseSchema])
def list_incidents(
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> List[IncidentResponseSchema]:
    """Lists all recorded incidents."""
    incidents = incident_service.list_all_incidents()
    return [IncidentResponseSchema(**inc.to_dict()) for inc in incidents]

@router.post("", response_model=IncidentResponseSchema, status_code=status.HTTP_201_CREATED)
def create_incident(
    schema: IncidentCreateSchema,
    incident_service: IncidentService = Depends(get_incident_service_dep)
) -> IncidentResponseSchema:
    """Creates a new incident record from form entry."""
    created = incident_service.create_incident(schema)
    return IncidentResponseSchema(**created.to_dict())
