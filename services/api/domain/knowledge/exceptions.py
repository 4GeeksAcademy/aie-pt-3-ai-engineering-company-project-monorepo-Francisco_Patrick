"""Domain exceptions for the TrackFlow RAG & Knowledge Base domain."""

from domain.common.exceptions import DomainException


class KnowledgeBaseException(DomainException):
    """Base exception for knowledge base domain operations."""

    def __init__(self, message: str = "A knowledge base operation failed.") -> None:
        """Initialize knowledge base exception."""
        super().__init__(message)


class KnowledgeBaseUnavailableException(KnowledgeBaseException):
    """Raised when the vector store or embedding engine is unreachable or degraded."""

    def __init__(
        self,
        message: str = "Knowledge base vector service is temporarily unavailable.",
    ) -> None:
        """Initialize unavailable exception."""
        super().__init__(message)


class IngestionException(KnowledgeBaseException):
    """Raised when document parsing, chunking, or vector indexing fails."""

    def __init__(
        self,
        message: str = "Failed to ingest knowledge base document.",
    ) -> None:
        """Initialize ingestion exception."""
        super().__init__(message)
