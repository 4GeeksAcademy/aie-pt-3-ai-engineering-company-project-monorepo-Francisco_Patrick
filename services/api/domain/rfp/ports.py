"""Domain ports (interfaces) for RFP Intake, Proposal Generation & Analysis."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from domain.rfp.entities import (
    DepartmentSection,
    EvaluationResult,
    IntakeHandoffPayload,
    IntakeTicket,
    Part3HandoffPayload,
    ReadabilityScores,
    RFPMetadata,
    TicketStatus,
)


class IntakeTicketRepositoryPort(ABC):
    """Port for persisting and retrieving RFP intake tickets, drafts, evaluations, and handoffs."""

    @abstractmethod
    def save_ticket(self, ticket: IntakeTicket) -> IntakeTicket:
        """Persist or update an intake ticket."""
        pass

    @abstractmethod
    def get_ticket(self, ticket_id: UUID) -> Optional[IntakeTicket]:
        """Retrieve an intake ticket by UUID."""
        pass

    @abstractmethod
    def get_ticket_by_number(self, ticket_number: str) -> Optional[IntakeTicket]:
        """Retrieve an intake ticket by human-readable reference code."""
        pass

    @abstractmethod
    def list_tickets(
        self, limit: int = 20, status: Optional[TicketStatus] = None
    ) -> List[IntakeTicket]:
        """List recent intake tickets optionally filtered by status."""
        pass

    @abstractmethod
    def count_tickets(self, status: Optional[TicketStatus] = None) -> int:
        """Count total intake tickets optionally filtered by status."""
        pass

    @abstractmethod
    def save_metadata(self, metadata: RFPMetadata) -> RFPMetadata:
        """Persist or update extracted commercial metadata for a ticket."""
        pass

    @abstractmethod
    def get_metadata(self, ticket_id: UUID) -> Optional[RFPMetadata]:
        """Retrieve extracted commercial metadata for a ticket."""
        pass

    @abstractmethod
    def save_department_section(self, section: DepartmentSection) -> DepartmentSection:
        """Persist or update a department analysis section."""
        pass

    @abstractmethod
    def get_department_section(
        self, ticket_id: UUID, department_id: str
    ) -> Optional[DepartmentSection]:
        """Retrieve a specific department section by ticket_id and department_id."""
        pass

    @abstractmethod
    def update_department_section_draft(
        self,
        ticket_id: UUID,
        department_id: str,
        draft_content: Optional[str],
        iteration: int,
        status: str,
        evaluation_result: Optional[EvaluationResult] = None,
    ) -> Optional[DepartmentSection]:
        """Update draft content, iteration counter, status, and evaluation history for a department section."""
        pass

    @abstractmethod
    def list_department_sections(self, ticket_id: UUID) -> List[DepartmentSection]:
        """List all department analysis sections for a ticket."""
        pass

    @abstractmethod
    def save_handoff_payload(self, payload: IntakeHandoffPayload) -> IntakeHandoffPayload:
        """Persist or update the Part 2 handoff payload."""
        pass

    @abstractmethod
    def get_handoff_payload(self, ticket_id: UUID) -> Optional[IntakeHandoffPayload]:
        """Retrieve the canonical Part 2 handoff payload for a ticket."""
        pass

    @abstractmethod
    def save_part3_handoff_payload(self, payload: Part3HandoffPayload) -> Part3HandoffPayload:
        """Persist or update the canonical Part 3 handoff payload."""
        pass

    @abstractmethod
    def get_part3_handoff_payload(self, ticket_id: UUID) -> Optional[Part3HandoffPayload]:
        """Retrieve the canonical Part 3 handoff payload for a ticket."""
        pass


class DocumentConverterPort(ABC):
    """Port for converting raw binary documents (e.g. PDF) into structured Markdown."""

    @abstractmethod
    def convert_to_markdown(self, file_path: str) -> str:
        """Extract text content and format as structured Markdown."""
        pass


class ReadabilityCalculatorPort(ABC):
    """Port for computing readability metrics from text."""

    @abstractmethod
    def calculate_scores(self, text: str) -> ReadabilityScores:
        """Compute readability ease, grade level, and text statistics."""
        pass
