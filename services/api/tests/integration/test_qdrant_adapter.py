"""Integration tests for QdrantVectorStoreAdapter (T015).

Verifies:
- Collection creation with exact canonical name `trackflow_knowledge` and 384 dims
- Idempotent upsert using deterministic UUID v5 IDs (added vs updated counts)
- Semantic cosine similarity search returning ranked RetrievedContext objects
- Payload schema integrity (`company`, `source_document`, `section`, `language`, `chunk_index`, `text`)
- Health status reporting.
"""

import dataclasses
from pathlib import Path
import pytest

from application.services.chunking import MarkdownSemanticChunker
from domain.knowledge.exceptions import (
    IngestionException,
    KnowledgeBaseUnavailableException,
)
from infrastructure.adapters.embedding_adapter import FastEmbedAdapter
from infrastructure.adapters.qdrant_vector_store_adapter import (
    CANONICAL_COLLECTION_NAME,
    QdrantVectorStoreAdapter,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_BASE_DIR = REPO_ROOT / "docs" / "company-knowledge-base"


class TestQdrantVectorStoreAdapterIntegration:
    """Integration test suite for QdrantVectorStoreAdapter in :memory: mode."""

    def test_ensure_collection_and_idempotent_upsert(self) -> None:
        """Upserting the 12 canonical chunks twice must add 12 on first run and update 12 on second."""
        adapter = QdrantVectorStoreAdapter(location=":memory:")
        embedder = FastEmbedAdapter()
        chunker = MarkdownSemanticChunker()

        adapter.ensure_collection()
        initial_health = adapter.get_health_status()
        assert initial_health["collection_name"] == CANONICAL_COLLECTION_NAME
        assert initial_health["indexed_points_count"] == 0
        assert initial_health["status"] == "degraded"

        _, raw_chunks = chunker.load_and_chunk_directory(KNOWLEDGE_BASE_DIR)
        vectors = embedder.embed_documents([c.text for c in raw_chunks])
        embedded_chunks = [
            dataclasses.replace(c, vector=v) for c, v in zip(raw_chunks, vectors)
        ]

        first_stats = adapter.upsert_chunks(embedded_chunks)
        assert first_stats == {"added": 12, "updated": 0, "total": 12}

        second_stats = adapter.upsert_chunks(embedded_chunks)
        assert second_stats == {"added": 0, "updated": 12, "total": 12}

        final_health = adapter.get_health_status()
        assert final_health["status"] == "healthy"
        assert final_health["indexed_points_count"] == 12
        assert final_health["vector_dimensions"] == 384

    def test_semantic_search_retrieves_expected_policy_chunks(self) -> None:
        """Semantic search must rank the matching policy chunk in top results."""
        adapter = QdrantVectorStoreAdapter(location=":memory:")
        embedder = FastEmbedAdapter()
        chunker = MarkdownSemanticChunker()

        _, raw_chunks = chunker.load_and_chunk_directory(KNOWLEDGE_BASE_DIR)
        vectors = embedder.embed_documents([c.text for c in raw_chunks])
        embedded_chunks = [
            dataclasses.replace(c, vector=v) for c, v in zip(raw_chunks, vectors)
        ]
        adapter.upsert_chunks(embedded_chunks)

        query_vec = embedder.embed_query(
            "What is TrackFlow's standard return window and who covers return shipping costs?"
        )
        results = adapter.search(query_vector=query_vec, top_k=3)

        assert len(results) == 3
        assert results[0].rank == 1
        assert results[0].chunk.source_document == "returns-policy"
        assert results[0].similarity_score >= 0.62
        assert "30 days" in results[0].chunk.text

    def test_rejects_chunk_with_missing_or_invalid_vector(self) -> None:
        """Upserting a chunk without a 384-dim vector must raise IngestionException."""
        adapter = QdrantVectorStoreAdapter(location=":memory:")
        chunker = MarkdownSemanticChunker()
        _, raw_chunks = chunker.load_and_chunk_directory(KNOWLEDGE_BASE_DIR)

        with pytest.raises(IngestionException):
            adapter.upsert_chunks([raw_chunks[0]])

        with pytest.raises(KnowledgeBaseUnavailableException):
            adapter.search(query_vector=[0.1, 0.2], top_k=3)
