from typing import List, Optional, Dict
from tinydb import TinyDB, Query
from domain.incident_model import Incident
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin

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

    def find_all(
        self,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Incident]:
        """Returns incidents matching optional filter criteria."""
        records = self.table.all()
        filtered = []

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

    def count_summary(self) -> Dict:
        """Computes 4-dimension metric totals grouped by status, category, origin, and branch."""
        records = self.table.all()
        by_status = {s.value: 0 for s in IncidentStatus}
        by_category = {c.value: 0 for c in IncidentCategory}
        by_origin = {o.value: 0 for o in IncidentOrigin}
        by_branch: Dict[str, int] = {}

        for r in records:
            st = r.get("status")
            cat = r.get("category")
            orig = r.get("origin")
            br = r.get("branch", "central")

            if st in by_status:
                by_status[st] += 1
            if cat in by_category:
                by_category[cat] += 1
            if orig in by_origin:
                by_origin[orig] += 1

            if br:
                by_branch[br] = by_branch.get(br, 0) + 1

        return {
            "total_incidents": len(records),
            "by_status": by_status,
            "by_category": by_category,
            "by_origin": by_origin,
            "by_branch": by_branch
        }
