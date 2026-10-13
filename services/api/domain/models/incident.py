from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Optional
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin

@dataclass
class Incident:
    title: str
    description: str
    category: IncidentCategory
    status: IncidentStatus = IncidentStatus.OPEN
    origin: IncidentOrigin = IncidentOrigin.CUSTOMER
    branch: str = "central"
    id: str = field(default_factory=lambda: f"inc_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    legacy_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value if isinstance(self.category, IncidentCategory) else self.category,
            "status": self.status.value if isinstance(self.status, IncidentStatus) else self.status,
            "origin": self.origin.value if isinstance(self.origin, IncidentOrigin) else self.origin,
            "branch": self.branch,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "legacy_id": self.legacy_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Incident":
        return cls(
            id=data.get("id"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=IncidentCategory(data.get("category")),
            status=IncidentStatus(data.get("status", "open")),
            origin=IncidentOrigin(data.get("origin", "customer")),
            branch=data.get("branch", "central"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            legacy_id=data.get("legacy_id"),
        )
