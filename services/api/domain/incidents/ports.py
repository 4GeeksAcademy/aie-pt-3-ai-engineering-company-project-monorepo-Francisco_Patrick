"""Incident domain driven port interfaces.

Defines the abstract repository contracts for persisting incidents and storing stream analysis results.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from domain.incidents.models import Incident


class IncidentRepositoryPort(ABC):
    """Driven port interface for Incident persistence operations."""

    @abstractmethod
    def save(self, incident: Incident) -> Incident:
        """Persist a new or updated incident entity.

        Args:
            incident: Pure domain Incident entity.

        Returns:
            Saved Incident instance.
        """
        ...

    @abstractmethod
    def find_by_id(self, incident_id: str) -> Optional[Incident]:
        """Find an incident by its unique identifier.

        Args:
            incident_id: Incident ID string.

        Returns:
            Incident domain entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def find_by_legacy_id(self, legacy_id: str) -> Optional[Incident]:
        """Find an incident by its original CSV legacy ID (for idempotency checks).

        Args:
            legacy_id: Legacy string ID.

        Returns:
            Incident domain entity if found, None otherwise.
        """
        ...

    @abstractmethod
    def find_all(
        self,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Incident]:
        """Filter incidents matching provided query criteria.

        Args:
            status: Optional lifecycle status filter.
            origin: Optional reporter origin filter.
            branch: Optional operational branch code filter.
            category: Optional category filter.

        Returns:
            List of matching Incident domain entities.
        """
        ...

    @abstractmethod
    def count_summary(self) -> Dict[str, Any]:
        """Calculate 4-dimensional aggregated metric summary totals.

        Returns:
            Dictionary containing total_incidents, by_status, by_category, by_origin, and by_branch.
        """
        ...


class AnalysisResultStorePort(ABC):
    """Driven port interface for storing and retrieving CSV stream analysis results."""

    @abstractmethod
    def save_analysis(self, analysis_id: str, data: Dict[str, Any], ttl_seconds: int = 3600) -> None:
        """Store an analysis result by unique ID."""
        ...

    @abstractmethod
    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an analysis result by unique ID."""
        ...


__all__ = ["AnalysisResultStorePort", "IncidentRepositoryPort"]
