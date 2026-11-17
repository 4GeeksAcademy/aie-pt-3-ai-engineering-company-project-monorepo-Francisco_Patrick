"""FastAPI presentation router for TrackFlow Knowledge Base & RAG endpoints.

Adheres strictly to Monorepo Constitution Principle II:
- Explicit Pydantic `response_model` on all routes
- Dependency injection via FastAPI `Depends`
- Non-blocking execution via `run_in_threadpool`
- Zero internal vector or Qdrant primitives leaked across HTTP boundaries.
"""

from fastapi import APIRouter, Depends, status
from fastapi.concurrency import run_in_threadpool

from application.services.knowledge_service import KnowledgeService
from domain.knowledge.entities import QueryRequest
from presentation.dependencies import get_knowledge_service_dep
from presentation.schemas.knowledge import (
    KnowledgeHealthResponseSchema,
    KnowledgeQueryRequestSchema,
    KnowledgeQueryResponseSchema,
    KnowledgeSourceCitationSchema,
)

router = APIRouter(tags=["Knowledge"])


@router.post(
    "/query",
    response_model=KnowledgeQueryResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Submit a natural-language query to the TrackFlow corporate knowledge base",
)
async def query_knowledge(
    payload: KnowledgeQueryRequestSchema,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service_dep),
) -> KnowledgeQueryResponseSchema:
    """Process a natural-language policy question and return a grounded answer with citations."""
    domain_request = QueryRequest(
        query=payload.query,
        language=payload.language or "en",
        top_k=payload.top_k,
        min_score=payload.min_score if payload.min_score is not None else 0.62,
    )
    grounded_answer = await run_in_threadpool(knowledge_service.query, domain_request)

    return KnowledgeQueryResponseSchema(
        query=grounded_answer.query,
        answer=grounded_answer.answer,
        is_refusal=grounded_answer.is_refusal,
        sources=[
            KnowledgeSourceCitationSchema(
                source_document=src.source_document,
                section=src.section,
                similarity_score=src.similarity_score,
            )
            for src in grounded_answer.sources
        ],
        execution_time_ms=grounded_answer.execution_time_ms,
    )


@router.get(
    "/health",
    response_model=KnowledgeHealthResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Health and collection status check for Qdrant knowledge index",
)
async def get_health(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service_dep),
) -> KnowledgeHealthResponseSchema:
    """Inspect operational health and indexed point count of the Qdrant knowledge base."""
    health_data = await run_in_threadpool(knowledge_service.get_health)
    return KnowledgeHealthResponseSchema(
        status=str(health_data["status"]),
        collection_name=str(health_data["collection_name"]),
        indexed_points_count=int(health_data["indexed_points_count"]),
        vector_dimensions=int(health_data["vector_dimensions"]),
    )
