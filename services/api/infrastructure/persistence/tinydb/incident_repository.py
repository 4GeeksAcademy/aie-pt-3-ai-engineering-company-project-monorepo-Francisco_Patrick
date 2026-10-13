"""TinyDB persistence adapter for Incident domain entities.

Implements IncidentRepositoryPort using TinyDB document store.
"""

from typing import Any, Dict, List, Optional
from tinydb import Query, TinyDB

from domain.incidents.models import Incident
from domain.incidents.ports import IncidentRepositoryPort
from infrastructure.persistence.tinydb.client import get_table, get_tinydb


class TinyDBIncidentRepository(IncidentRepositoryPort):
    """TinyDB document store adapter implementing IncidentRepositoryPort."""

    def __init__(self, db: Optional[TinyDB] = None, table_name: str = "incidents") -> None:
        """Initialize incident repository with TinyDB table."""
        self._db = db if db is not None else get_tinydb()
        self.table = get_table(table_name, db=self._db)
        self.IncidentQuery = Query()

    def save(self, incident: Incident) -> Incident:
        """Persist a new or modified incident entity."""
        data = incident.to_dict()
        existing = self.table.search(self.IncidentQuery.id == incident.id)
        if existing:
            self.table.update(data, self.IncidentQuery.id == incident.id)
        else:
            self.table.insert(data)
        return incident

    def find_by_id(self, incident_id: str) -> Optional[Incident]:
        """Find an incident by unique identifier."""
        results = self.table.search(self.IncidentQuery.id == incident_id)
        if results and len(results) > 0:
            return Incident.from_dict(results[0])
        return None

    def find_by_legacy_id(self, legacy_id: str) -> Optional[Incident]:
        """Find an incident by legacy CSV identifier (idempotency)."""
        results = self.table.search(self.IncidentQuery.legacy_id == str(legacy_id))
        if results and len(results) > 0:
            return Incident.from_dict(results[0])
        return None

    def find_all(
        self,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Incident]:
        """List incidents matching optional filter criteria."""
        records = self.table.all()
        filtered: List[Dict[str, Any]] = []

        for r in records:
            if status and r.get("status") != status:
                continue
            if origin and r.get("origin") != origin:
                continue
            if branch and r.get("branch") != branch:
                continue
            if category and r.get("category") != category:
                continue
            filtered.append(r)

        return [Incident.from_dict(r) for r in filtered]

    def count_summary(self) -> Dict[str, Any]:
        """Calculate 4-dimension aggregated metric counts."""
        records = self.table.all()
        by_status: Dict[str, int] = {
            "open": 0,
            "in_progress": 0,
            "resolved": 0,
            "closed": 0,
            "discarded": 0,
        }
        by_category: Dict[str, int] = {
            "warehouse": 0,
            "last_mile": 0,
            "reverse_logistics": 0,
            "customer_experience": 0,
        }
        by_origin: Dict[str, int] = {
            "customer": 0,
            "internal": 0,
            "partner": 0,
        }
        by_branch: Dict[str, int] = {}

        for r in records:
            st = str(r.get("status", "")).lower()
            cat = str(r.get("category", "")).lower()
            orig = str(r.get("origin", "")).lower()
            br = r.get("branch", "central")

            if st in by_status:
                by_status[st] += 1
            else:
                by_status[st] = 1

            if cat in by_category:
                by_category[cat] += 1
            else:
                by_category[cat] = 1

            if orig in by_origin:
                by_origin[orig] += 1
            else:
                by_origin[orig] = 1

            if br:
                by_branch[br] = by_branch.get(br, 0) + 1

        return {
            "total_incidents": len(records),
            "by_status": by_status,
            "by_category": by_category,
            "by_origin": by_origin,
            "by_branch": by_branch,
        }


__all__ = ["TinyDBIncidentRepository"]
