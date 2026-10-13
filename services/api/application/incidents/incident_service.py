"""Incident application service orchestrating incident lifecycle and metrics."""

from typing import Any, Dict, List, Optional

from application.incidents.dto import IncidentCreateDTO
from domain.common.exceptions import IncidentNotFoundError
from domain.common.ports import CachePort
from domain.incidents.models import Incident
from domain.incidents.ports import IncidentRepositoryPort


class IncidentService:
    """Application orchestration service for the Incident functional domain."""

    def __init__(
        self,
        incident_repo: IncidentRepositoryPort,
        cache: Optional[CachePort] = None,
    ) -> None:
        """Initialize service with injected repository and optional cache port."""
        self._repo = incident_repo
        self._cache = cache

    def create_incident(self, dto: IncidentCreateDTO) -> Incident:
        """Validate, persist, and invalidate metrics cache upon creating a new incident."""
        incident = Incident(
            title=dto.title,
            description=dto.description,
            category=dto.category,
            status=dto.status,
            origin=dto.origin,
            branch=dto.branch or "central",
            satisfaction_index=dto.satisfaction_index,
            legacy_id=dto.legacy_id,
        )
        saved = self._repo.save(incident)

        if self._cache is not None:
            self._cache.invalidate("incident_summary:global")

        return saved

    def get_incident_by_id(self, incident_id: str) -> Incident:
        """Retrieve an incident by ID or raise IncidentNotFoundError."""
        incident = self._repo.find_by_id(incident_id)
        if not incident:
            raise IncidentNotFoundError(incident_id=incident_id)
        return incident

    def update_incident_status(self, incident_id: str, new_status: str) -> Incident:
        """Update incident lifecycle status enforcing state machine invariants."""
        incident = self._repo.find_by_id(incident_id)
        if not incident:
            raise IncidentNotFoundError(incident_id=incident_id)

        # Enforces transition graph; raises InvalidStatusTransitionError if prohibited
        incident.update_status(new_status)
        saved = self._repo.save(incident)

        if self._cache is not None:
            self._cache.invalidate("incident_summary:global")

        return saved

    def list_all_incidents(
        self,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Incident]:
        """List recorded incidents matching optional multi-filter criteria."""
        return self._repo.find_all(
            status=status, origin=origin, branch=branch, category=category
        )

    def get_summary(self) -> Dict[str, Any]:
        """Retrieve 4-dimension aggregated metrics with TTL caching."""
        cache_key = "incident_summary:global"
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        summary = self._repo.count_summary()

        if self._cache is not None:
            self._cache.set(cache_key, summary, ttl_seconds=30)

        return summary


__all__ = ["IncidentService"]
