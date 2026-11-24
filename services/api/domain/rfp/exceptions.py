"""Domain exceptions for the RFP Intake & Analysis domain."""

from domain.common.exceptions import DomainException


class RFPException(DomainException):
    """Base exception for all RFP intake domain errors."""

    def __init__(self, message: str = "An RFP intake operation failed.") -> None:
        """Initialize RFP exception."""
        super().__init__(message)


class NonRFPError(RFPException):
    """Raised when an ingested document is classified as a non-RFP (e.g. carrier rate pitch, spam)."""

    def __init__(self, reason: str = "Document is not a customer RFP proposal.") -> None:
        """Initialize NonRFPError with specific rejection reason."""
        super().__init__(f"Rejected proposal: {reason}")
        self.reason = reason


class DocumentParseError(RFPException):
    """Raised when a document cannot be parsed or converted into markdown."""

    def __init__(self, message: str = "Failed to parse proposal document.") -> None:
        """Initialize DocumentParseError."""
        super().__init__(message)


class TicketNotFoundError(RFPException):
    """Raised when a requested intake ticket is not found."""

    def __init__(self, ticket_id: str) -> None:
        """Initialize TicketNotFoundError."""
        super().__init__(f"Intake ticket '{ticket_id}' not found.")
        self.ticket_id = ticket_id
