"""Pydantic presentation schemas for RFP Intake & Response Generation API matching OpenAPI contracts."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


TicketStatusLiteral = Literal[
    "analizando",
    "descartado",
    "analisis_completo",
    "generando_borrador",
    "en_evaluación",
    "needs_human_review",
]


class ErrorResponse(BaseModel):
    """Sanitized error envelope."""

    model_config = ConfigDict(extra="ignore")
    detail: str = Field(..., description="Sanitized human-readable error description")


class IntakeTicketAcceptedResponse(BaseModel):
    """Immediate response returned upon successful PDF ingestion (HTTP 202)."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    ticket_number: str
    status: TicketStatusLiteral
    message: str
    created_at: datetime


class ProposalGenerationAcceptedResponse(BaseModel):
    """Immediate response returned when initiating Part 2 proposal generation (HTTP 202)."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    status: str = Field(default="generando_borrador")
    message: str
    active_departments: List[Literal["warehouse", "lastmile", "reverse"]]


class IntakeTicketSummary(BaseModel):
    """Compact summary of an intake ticket for list views."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    ticket_number: str
    status: TicketStatusLiteral
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


class ReadabilityEvaluationSchema(BaseModel):
    """Readability dimension evaluation outcome."""

    model_config = ConfigDict(from_attributes=True)

    pass_status: bool
    score: float
    details: str


class RelevanceEvaluationSchema(BaseModel):
    """Relevance dimension evaluation outcome."""

    model_config = ConfigDict(from_attributes=True)

    pass_status: bool
    missing_aspects: List[str] = Field(default_factory=list)


class ComplianceEvaluationSchema(BaseModel):
    """Compliance dimension evaluation outcome."""

    model_config = ConfigDict(from_attributes=True)

    pass_status: bool
    rule_ids: List[str] = Field(default_factory=list)
    violations: List[str] = Field(default_factory=list)


class EvaluationResultSchema(BaseModel):
    """Structured multi-dimensional evaluation result for a department section draft."""

    model_config = ConfigDict(from_attributes=True)

    department_id: Literal["warehouse", "lastmile", "reverse"]
    iteration: int
    readability: ReadabilityEvaluationSchema
    relevance: RelevanceEvaluationSchema
    compliance: ComplianceEvaluationSchema
    overall_pass: bool
    feedback_for_generator: str
    evaluated_at: datetime


class DepartmentSectionResponse(BaseModel):
    """Analysis and proposal draft results for a specific department."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[UUID] = None
    ticket_id: Optional[UUID] = None
    department_id: Literal["warehouse", "lastmile", "reverse"]
    department_name: str
    responsible_person: str
    key_aspects: Dict[str, Any] = Field(default_factory=dict)
    open_questions: List[str] = Field(default_factory=list)
    policy_warnings: List[str] = Field(default_factory=list)
    status: str = "pending"
    iteration: int = 0
    draft_content: Optional[str] = None
    latest_evaluation: Optional[EvaluationResultSchema] = None
    evaluation_results: List[EvaluationResultSchema] = Field(default_factory=list)


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


class Part3DepartmentSectionBundleSchema(BaseModel):
    """Per-department finalized draft and evaluation bundle for Part 3 handoff."""

    model_config = ConfigDict(from_attributes=True)

    draft_content: str
    status: Literal["passed", "needs_human_review"]
    iteration: int
    evaluation_result: EvaluationResultSchema


class Part3HandoffPayloadResponse(BaseModel):
    """Canonical Part 3 proposal approval handoff payload."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    schema_version: str = "2.0.0"
    overall_status: Literal["passed", "needs_human_review"]
    rfp_metadata: Dict[str, Any]
    department_sections: Dict[str, Part3DepartmentSectionBundleSchema]
    emitted_at: datetime


class IntakeTicketDetailResponse(BaseModel):
    """Comprehensive ticket response including metadata, sections, and handoff."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    ticket_number: str
    status: TicketStatusLiteral
    raw_pdf_filename: str
    file_size_bytes: int
    rejection_reason: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[RFPMetadataResponse] = None
    department_sections: List[DepartmentSectionResponse] = Field(default_factory=list)
    handoff: Optional[IntakeHandoffPayloadResponse] = None
    created_at: datetime
    updated_at: datetime
