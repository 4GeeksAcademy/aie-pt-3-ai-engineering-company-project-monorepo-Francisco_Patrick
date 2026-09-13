from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Optional
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin
from domain.exceptions import InvalidStatusTransitionError

ALLOWED_TRANSITIONS = {
    IncidentStatus.OPEN: {IncidentStatus.IN_PROGRESS, IncidentStatus.DISCARDED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.RESOLVED, IncidentStatus.DISCARDED},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.DISCARDED: set(),
}

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

    def update_status(self, new_status: IncidentStatus) -> None:
        """Enforces status lifecycle state transition rules."""
        if isinstance(new_status, str):
            new_status = IncidentStatus(new_status)

        current_allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in current_allowed:
            if self.status in (IncidentStatus.RESOLVED, IncidentStatus.DISCARDED):
                raise InvalidStatusTransitionError(
                    f"Incident is in terminal state '{self.status.value}' and cannot be modified."
                )
            raise InvalidStatusTransitionError(
                f"Cannot transition incident status from '{self.status.value}' to '{new_status.value}'."
            )

        self.status = new_status
        self.updated_at = datetime.now(timezone.utc).isoformat()

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
        kwargs = {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "category": IncidentCategory(data.get("category")),
            "status": IncidentStatus(data.get("status", "open")),
            "origin": IncidentOrigin(data.get("origin", "customer")),
            "branch": data.get("branch", "central"),
            "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
            "updated_at": data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            "legacy_id": data.get("legacy_id"),
        }
        if data.get("id"):
            kwargs["id"] = data["id"]
        return cls(**kwargs)
