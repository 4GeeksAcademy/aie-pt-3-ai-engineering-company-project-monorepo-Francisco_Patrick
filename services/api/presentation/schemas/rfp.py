"""Pydantic presentation schemas for RFP Intake & Response Generation API matching OpenAPI contracts."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


TicketStatusLiteral = Literal[
    "analizando",
    "descartado",
    "analisis_completo",
    "generando_borrador",
    "en_evaluación",
    "needs_human_review",
    "esperando_aprobación",
    "terminado",
]

ApprovalStatusLiteral = Literal[
    "pending",
    "approved",
    "rejected",
    "changes_requested",
    "needs_human_review",
]

ApprovalDecisionLiteral = Literal["approve", "reject", "request_changes"]

ArbitrationTriggerLiteral = Literal[
    "volume-vs-capacity",
    "returns-sla-breach",
    "currency-mismatch",
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
    approval_status: str = "pending"
    approver: Optional[str] = None
    review_feedback: Optional[str] = None
    approved_at: Optional[datetime] = None


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


class ResumeDecisionRequest(BaseModel):
    """Request payload for resuming an interrupted department approval branch (Part 3)."""

    model_config = ConfigDict(extra="forbid")

    department_id: Literal["warehouse", "lastmile", "reverse"] = Field(
        ..., description="Department branch being resumed"
    )
    decision: ApprovalDecisionLiteral = Field(
        ..., description="Human reviewer operational decision"
    )
    approver: str = Field(
        ...,
        min_length=2,
        description="Name of responsible department lead (Ana Whitfield, Carlos Vega, Sofía Ramos)",
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Mandatory feedback if decision is 'request_changes'",
    )

    @model_validator(mode="after")
    def validate_feedback_for_changes(self) -> "ResumeDecisionRequest":
        """Enforce non-empty revision feedback when decision is 'request_changes'."""
        if self.decision == "request_changes":
            if not self.feedback or len(self.feedback.strip()) < 5:
                raise ValueError(
                    "Non-empty 'feedback' (minimum 5 characters) is mandatory when decision is 'request_changes'."
                )
        return self


class ResumeDecisionResponse(BaseModel):
    """Response payload returned after resuming an interrupted department approval branch."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: UUID
    department_id: Literal["warehouse", "lastmile", "reverse"]
    approval_status: ApprovalStatusLiteral
    ticket_status: Literal["esperando_aprobación", "terminado", "needs_human_review"]
    message: str
    approved_at: Optional[datetime] = None


class ArbitrationLogResponse(BaseModel):
    """Deterministic conflict arbitration log record schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    trigger_id: ArbitrationTriggerLiteral
    arbiter: str
    rule_applied: str
    resolution_details: Dict[str, Any]
    created_at: datetime


class ArbitrationLogListResponse(BaseModel):
    """List wrapper for ticket arbitration log records."""

    model_config = ConfigDict(from_attributes=True)

    items: List[ArbitrationLogResponse]
    total: int


class FinalDocumentResponse(BaseModel):
    """Consolidated final commercial proposal document response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    title: str
    client_name: str
    currency: Literal["USD", "EUR"]
    executive_summary: str
    sections: Dict[str, Any]
    generated_at: datetime


class IntakeTicketDetailResponse(BaseModel):
    """Comprehensive ticket response including metadata, sections, handoff, arbitration logs, and final document."""

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
    arbitration_logs: List[ArbitrationLogResponse] = Field(default_factory=list)
    final_document: Optional[FinalDocumentResponse] = None
    created_at: datetime
    updated_at: datetime
