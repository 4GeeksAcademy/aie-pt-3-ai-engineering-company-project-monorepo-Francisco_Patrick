from typing import List, Optional, Dict
from domain.incident_model import Incident
from domain.schemas.incident_schema import IncidentCreateSchema
from domain.exceptions import IncidentNotFoundError
from shared.incidents.enums import IncidentStatus
from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository

class IncidentService:
    def __init__(self, repo: TinyDBIncidentRepository):
        self.repo = repo

    def create_incident(self, schema: IncidentCreateSchema) -> Incident:
        """Validates and persists a new incident."""
        incident = Incident(
            title=schema.title,
            description=schema.description,
            category=schema.category,
            status=schema.status,
            origin=schema.origin,
            branch=schema.branch or "central"
        )
        return self.repo.save(incident)

    def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
        """Retrieves an incident by unique ID."""
        return self.repo.find_by_id(incident_id)

    def update_incident_status(self, incident_id: str, new_status: IncidentStatus) -> Incident:
        """Updates the lifecycle status of an existing incident."""
        incident = self.repo.find_by_id(incident_id)
        if not incident:
            raise IncidentNotFoundError(f"Incident with ID '{incident_id}' was not found.")

        incident.update_status(new_status)
        return self.repo.save(incident)

    def list_all_incidents(
        self,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Incident]:
        """Lists recorded incidents with optional filters."""
        return self.repo.find_all(status=status, origin=origin, branch=branch, category=category)

    def get_summary(self) -> Dict:
        """Returns 4-dimension metric counts."""
        return self.repo.count_summary()
