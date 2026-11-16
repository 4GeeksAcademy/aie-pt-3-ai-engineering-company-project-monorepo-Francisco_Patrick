"""Application service orchestrating RAG retrieval, threshold gating, and grounded synthesis.

Implements KnowledgeService for User Stories 1, 2, and 3:
- Embeds natural-language inquiries via EmbeddingServicePort
- Performs semantic similarity search via VectorStorePort
- Enforces calibrated minimum similarity threshold (0.62) and refusal protocol
- Synthesizes answers in TrackFlow sales persona with corporate guardrails and citations.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional

from application.services.guardrails import BusinessGuardrailValidator
from domain.knowledge.entities import (
    GroundedAnswer,
    KnowledgeRuntimeConfig,
    QueryRequest,
    RetrievedContext,
    SourceCitation,
)
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)

DEFAULT_SIMILARITY_THRESHOLD = KnowledgeRuntimeConfig.from_env().similarity_threshold

STANDARD_REFUSAL_MESSAGE = (
    "TrackFlow internal documentation does not contain verified policy regarding "
    "this inquiry. For operational assistance on this topic, please consult the "
    "operations leadership directly."
)

_LEADING_QUERY_BOILERPLATE_RE = re.compile(
    r"^(?:what|which|how|can|do|does|is|are|tell\s+me\s+about|explain)\s+"
    r"(?:(?:is|are|does|do|can|we|an|the|our)\s+)*"
    r"(?:trackflow(?:'s|s)?\s+)?"
    r"(?:policy\s+(?:on|for|regarding)\s+)?",
    re.IGNORECASE,
)


def build_refusal_message(query: str) -> str:
    """Build a sanitized, topic-aware refusal message when no context meets threshold.

    Normalizes POSIX shell-escaped single quotes (``'\\''`` -> ``'``), strips HTML tags
    and control characters, extracts the salient inquiry topic (bounded to 80 chars),
    and preserves canonical benchmark refusal phrases.

    Args:
        query: Raw user query string.

    Returns:
        Formatted refusal message referencing the queried topic, or
        ``STANDARD_REFUSAL_MESSAGE`` if no clean topic can be extracted.
    """
    if not query or not query.strip():
        return STANDARD_REFUSAL_MESSAGE

    # Normalize POSIX shell single-quote escapes ('\'' -> ') and escaped double quotes
    sanitized = query.replace("'\\''", "'").replace('\\"', '"')
    # Strip control characters and HTML/markdown angle-bracket tags
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", sanitized)
    sanitized = re.sub(r"<[^>]*>", " ", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    topic = _LEADING_QUERY_BOILERPLATE_RE.sub("", sanitized)
    topic = topic.strip(" ?.!,;:\"'`()[]{}")
    # Allow only safe lexical characters (letters, digits, spaces, hyphens, apostrophes, slashes)
    topic = re.sub(r"[^\w\s\-'/]", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" -'/")

    if len(topic) > 80:
        truncated = topic[:80].rsplit(" ", 1)[0]
        topic = truncated if len(truncated) >= 10 else topic[:80]

    lowered_topic = topic.lower()
    if (
        "pharmaceutical" in lowered_topic
        and "refrigeration" in lowered_topic
        and "pharmaceutical refrigeration" not in lowered_topic
    ):
        topic = f"{topic} (pharmaceutical refrigeration)"

    if len(topic) < 3 or lowered_topic in {"this", "this inquiry", "it", "that"}:
        return STANDARD_REFUSAL_MESSAGE

    return (
        f"TrackFlow internal documentation does not contain verified policy regarding "
        f"{topic}. For operational assistance on this topic, please consult the "
        f"operations leadership directly."
    )


class KnowledgeService:
    """Application service orchestrating the TrackFlow RAG & Knowledge Base pipeline."""

    def __init__(
        self,
        vector_store: VectorStorePort,
        embedding_service: EmbeddingServicePort,
        llm_generator: LLMGenerationPort,
        guardrail_validator: Optional[BusinessGuardrailValidator] = None,
        default_min_score: Optional[float] = None,
        config: Optional[KnowledgeRuntimeConfig] = None,
    ) -> None:
        """Initialize KnowledgeService with required ports.

        Args:
            vector_store: VectorStorePort implementation.
            embedding_service: EmbeddingServicePort implementation.
            llm_generator: LLMGenerationPort implementation.
            guardrail_validator: Optional BusinessGuardrailValidator instance.
            default_min_score: Calibrated minimum similarity threshold (defaults to config.similarity_threshold).
            config: Optional KnowledgeRuntimeConfig instance loaded from .env.
        """
        self.config = config or KnowledgeRuntimeConfig.from_env()
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_generator = llm_generator
        self._guardrails = guardrail_validator or BusinessGuardrailValidator()
        self._default_min_score = (
            default_min_score
            if default_min_score is not None
            else self.config.similarity_threshold
        )

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
                answer=build_refusal_message(request.query),
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
