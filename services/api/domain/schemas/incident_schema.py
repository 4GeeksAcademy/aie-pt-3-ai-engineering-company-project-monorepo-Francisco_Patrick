from pydantic import BaseModel, Field, field_validator
from typing import Optional
from shared.incidents.enums import IncidentCategory, IncidentStatus, IncidentOrigin

class IncidentCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, description="Brief incident title")
    description: str = Field(..., min_length=1, description="Detailed incident description")
    category: IncidentCategory = Field(..., description="Category: warehouse, reverse_logistics, last_mile, customer_experience")
    status: IncidentStatus = Field(default=IncidentStatus.OPEN, description="Status: open, in_progress, resolved, discarded")
    origin: IncidentOrigin = Field(default=IncidentOrigin.INTERNAL, description="Origin: customer, branch, internal")
    branch: str = Field(default="central", min_length=1, description="Branch identifier")

    @field_validator("title", "description", "branch")
    @classmethod
    def prevent_empty_whitespace(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field cannot be empty or blank whitespace")
        return value.strip()

class IncidentResponseSchema(BaseModel):
    id: str
    title: str
    description: str
    category: IncidentCategory
    status: IncidentStatus
    origin: IncidentOrigin
    branch: str
    created_at: str
    updated_at: str
    legacy_id: Optional[str] = None
