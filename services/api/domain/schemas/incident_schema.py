from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
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

class IncidentStatusUpdateSchema(BaseModel):
    status: IncidentStatus = Field(..., description="New status: open, in_progress, resolved, discarded")

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

class IncidentSummaryResponse(BaseModel):
    total_incidents: int
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    by_origin: Dict[str, int]
    by_branch: Dict[str, int]

class InvalidRecordDetail(BaseModel):
    row: int
    id: str
    reason: str

class IncidentMetrics(BaseModel):
    total_processed: int
    valid_records: int
    invalid_records: int
    category_breakdown: Dict[str, int]
    status_breakdown: Dict[str, int]
    average_satisfaction_index: float

class IncidentDiagnostics(BaseModel):
    invalid_sample: List[InvalidRecordDetail]

class IncidentAnalysisResponse(BaseModel):
    metrics: IncidentMetrics
    diagnostics: IncidentDiagnostics
