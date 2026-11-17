"""TrackFlow RAG & Knowledge Base domain package."""

from domain.knowledge.entities import (
    GroundedAnswer,
    KnowledgeChunk,
    KnowledgeDocument,
    QueryRequest,
    RetrievedContext,
    SourceCitation,
    generate_chunk_id,
)
from domain.knowledge.exceptions import (
    IngestionException,
    KnowledgeBaseException,
    KnowledgeBaseUnavailableException,
)
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)

__all__ = [
    "EmbeddingServicePort",
    "GroundedAnswer",
    "IngestionException",
    "KnowledgeBaseException",
    "KnowledgeBaseUnavailableException",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "LLMGenerationPort",
    "QueryRequest",
    "RetrievedContext",
    "SourceCitation",
    "VectorStorePort",
    "generate_chunk_id",
]
