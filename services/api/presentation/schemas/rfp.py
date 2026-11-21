"""Pydantic presentation schemas for RFP Intake API matching OpenAPI contract."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Sanitized error envelope."""

    model_config = ConfigDict(extra="ignore")
    detail: str = Field(..., description="Sanitized human-readable error description")


class IntakeTicketAcceptedResponse(BaseModel):
    """Immediate response returned upon successful PDF ingestion (HTTP 202)."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    ticket_number: str
    status: Literal["analizando", "descartado", "analisis_completo"]
    message: str
    created_at: datetime


class IntakeTicketSummary(BaseModel):
    """Compact summary of an intake ticket for list views."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    ticket_number: str
    status: Literal["analizando", "descartado", "analisis_completo"]
    raw_pdf_filename: str
    client_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IntakeTicketListResponse(BaseModel):
    """Paginated list wrapper for ticket summaries."""

    items: List[IntakeTicketSummary]
    total: int


class ReadabilityScoresResponse(BaseModel):
    """Embedded readability scores and statistics."""

    model_config = ConfigDict(from_attributes=True)

    flesch_reading_ease: float
    flesch_kincaid_grade: float
    reading_level_label: str
    word_count: int
    sentence_count: int


class RFPMetadataResponse(BaseModel):
    """Extracted commercial metadata."""

    model_config = ConfigDict(from_attributes=True)

    client_name: str
    client_country: Literal["US", "ES"]
    currency: Literal["USD", "EUR"]
    services_requested: List[str]
    monthly_volume: Optional[int] = None
    deadline: Optional[str] = None
    budget_range: Optional[str] = None
    departments_needed: List[str]
    unsupported_services: List[str]
    readability_scores: ReadabilityScoresResponse


class DepartmentSectionResponse(BaseModel):
    """Analysis results from a specific department worker."""

    model_config = ConfigDict(from_attributes=True)

    department_id: Literal["warehouse", "lastmile", "reverse"]
    department_name: str
    responsible_person: str
    key_aspects: Dict[str, Any]
    open_questions: List[str]
    policy_warnings: List[str]


class InternalContact(BaseModel):
    """Recommended internal stakeholder contact."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    role: str
    department: str


class IntakeHandoffPayloadResponse(BaseModel):
    """Canonical Part 2 proposal generation handoff payload."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    schema_version: str = "1.0.0"
    executive_summary: str
    flagged_contradictions: List[str]
    key_questions_for_prospect: List[str]
    internal_contacts: List[InternalContact]
    full_handoff_json: Dict[str, Any]
    created_at: datetime


class IntakeTicketDetailResponse(BaseModel):
    """Comprehensive ticket response including metadata, sections, and handoff."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    ticket_number: str
    status: Literal["analizando", "descartado", "analisis_completo"]
    raw_pdf_filename: str
    file_size_bytes: int
    rejection_reason: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[RFPMetadataResponse] = None
    department_sections: List[DepartmentSectionResponse] = Field(default_factory=list)
    handoff: Optional[IntakeHandoffPayloadResponse] = None
    created_at: datetime
    updated_at: datetime
