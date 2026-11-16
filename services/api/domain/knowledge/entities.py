"""Domain entities and value objects for the TrackFlow RAG & Knowledge Base domain.

Defines immutable domain representations for corporate knowledge documents,
semantic chunks, query requests, retrieved contexts, and grounded answers.
"""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional


def generate_chunk_id(source_document: str, chunk_index: int) -> uuid.UUID:
    """Generate a deterministic RFC 4122 UUID v5 for a knowledge chunk.

    Args:
        source_document: Canonical source document slug (e.g. "sla-delivery").
        chunk_index: Zero-based ordinal index of the chunk within the document.

    Returns:
        Deterministic UUID v5 instance.
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"trackflow:{source_document}:{chunk_index}")


@dataclass(frozen=True)
class KnowledgeDocument:
    """Represents a canonical operational policy or service specification markdown file."""

    id: str
    title: str
    source_file: str
    language: str
    version: str
    raw_content: str
    sections: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnowledgeChunk:
    """An atomic, self-contained semantic segment of a KnowledgeDocument."""

    id: uuid.UUID
    company: str
    source_document: str
    section: str
    language: str
    chunk_index: int
    text: str
    vector: Optional[List[float]] = None

    def __post_init__(self) -> None:
        """Validate domain invariants for KnowledgeChunk."""
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be a non-negative integer (>= 0).")
        if not self.text or len(self.text.strip()) < 20:
            raise ValueError("chunk text must not be empty and must contain at least 20 characters.")
        if self.company != "trackflow":
            raise ValueError("company must be 'trackflow'.")


@dataclass(frozen=True)
class QueryRequest:
    """User inquiry submitted from frontline interfaces or API consumers."""

    query: str
    language: str = "en"
    top_k: int = 3
    min_score: float = 0.62

    def __post_init__(self) -> None:
        """Validate domain invariants for QueryRequest."""
        stripped = self.query.strip() if self.query else ""
        if len(stripped) < 3 or len(stripped) > 1000:
            raise ValueError("query stripped length must be between 3 and 1000 characters.")
        if self.top_k < 1 or self.top_k > 10:
            raise ValueError("top_k must be between 1 and 10.")
        if self.min_score < 0.0 or self.min_score > 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0.")


@dataclass(frozen=True)
class RetrievedContext:
    """Scored candidate chunk returned from semantic vector search."""

    chunk: KnowledgeChunk
    similarity_score: float
    rank: int


@dataclass(frozen=True)
class SourceCitation:
    """Verifiable source citation metadata included in a GroundedAnswer."""

    source_document: str
    section: str
    similarity_score: float


@dataclass(frozen=True)
class GroundedAnswer:
    """Final synthesized natural-language response delivered to the caller."""

    query: str
    answer: str
    is_refusal: bool
    sources: List[SourceCitation] = field(default_factory=list)
    execution_time_ms: float = 0.0
