"""Pydantic request and response schemas for TrackFlow Knowledge Base endpoints.

Conforms strictly to Monorepo Constitution Principle II (Public API Compatibility &
Strict Contract Serialization).
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class KnowledgeSourceCitationSchema(BaseModel):
    """Verifiable source document and section citation supporting a grounded answer."""

    source_document: str = Field(
        ..., description="Canonical source document slug (e.g. 'returns-policy')"
    )
    section: str = Field(..., description="Source section title or subtitle")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity score of the cited chunk"
    )


class KnowledgeQueryRequestSchema(BaseModel):
    """Request payload for natural-language inquiries against the TrackFlow knowledge base."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language inquiry string",
    )
    language: Optional[str] = Field(
        default="en", description="Target response language ISO code"
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of candidate chunks to retrieve",
    )
    min_score: Optional[float] = Field(
        default=0.62,
        ge=0.0,
        le=1.0,
        description="Minimum calibrated cosine similarity score threshold",
    )

    @field_validator("query")
    @classmethod
    def validate_non_whitespace_query(cls, value: str) -> str:
        """Ensure query is not empty or whitespace-only and has >= 3 characters after stripping."""
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError(
                "Query must contain at least 3 non-whitespace characters."
            )
        if len(stripped) > 1000:
            raise ValueError("Query must not exceed 1000 characters.")
        return stripped


class KnowledgeQueryResponseSchema(BaseModel):
    """Synthesized grounded response returned by POST /api/v1/knowledge/query."""

    query: str = Field(..., description="Echoed sanitized input query")
    answer: str = Field(
        ..., description="Grounded synthesized response in TrackFlow sales persona"
    )
    is_refusal: bool = Field(
        ...,
        description="Whether the inquiry was refused due to insufficient documentation or low confidence",
    )
    sources: List[KnowledgeSourceCitationSchema] = Field(
        default_factory=list,
        description="List of verifiable source citations used for answer synthesis",
    )
    execution_time_ms: float = Field(
        ..., ge=0.0, description="End-to-end processing time in milliseconds"
    )


class KnowledgeHealthResponseSchema(BaseModel):
    """Operational status and index metrics returned by GET /api/v1/knowledge/health."""

    status: str = Field(
        ..., description="Operational status: healthy, degraded, or unhealthy"
    )
    collection_name: str = Field(..., description="Active Qdrant collection name")
    indexed_points_count: int = Field(
        ..., ge=0, description="Total number of vector points indexed"
    )
    vector_dimensions: int = Field(
        ..., ge=1, description="Dimensionality of indexed vectors"
    )
