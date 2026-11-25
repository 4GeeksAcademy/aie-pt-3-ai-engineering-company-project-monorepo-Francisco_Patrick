"""Reusable RAG pipeline functions (`setup`, `embed`, `retrieve`, `generate_answer`, `query`).

Exposes the core TrackFlow RAG operations under `data/pipelines/` by delegating
directly to the canonical domain ports, adapters, and `KnowledgeService` in
`services/api/` without duplicating vector search, embedding, or guardrail logic.

Contract:
- `setup(...)`: Ensures the Qdrant `trackflow_knowledge` collection is ready.
- `embed(...)`: Generates dense 384-dim embeddings (and optionally indexes chunks).
- `retrieve(question, ...)`: Embeds `question`, queries Qdrant, and filters by `min_score` (0.62).
- `generate_answer(question, context, ...)`: Synthesizes a grounded answer and citations
  strictly from pre-retrieved `context` without re-invoking `retrieve()`.
- `query(question, context=None, ...)`: Runs the full RAG flow, or skips `retrieve()` when
  pre-retrieved `context` is supplied.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.services.guardrails import BusinessGuardrailValidator  # noqa: E402
from application.services.knowledge_service import (  # noqa: E402
    DEFAULT_SIMILARITY_THRESHOLD,
    KnowledgeService,
    build_refusal_message,
)
from domain.knowledge.entities import (  # noqa: E402
    GroundedAnswer,
    KnowledgeChunk,
    KnowledgeRuntimeConfig,
    QueryRequest,
    RetrievedContext,
    SourceCitation,
)
from domain.knowledge.ports import (  # noqa: E402
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)
from infrastructure.adapters.embedding_adapter import FastEmbedAdapter  # noqa: E402
from infrastructure.adapters.grounded_generation_adapter import (  # noqa: E402
    GroundedGenerationAdapter,
)
from infrastructure.adapters.qdrant_vector_store_adapter import (  # noqa: E402
    QdrantVectorStoreAdapter,
)


def setup(
    vector_store: Optional[VectorStorePort] = None,
    config: Optional[KnowledgeRuntimeConfig] = None,
) -> VectorStorePort:
    """Initialize and ensure the canonical `trackflow_knowledge` Qdrant collection exists.

    Args:
        vector_store: Optional existing VectorStorePort instance.
        config: Optional KnowledgeRuntimeConfig override.

    Returns:
        Configured VectorStorePort with its collection initialized.
    """
    active_config = config or KnowledgeRuntimeConfig.from_env()
    store = vector_store or QdrantVectorStoreAdapter(config=active_config)
    store.ensure_collection()
    return store


def embed(
    inputs: Union[str, Sequence[str], Sequence[KnowledgeChunk]],
    embedding_service: Optional[EmbeddingServicePort] = None,
    vector_store: Optional[VectorStorePort] = None,
    config: Optional[KnowledgeRuntimeConfig] = None,
) -> Union[List[float], List[List[float]], Dict[str, int]]:
    """Embed a query string, a batch of texts, or a sequence of KnowledgeChunk entities.

    When `inputs` is a sequence of `KnowledgeChunk` and `vector_store` is provided,
    embeds and idempotently upserts the chunks into the vector store.

    Args:
        inputs: Query string, list of text strings, or list of KnowledgeChunk objects.
        embedding_service: Optional EmbeddingServicePort adapter.
        vector_store: Optional VectorStorePort adapter for chunk indexing.
        config: Optional KnowledgeRuntimeConfig override.

    Returns:
        Single vector for a string input, list of vectors for string sequences,
        or upsert summary dictionary when indexing KnowledgeChunk objects into `vector_store`.
    """
    active_config = config or KnowledgeRuntimeConfig.from_env()
    embedder = embedding_service or FastEmbedAdapter(config=active_config)

    if isinstance(inputs, str):
        return embedder.embed_query(inputs)

    items = list(inputs)
    if not items:
        return []

    if isinstance(items[0], KnowledgeChunk):
        chunk_items: List[KnowledgeChunk] = [
            c for c in items if isinstance(c, KnowledgeChunk)
        ]
        vectors = embedder.embed_documents([c.text for c in chunk_items])
        if vector_store is not None:
            embedded_chunks = [
                dataclasses.replace(c, vector=v)
                for c, v in zip(chunk_items, vectors)
            ]
            vector_store.ensure_collection()
            return vector_store.upsert_chunks(embedded_chunks)
        return vectors

    str_items = [str(item) for item in items]
    return embedder.embed_documents(str_items)


def retrieve(
    question: str,
    vector_store: VectorStorePort,
    embedding_service: EmbeddingServicePort,
    top_k: int = 3,
    min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> List[RetrievedContext]:
    """Retrieve context chunks from the knowledge base qualifying under `min_score`.

    Reuses `EmbeddingServicePort` and `VectorStorePort` without duplicating vector search logic.

    Args:
        question: Sanitized user question.
        vector_store: VectorStorePort implementation.
        embedding_service: EmbeddingServicePort implementation.
        top_k: Maximum number of chunks to retrieve.
        min_score: Minimum cosine similarity threshold (defaults to 0.62).

    Returns:
        List of qualifying RetrievedContext chunks with `similarity_score >= min_score`.
    """
    query_vector = embedding_service.embed_query(question)
    candidates = vector_store.search(
        query_vector=query_vector,
        top_k=top_k,
        language=None,
    )
    return [ctx for ctx in candidates if ctx.similarity_score >= min_score]


def generate_answer(
    question: str,
    context: List[RetrievedContext],
    llm_generator: Optional[LLMGenerationPort] = None,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
    language: str = "en",
    config: Optional[KnowledgeRuntimeConfig] = None,
) -> Tuple[str, List[SourceCitation]]:
    """Generate a grounded answer and citations strictly from pre-retrieved context.

    This is the generation step separated from `query()`. It never invokes `retrieve()`.

    Args:
        question: User question string.
        context: Pre-retrieved list of qualifying RetrievedContext chunks.
        llm_generator: Optional LLMGenerationPort implementation.
        guardrail_validator: Optional BusinessGuardrailValidator instance.
        language: Target response language ISO code (defaults to 'en').
        config: Optional KnowledgeRuntimeConfig override.

    Returns:
        Tuple of `(enforced_answer, citations)`.
    """
    active_config = config or KnowledgeRuntimeConfig.from_env()
    validator = guardrail_validator or BusinessGuardrailValidator()
    generator = llm_generator or GroundedGenerationAdapter(
        guardrail_validator=validator,
        config=active_config,
    )

    raw_answer = generator.generate_grounded_answer(
        query=question,
        contexts=context,
        language=language,
    )
    enforced_answer = validator.enforce(
        query=question,
        answer=raw_answer,
        contexts=context,
    )
    citations: List[SourceCitation] = [
        SourceCitation(
            source_document=ctx.chunk.source_document,
            section=ctx.chunk.section,
            similarity_score=round(max(0.0, min(1.0, ctx.similarity_score)), 4),
        )
        for ctx in context
    ]
    return enforced_answer, citations


def build_citations_from_context(
    context: Sequence[RetrievedContext],
) -> List[SourceCitation]:
    """Build normalized SourceCitation records from pre-retrieved context chunks."""
    return [
        SourceCitation(
            source_document=ctx.chunk.source_document,
            section=ctx.chunk.section,
            similarity_score=round(max(0.0, min(1.0, ctx.similarity_score)), 4),
        )
        for ctx in context
    ]


def stream_generate_answer(
    question: str,
    context: List[RetrievedContext],
    llm_generator: Optional[LLMGenerationPort] = None,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
    language: str = "en",
    config: Optional[KnowledgeRuntimeConfig] = None,
    abort_event: Optional[Any] = None,
) -> Iterator[str]:
    """Stream grounded answer deltas progressively from pre-retrieved context with cooperative cancellation.

    Delegates to `llm_generator.stream_grounded_answer(...)` if supported, checking `abort_event`
    on every yielded delta so an interrupted turn immediately halts the underlying generation stream.
    """
    if abort_event is not None and hasattr(abort_event, "is_set") and abort_event.is_set():
        return

    active_config = config or KnowledgeRuntimeConfig.from_env()
    validator = guardrail_validator or BusinessGuardrailValidator()
    generator = llm_generator or GroundedGenerationAdapter(
        guardrail_validator=validator,
        config=active_config,
    )

    if hasattr(generator, "stream_grounded_answer"):
        for delta in generator.stream_grounded_answer(
            query=question,
            contexts=context,
            language=language,
            abort_event=abort_event,
        ):
            if abort_event is not None and hasattr(abort_event, "is_set") and abort_event.is_set():
                return
            if delta:
                yield delta
        return

    raw_answer = generator.generate_grounded_answer(
        query=question,
        contexts=context,
        language=language,
    )
    enforced_answer = validator.enforce(
        query=question,
        answer=raw_answer,
        contexts=context,
    )
    for delta in re.findall(r"\S+\s*|\s+", enforced_answer):
        if abort_event is not None and hasattr(abort_event, "is_set") and abort_event.is_set():
            return
        if delta:
            yield delta


def query(
    question: str,
    vector_store: VectorStorePort,
    embedding_service: EmbeddingServicePort,
    llm_generator: LLMGenerationPort,
    context: Optional[List[RetrievedContext]] = None,
    guardrail_validator: Optional[BusinessGuardrailValidator] = None,
    top_k: int = 3,
    min_score: float = DEFAULT_SIMILARITY_THRESHOLD,
    language: str = "en",
) -> GroundedAnswer:
    """Execute a RAG query, skipping internal `retrieve()` if `context` is already provided.

    Args:
        question: User question string.
        vector_store: VectorStorePort implementation.
        embedding_service: EmbeddingServicePort implementation.
        llm_generator: LLMGenerationPort implementation.
        context: Optional pre-retrieved context chunks; when provided, skips `retrieve()`.
        guardrail_validator: Optional BusinessGuardrailValidator instance.
        top_k: Maximum chunks to retrieve if `context` is not supplied.
        min_score: Calibrated cosine similarity threshold (0.62).
        language: Target response language ISO code.

    Returns:
        GroundedAnswer domain object.
    """
    service = KnowledgeService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        llm_generator=llm_generator,
        guardrail_validator=guardrail_validator,
        default_min_score=min_score,
    )
    return service.query(
        request=QueryRequest(
            query=question,
            top_k=top_k,
            min_score=min_score,
            language=language,
        ),
        contexts=context,
    )


__all__ = [
    "DEFAULT_SIMILARITY_THRESHOLD",
    "build_citations_from_context",
    "build_refusal_message",
    "embed",
    "generate_answer",
    "query",
    "retrieve",
    "setup",
    "stream_generate_answer",
]
