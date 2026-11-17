"""Abstract port interfaces for the TrackFlow RAG & Knowledge Base domain.

Adheres strictly to Hexagonal Architecture and Monorepo Constitution Principle VII,
isolating the domain core from Qdrant SDK, embedding models, and LLM engines.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from domain.knowledge.entities import (
    KnowledgeChunk,
    RetrievedContext,
)


class VectorStorePort(ABC):
    """Port interface for vector database persistence and semantic similarity search."""

    @abstractmethod
    def ensure_collection(self) -> None:
        """Ensure the canonical Qdrant collection exists with required schema and indexes."""

    @abstractmethod
    def upsert_chunks(self, chunks: List[KnowledgeChunk]) -> Dict[str, int]:
        """Idempotently upsert embedded knowledge chunks into the vector store.

        Args:
            chunks: List of KnowledgeChunk instances with populated vectors.

        Returns:
            Dictionary with keys 'added', 'updated', and 'total'.
        """

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 3,
        language: Optional[str] = None,
    ) -> List[RetrievedContext]:
        """Perform semantic cosine similarity search against indexed chunks.

        Args:
            query_vector: Dense embedding vector for the user query.
            top_k: Maximum number of top results to return.
            language: Optional language filter.

        Returns:
            List of RetrievedContext sorted descending by similarity_score.
        """

    @abstractmethod
    def get_health_status(self) -> Dict[str, Any]:
        """Retrieve collection health status and indexed point count.

        Returns:
            Dictionary containing status, collection_name, indexed_points_count, and vector_dimensions.
        """


class EmbeddingServicePort(ABC):
    """Port interface for text embedding generation."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate dense vector embeddings for a batch of document texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of 384-dimensional float vectors.
        """

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Generate a dense vector embedding for a single user query.

        Args:
            text: Natural language query string.

        Returns:
            384-dimensional float vector.
        """


class LLMGenerationPort(ABC):
    """Port interface for grounded natural-language answer synthesis."""

    @abstractmethod
    def generate_grounded_answer(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
    ) -> str:
        """Synthesize a grounded response in the TrackFlow sales persona from retrieved contexts.

        Args:
            query: User's natural language question.
            contexts: Threshold-cleared RetrievedContext chunks.
            language: Desired response language code.

        Returns:
            Grounded natural-language answer adhering to corporate guardrails.
        """
