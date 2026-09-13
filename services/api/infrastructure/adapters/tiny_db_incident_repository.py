from typing import List, Optional, Dict
from tinydb import TinyDB, Query
from domain.incident_model import Incident
from shared.incidents.enums import IncidentCategory, IncidentStatus

class TinyDBIncidentRepository:
    def __init__(self, db: TinyDB):
        self.table = db.table("incidents")

    def save(self, incident: Incident) -> Incident:
        """Saves or updates an incident in TinyDB."""
        data = incident.to_dict()
        q = Query()
        existing = self.table.search(q.id == incident.id)
        if existing:
            self.table.update(data, q.id == incident.id)
        else:
            self.table.insert(data)
        return incident

    def find_by_id(self, incident_id: str) -> Optional[Incident]:
        """Finds an incident by its unique ID."""
        q = Query()
        results = self.table.search(q.id == incident_id)
        if results and len(results) > 0:
            return Incident.from_dict(results[0])
        return None

    def find_by_legacy_id(self, legacy_id: str) -> Optional[Incident]:
        """Finds an incident by its original CSV legacy ID (for idempotency checks)."""
        q = Query()
        results = self.table.search(q.legacy_id == str(legacy_id))
        if results and len(results) > 0:
            return Incident.from_dict(results[0])
        return None

    def find_all(self) -> List[Incident]:
        """Returns all incidents in the repository."""
        records = self.table.all()
        return [Incident.from_dict(r) for r in records]

    def count_summary(self) -> Dict:
        """Computes total counts grouped by status and category."""
        records = self.table.all()
        by_status = {status.value: 0 for status in IncidentStatus}
        by_category = {cat.value: 0 for cat in IncidentCategory}

        for r in records:
            status_val = r.get("status")
            cat_val = r.get("category")
            if status_val in by_status:
                by_status[status_val] += 1
            if cat_val in by_category:
                by_category[cat_val] += 1

        return {
            "total_incidents": len(records),
            "by_status": by_status,
            "by_category": by_category
        }
