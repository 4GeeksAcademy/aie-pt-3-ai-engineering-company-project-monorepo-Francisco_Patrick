from typing import List, Optional, Dict
from domain.incident_model import Incident
from domain.schemas.incident_schema import IncidentCreateSchema
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

    def list_all_incidents(self) -> List[Incident]:
        """Lists all recorded incidents."""
        return self.repo.find_all()

    def get_summary(self) -> Dict:
        """Returns total counts grouped by status and category."""
        return self.repo.count_summary()
