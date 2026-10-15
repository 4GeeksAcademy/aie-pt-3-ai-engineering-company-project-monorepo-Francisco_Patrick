"""Incident domain models, enums, and lifecycle transitions.

Pure business entities for TrackFlow incidents domain with zero framework or database dependencies.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Set
import uuid
from pydantic import BaseModel, Field

from domain.common.exceptions import InvalidStatusTransitionError

IncidentStatus = Literal["open", "in_progress", "resolved", "closed", "discarded"]
IncidentCategory = Literal[
    "warehouse", "reverse_logistics", "last_mile", "customer_experience"
]
IncidentOrigin = Literal["customer", "internal", "partner"]

# Lifecycle state transition graph
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "open": {"in_progress", "closed", "discarded"},
    "in_progress": {"resolved", "open", "discarded"},
    "resolved": {"closed", "in_progress"},
    "closed": set(),
    "discarded": set(),
}


class Incident(BaseModel):
    """Pure domain entity representing an operational incident with lifecycle invariants."""

    id: str = Field(
        default_factory=lambda: f"inc_{uuid.uuid4().hex[:12]}",
        description="Unique incident identifier prefix inc_",
    )
    title: str = Field(..., min_length=1, max_length=200, description="Incident title")
    description: str = Field(..., min_length=1, description="Detailed problem description")
    category: str = Field(..., description="Operational category")
    status: str = Field(default="open", description="Lifecycle status")
    origin: str = Field(default="customer", description="Incident reporter origin")
    branch: str = Field(default="central", description="Operational branch code")
    satisfaction_index: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=5.0,
        description="Customer satisfaction rating between 1.0 and 5.0",
    )
    legacy_id: Optional[str] = Field(
        default=None, description="Optional legacy CSV identifier for idempotency"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Creation ISO timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Last update ISO timestamp",
    )

    def update_status(self, new_status: str) -> None:
        """Enforces status lifecycle state transition rules.

        Args:
            new_status: Target status string.

        Raises:
            InvalidStatusTransitionError: If the transition is prohibited by state machine.
        """
        curr = self.status.lower()
        target = new_status.lower()

        allowed = ALLOWED_TRANSITIONS.get(curr, set())
        if target not in allowed:
            if curr in ("closed", "discarded", "resolved") and not allowed:
                raise InvalidStatusTransitionError(
                    f"Incident is in terminal state '{curr}' and cannot be modified."
                )
            raise InvalidStatusTransitionError(
                f"Cannot transition incident status from '{curr}' to '{target}'."
            )

        self.status = target
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert incident to storage dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Incident":
        """Reconstruct domain incident from dictionary."""
        return cls(**data)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "Incident",
    "IncidentCategory",
    "IncidentOrigin",
    "IncidentStatus",
]
