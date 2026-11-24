"""Domain entities, value objects, and lifecycle models for RFP Intake & Analysis."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4


class TicketStatus(str, Enum):
    """Lifecycle status states for an intake ticket."""

    ANALIZANDO = "analizando"
    DESCARTADO = "descartado"
    ANALISIS_COMPLETO = "analisis_completo"


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


@dataclass(frozen=True)
class DepartmentSection:
    """Department-specific operational evaluation and open questions."""

    id: UUID
    ticket_id: UUID
    department_id: Literal["warehouse", "lastmile", "reverse"]
    department_name: str
    responsible_person: str
    key_aspects: Dict[str, Any]
    open_questions: List[str]
    policy_warnings: List[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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


@dataclass
class IntakeTicket:
    """Root aggregate representing an uploaded RFP proposal and its analysis state."""

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
        # Generate default ticket number if not provided
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
        """Mark ticket as successfully analyzed."""
        self.status = TicketStatus.ANALISIS_COMPLETO
        self.updated_at = datetime.now(timezone.utc)
