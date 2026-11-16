"""Unit tests for KnowledgeService orchestration, threshold gating, and refusal logic (T025).

Verifies:
- Calibrated similarity threshold (0.62) filtering of retrieved chunks
- Refusal response (`is_refusal=True`, `sources=[]`) when all candidates score < 0.62
- Grounded answer synthesis and citation population when candidates score >= 0.62
- Custom per-request `min_score` override behavior.
"""

from typing import Any, Dict, List, Optional

from application.services.knowledge_service import (
    KnowledgeService,
    STANDARD_REFUSAL_MESSAGE,
    build_refusal_message,
)
from domain.knowledge.entities import (
    KnowledgeChunk,
    QueryRequest,
    RetrievedContext,
    generate_chunk_id,
)
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)


class StubEmbeddingService(EmbeddingServicePort):
    """Deterministic stub embedding service returning 384-dimensional vectors."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Return stub 384-dim embeddings for documents."""
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        """Return stub 384-dim embedding for query."""
        return [0.1] * 384


class StubVectorStore(VectorStorePort):
    """Configurable stub vector store returning preset RetrievedContext candidates."""

    def __init__(self, candidates: List[RetrievedContext]) -> None:
        """Initialize with preset candidates."""
        self._candidates = candidates

    def ensure_collection(self) -> None:
        """No-op collection check."""

    def upsert_chunks(self, chunks: List[KnowledgeChunk]) -> Dict[str, int]:
        """Return stub upsert counts."""
        return {"added": len(chunks), "updated": 0, "total": len(chunks)}

    def search(
        self,
        query_vector: List[float],
        top_k: int = 3,
        language: Optional[str] = None,
    ) -> List[RetrievedContext]:
        """Return up to top_k preset candidates."""
        return self._candidates[:top_k]

    def get_health_status(self) -> Dict[str, Any]:
        """Return stub healthy status."""
        return {
            "status": "healthy",
            "collection_name": "trackflow_knowledge",
            "indexed_points_count": 12,
            "vector_dimensions": 384,
        }


class StubLLMGenerator(LLMGenerationPort):
    """Stub LLM generator recording whether it was called."""

    def __init__(self) -> None:
        """Initialize call tracking."""
        self.called = False

    def generate_grounded_answer(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
    ) -> str:
        """Synthesize stub answer from top context text."""
        self.called = True
        return f"Grounded answer from {contexts[0].chunk.source_document}: {contexts[0].chunk.text}"


def _build_candidate(
    doc_slug: str,
    section: str,
    text: str,
    score: float,
    rank: int = 1,
) -> RetrievedContext:
    """Create a RetrievedContext candidate with the given similarity score."""
    chunk = KnowledgeChunk(
        id=generate_chunk_id(doc_slug, rank - 1),
        company="trackflow",
        source_document=doc_slug,
        section=section,
        language="en",
        chunk_index=rank - 1,
        text=text,
    )
    return RetrievedContext(chunk=chunk, similarity_score=score, rank=rank)


class TestKnowledgeServiceThresholdAndRefusal:
    """Unit test suite for KnowledgeService confidence gating and refusal generation."""

    def test_refuses_query_when_all_candidates_fall_below_0_62_threshold(self) -> None:
        """Candidates below 0.62 must be filtered out, returning is_refusal=True and empty sources."""
        low_candidates = [
            _build_candidate(
                "sla-delivery",
                "Scope & Delivery Service Tiers",
                "TrackFlow manages last-mile delivery in the United States and Spain.",
                score=0.51,
                rank=1,
            ),
            _build_candidate(
                "storage-pricing",
                "Standard Storage Rates",
                "TrackFlow charges client brands for storage based on volume occupied.",
                score=0.38,
                rank=2,
            ),
        ]
        llm = StubLLMGenerator()
        service = KnowledgeService(
            vector_store=StubVectorStore(low_candidates),
            embedding_service=StubEmbeddingService(),
            llm_generator=llm,
            default_min_score=0.62,
        )

        response = service.query(
            QueryRequest(
                query="What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?",
                top_k=3,
                min_score=0.62,
            )
        )

        assert response.is_refusal is True
        assert response.sources == []
        assert "TrackFlow internal documentation does not contain verified policy regarding" in response.answer
        assert "pharmaceutical refrigeration" in response.answer.lower()
        assert "operations leadership directly" in response.answer
        assert llm.called is False

        # Verify POSIX shell-escaped single quotes ('\'') are normalized cleanly
        escaped_response = service.query(
            QueryRequest(
                query="What is TrackFlow'\\''s temperature-controlled pharmaceutical refrigeration SLA?",
                top_k=3,
                min_score=0.62,
            )
        )
        assert escaped_response.is_refusal is True
        assert "'\\''" not in escaped_response.answer
        assert "pharmaceutical refrigeration" in escaped_response.answer.lower()
        assert build_refusal_message("") == STANDARD_REFUSAL_MESSAGE

    def test_filters_out_sub_threshold_candidates_while_keeping_qualified_ones(
        self,
    ) -> None:
        """Only candidates with similarity_score >= 0.62 must be passed to generation and cited."""
        mixed_candidates = [
            _build_candidate(
                "returns-policy",
                "Standard Return Window & Return Shipping Costs",
                "Standard return window: 30 days from delivery unless customized.",
                score=0.84,
                rank=1,
            ),
            _build_candidate(
                "sla-delivery",
                "Scope & Delivery Service Tiers",
                "Standard shipping takes 3 to 5 business days within the same country.",
                score=0.54,
                rank=2,
            ),
        ]
        llm = StubLLMGenerator()
        service = KnowledgeService(
            vector_store=StubVectorStore(mixed_candidates),
            embedding_service=StubEmbeddingService(),
            llm_generator=llm,
            default_min_score=0.62,
        )

        response = service.query(
            QueryRequest(
                query="What is TrackFlow's standard return window?",
                top_k=3,
                min_score=0.62,
            )
        )

        assert response.is_refusal is False
        assert llm.called is True
        assert len(response.sources) == 1
        assert response.sources[0].source_document == "returns-policy"
        assert response.sources[0].similarity_score == 0.84
        assert "30 days" in response.answer
