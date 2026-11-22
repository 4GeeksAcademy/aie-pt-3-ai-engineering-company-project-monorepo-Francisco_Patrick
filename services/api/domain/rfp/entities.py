"""Domain entities, value objects, and lifecycle models for RFP Intake & Response Generation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TicketStatus(str, Enum):
    """Lifecycle status states for an RFP ticket across Part 1 and Part 2."""

    ANALIZANDO = "analizando"
    DESCARTADO = "descartado"
    ANALISIS_COMPLETO = "analisis_completo"
    # Part 2 proposal generation & evaluation statuses
    DRAFTING = "generando_borrador"
    UNDER_EVALUATION = "en_evaluación"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


@dataclass(frozen=True)
class ReadabilityScores:
    """Readability and complexity metrics calculated from document content."""

    flesch_reading_ease: float
    flesch_kincaid_grade: float
    reading_level_label: str
    word_count: int
    sentence_count: int


@dataclass(frozen=True)
class InternalContact:
    """TrackFlow internal stakeholder assigned to support the proposal."""

    name: str
    role: str
    department: str


@dataclass(frozen=True)
class RFPMetadata:
    """Extracted commercial parameters and metadata for an RFP proposal."""

    id: UUID
    ticket_id: UUID
    client_name: str
    client_country: Literal["US", "ES"]
    currency: Literal["USD", "EUR"]
    services_requested: List[str]
    monthly_volume: Optional[int]
    deadline: Optional[str]
    budget_range: Optional[str]
    departments_needed: List[Literal["warehouse", "lastmile", "reverse"]]
    unsupported_services: List[str]
    readability_scores: ReadabilityScores
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ReadabilityEvaluation(BaseModel):
    """Readability evaluation outcome for a generated department proposal section."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    pass_status: bool = Field(..., description="Whether readability meets business thresholds")
    score: float = Field(..., description="Flesch Reading Ease score")
    details: str = Field(..., description="Qualitative readability assessment")

    def __getattr__(self, name: str) -> Any:
        if name == "pass":
            return self.pass_status
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class RelevanceEvaluation(BaseModel):
    """Relevance evaluation outcome checking coverage of Part 1 key_aspects."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    pass_status: bool = Field(..., description="Whether all required key aspects are covered")
    missing_aspects: List[str] = Field(
        default_factory=list, description="List of unaddressed key aspects"
    )

    def __getattr__(self, name: str) -> Any:
        if name == "pass":
            return self.pass_status
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class ComplianceEvaluation(BaseModel):
    """Compliance evaluation outcome verifying the 5 TrackFlow briefing rules (§5)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    pass_status: bool = Field(..., description="Whether all briefing compliance rules passed")
    rule_ids: List[str] = Field(
        default_factory=list, description="Identifiers of violated compliance rules"
    )
    violations: List[str] = Field(
        default_factory=list, description="Actionable descriptions of rule violations"
    )

    def __getattr__(self, name: str) -> Any:
        if name == "pass":
            return self.pass_status
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class EvaluationResult(BaseModel):
    """Immutable structured evaluation outcome emitted by parallel evaluators for a draft iteration."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    department_id: Literal["warehouse", "lastmile", "reverse"]
    iteration: int = Field(..., ge=1, le=3)
    readability: ReadabilityEvaluation
    relevance: RelevanceEvaluation
    compliance: ComplianceEvaluation
    overall_pass: bool
    feedback_for_generator: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_schema_dict(self) -> Dict[str, Any]:
        """Serialize strictly to JSON-schema compliant dictionary."""
        return {
            "department_id": self.department_id,
            "iteration": self.iteration,
            "readability": {
                "pass_status": self.readability.pass_status,
                "score": self.readability.score,
                "details": self.readability.details,
            },
            "relevance": {
                "pass_status": self.relevance.pass_status,
                "missing_aspects": list(self.relevance.missing_aspects),
            },
            "compliance": {
                "pass_status": self.compliance.pass_status,
                "rule_ids": list(self.compliance.rule_ids),
                "violations": list(self.compliance.violations),
            },
            "overall_pass": self.overall_pass,
            "feedback_for_generator": self.feedback_for_generator,
            "evaluated_at": (
                self.evaluated_at.isoformat()
                if isinstance(self.evaluated_at, datetime)
                else str(self.evaluated_at)
            ),
        }


@dataclass(frozen=True)
class DepartmentSection:
    """Department-specific operational evaluation, generated draft, and evaluation history."""

    id: UUID
    ticket_id: UUID
    department_id: Literal["warehouse", "lastmile", "reverse"]
    department_name: str
    responsible_person: str
    key_aspects: Dict[str, Any]
    open_questions: List[str]
    policy_warnings: List[str]
    draft_content: Optional[str] = None
    iteration: int = 0
    status: str = "pending"
    evaluation_results: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class SalesSynthesis:
    """Consolidated sales briefing and policy cross-check results."""

    executive_summary: str
    flagged_contradictions: List[str]
    key_questions_for_prospect: List[str]
    internal_contacts: List[InternalContact]


@dataclass(frozen=True)
class IntakeHandoffPayload:
    """Canonical handoff payload committed for Part 2 proposal generation."""

    id: UUID
    ticket_id: UUID
    schema_version: str
    executive_summary: str
    flagged_contradictions: List[str]
    key_questions_for_prospect: List[str]
    internal_contacts: List[InternalContact]
    full_handoff_json: Dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Part3HandoffPayload:
    """Canonical handoff payload emitted at the end of Part 2 for Part 3 human approvals."""

    id: UUID
    ticket_id: UUID
    schema_version: str
    overall_status: Literal["passed", "needs_human_review"]
    rfp_metadata: Dict[str, Any]
    department_sections: Dict[str, Any]
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_schema_dict(self) -> Dict[str, Any]:
        """Serialize strictly to part3-handoff.schema.json dictionary."""
        return {
            "ticket_id": str(self.ticket_id),
            "schema_version": self.schema_version,
            "overall_status": self.overall_status,
            "rfp_metadata": dict(self.rfp_metadata),
            "department_sections": dict(self.department_sections),
            "emitted_at": (
                self.emitted_at.isoformat()
                if isinstance(self.emitted_at, datetime)
                else str(self.emitted_at)
            ),
        }


@dataclass
class IntakeTicket:
    """Root aggregate representing an uploaded RFP proposal and its lifecycle state."""

    id: UUID
    ticket_number: str
    status: TicketStatus
    raw_pdf_path: str
    raw_pdf_filename: str
    file_size_bytes: int
    rejection_reason: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        raw_pdf_path: str,
        raw_pdf_filename: str,
        file_size_bytes: int,
        ticket_number: Optional[str] = None,
        ticket_id: Optional[UUID] = None,
    ) -> "IntakeTicket":
        """Factory method to initialize a new ticket in ANALIZANDO state."""
        tid = ticket_id or uuid4()
        year = datetime.now(timezone.utc).year
        tnum = ticket_number or f"RFP-{year}-{str(tid.int)[:4]}"
        now = datetime.now(timezone.utc)
        return cls(
            id=tid,
            ticket_number=tnum,
            status=TicketStatus.ANALIZANDO,
            raw_pdf_path=raw_pdf_path,
            raw_pdf_filename=raw_pdf_filename,
            file_size_bytes=file_size_bytes,
            created_at=now,
            updated_at=now,
        )

    def mark_discarded(self, rejection_reason: str, error_message: Optional[str] = None) -> None:
        """Mark ticket as rejected/discarded."""
        self.status = TicketStatus.DESCARTADO
        self.rejection_reason = rejection_reason
        self.error_message = error_message
        self.updated_at = datetime.now(timezone.utc)

    def mark_complete(self) -> None:
        """Mark ticket as having completed Part 1 intake analysis."""
        self.status = TicketStatus.ANALISIS_COMPLETO
        self.updated_at = datetime.now(timezone.utc)

    def mark_drafting(self) -> None:
        """Transition ticket to Part 2 proposal drafting state (generando_borrador)."""
        self.status = TicketStatus.DRAFTING
        self.updated_at = datetime.now(timezone.utc)

    def mark_under_evaluation(self) -> None:
        """Transition ticket to Part 2 multi-dimensional evaluation state (en_evaluación)."""
        self.status = TicketStatus.UNDER_EVALUATION
        self.updated_at = datetime.now(timezone.utc)

    def mark_needs_human_review(self, error_message: Optional[str] = None) -> None:
        """Transition ticket to needs_human_review without discarding the ticket."""
        self.status = TicketStatus.NEEDS_HUMAN_REVIEW
        if error_message is not None:
            self.error_message = error_message
        self.updated_at = datetime.now(timezone.utc)
