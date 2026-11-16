"""Application service orchestrating RAG retrieval, threshold gating, and grounded synthesis.

Implements KnowledgeService for User Stories 1, 2, and 3:
- Embeds natural-language inquiries via EmbeddingServicePort
- Performs semantic similarity search via VectorStorePort
- Enforces calibrated minimum similarity threshold (0.62) and refusal protocol
- Synthesizes answers in TrackFlow sales persona with corporate guardrails and citations.
"""

import os
import time
from typing import Any, Dict, List, Optional

from application.services.guardrails import BusinessGuardrailValidator
from domain.knowledge.entities import (
    GroundedAnswer,
    QueryRequest,
    RetrievedContext,
    SourceCitation,
)
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)

DEFAULT_SIMILARITY_THRESHOLD = float(
    os.getenv("KNOWLEDGE_SIMILARITY_THRESHOLD", "0.62")
)

STANDARD_REFUSAL_MESSAGE = (
    "TrackFlow internal documentation does not contain verified policy regarding "
    "this inquiry. For operational assistance on this topic, please consult the "
    "operations leadership directly."
)


class KnowledgeService:
    """Application service orchestrating the TrackFlow RAG & Knowledge Base pipeline."""

    def __init__(
        self,
        vector_store: VectorStorePort,
        embedding_service: EmbeddingServicePort,
        llm_generator: LLMGenerationPort,
        guardrail_validator: Optional[BusinessGuardrailValidator] = None,
        default_min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        """Initialize KnowledgeService with required ports.

        Args:
            vector_store: VectorStorePort implementation.
            embedding_service: EmbeddingServicePort implementation.
            llm_generator: LLMGenerationPort implementation.
            guardrail_validator: Optional BusinessGuardrailValidator instance.
            default_min_score: Calibrated minimum similarity threshold (defaults to 0.62).
        """
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_generator = llm_generator
        self._guardrails = guardrail_validator or BusinessGuardrailValidator()
        self._default_min_score = default_min_score

    def query(self, request: QueryRequest) -> GroundedAnswer:
        """Process a natural-language policy query and return a grounded answer or refusal.

        Args:
            request: Validated QueryRequest domain object.

        Returns:
            GroundedAnswer containing synthesized answer, refusal flag, citations, and latency.
        """
        start_time = time.perf_counter()
        effective_threshold = (
            request.min_score
            if request.min_score is not None
            else self._default_min_score
        )

        query_vector = self._embedding_service.embed_query(request.query)
        raw_candidates = self._vector_store.search(
            query_vector=query_vector,
            top_k=request.top_k,
            language=None,
        )

        # Filter candidates strictly against calibrated minimum similarity score threshold
        qualified_contexts: List[RetrievedContext] = [
            ctx
            for ctx in raw_candidates
            if ctx.similarity_score >= effective_threshold
        ]

        if not qualified_contexts:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return GroundedAnswer(
                query=request.query,
                answer=STANDARD_REFUSAL_MESSAGE,
                is_refusal=True,
                sources=[],
                execution_time_ms=round(elapsed_ms, 2),
            )

        raw_answer = self._llm_generator.generate_grounded_answer(
            query=request.query,
            contexts=qualified_contexts,
            language=request.language,
        )
        enforced_answer = self._guardrails.enforce(
            query=request.query,
            answer=raw_answer,
            contexts=qualified_contexts,
        )

        citations: List[SourceCitation] = [
            SourceCitation(
                source_document=ctx.chunk.source_document,
                section=ctx.chunk.section,
                similarity_score=round(max(0.0, min(1.0, ctx.similarity_score)), 4),
            )
            for ctx in qualified_contexts
        ]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return GroundedAnswer(
            query=request.query,
            answer=enforced_answer,
            is_refusal=False,
            sources=citations,
            execution_time_ms=round(elapsed_ms, 2),
        )

    def get_health(self) -> Dict[str, Any]:
        """Return operational health status of the knowledge base vector store.

        Returns:
            Dictionary with status, collection_name, indexed_points_count, and vector_dimensions.
        """
        return self._vector_store.get_health_status()
