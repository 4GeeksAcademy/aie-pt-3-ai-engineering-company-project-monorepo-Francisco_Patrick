"""Qdrant vector database adapter for TrackFlow RAG & Knowledge Base.

Adheres strictly to Monorepo Constitution Principle VII:
- Encapsulates all qdrant-client SDK operations within infrastructure/adapters/
- Enforces canonical collection name `trackflow_knowledge` (384 dims, Cosine)
- Enforces strict payload schema (`company`, `source_document`, `section`, `language`, `chunk_index`, `text`)
- Supports deterministic UUID v5 idempotent upserts and graceful error handling.
"""

import logging
import os
import uuid
import warnings
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from domain.knowledge.entities import (
    KnowledgeChunk,
    KnowledgeRuntimeConfig,
    RetrievedContext,
)
from domain.knowledge.exceptions import (
    IngestionException,
    KnowledgeBaseUnavailableException,
)
from domain.knowledge.ports import VectorStorePort

logger = logging.getLogger(__name__)

CANONICAL_COLLECTION_NAME = "trackflow_knowledge"
DEFAULT_VECTOR_DIMENSIONS = 384


class QdrantVectorStoreAdapter(VectorStorePort):
    """Concrete Qdrant implementation of VectorStorePort."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        vector_dimensions: int = DEFAULT_VECTOR_DIMENSIONS,
        location: Optional[str] = None,
        url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        path: Optional[str] = None,
        timeout: float = 5.0,
        client: Optional[QdrantClient] = None,
        config: Optional[KnowledgeRuntimeConfig] = None,
    ) -> None:
        """Initialize the Qdrant vector store adapter.

        Args:
            collection_name: Qdrant collection name (defaults to config or 'trackflow_knowledge').
            vector_dimensions: Embedding vector dimensionality (defaults to 384).
            location: Optional Qdrant location (e.g. ':memory:').
            url: Optional Qdrant HTTP URL.
            host: Optional Qdrant hostname.
            port: Optional Qdrant port (defaults to 6333 when host is set).
            path: Optional local filesystem persistence path.
            timeout: Connection timeout in seconds.
            client: Optional pre-configured QdrantClient instance.
            config: Optional KnowledgeRuntimeConfig instance loaded from .env.
        """
        self.config = config or KnowledgeRuntimeConfig.from_env()
        self.collection_name = collection_name or self.config.qdrant_collection_name or CANONICAL_COLLECTION_NAME
        self.vector_dimensions = vector_dimensions
        self._timeout = timeout

        if client is not None:
            self._client = client
            return

        resolved_url = url if url is not None else self.config.qdrant_url
        resolved_host = host if host is not None else self.config.qdrant_host
        resolved_path = path or os.getenv("QDRANT_PATH")
        resolved_port = port if port is not None else self.config.qdrant_port

        try:
            if location is not None:
                self._client = QdrantClient(location=location)
            elif resolved_url:
                self._client = QdrantClient(url=resolved_url, timeout=int(timeout))
            elif resolved_host:
                self._client = QdrantClient(
                    host=resolved_host, port=resolved_port, timeout=int(timeout)
                )
            elif resolved_path:
                os.makedirs(resolved_path, exist_ok=True)
                self._client = QdrantClient(path=resolved_path)
            else:
                self._client = QdrantClient(location=":memory:")
        except Exception as exc:
            raise KnowledgeBaseUnavailableException(
                f"Failed to initialize Qdrant client: {exc}"
            ) from exc

    def ensure_collection(self) -> None:
        """Ensure the `trackflow_knowledge` collection and payload indexes exist.

        Raises:
            KnowledgeBaseUnavailableException: If Qdrant cannot be reached or configured.
        """
        try:
            exists = self._client.collection_exists(collection_name=self.collection_name)
            if not exists:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=self.vector_dimensions,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message="Payload indexes have no effect in the local Qdrant.*",
                    )
                    for field_name in ("company", "source_document", "language"):
                        try:
                            self._client.create_payload_index(
                                collection_name=self.collection_name,
                                field_name=field_name,
                                field_schema=qmodels.PayloadSchemaType.KEYWORD,
                            )
                        except Exception:
                            pass
        except Exception as exc:
            raise KnowledgeBaseUnavailableException(
                f"Unable to ensure Qdrant collection '{self.collection_name}': {exc}"
            ) from exc

    def upsert_chunks(self, chunks: List[KnowledgeChunk]) -> Dict[str, int]:
        """Idempotently upsert KnowledgeChunks using deterministic UUID v5 identifiers.

        Args:
            chunks: List of KnowledgeChunk instances with vectors populated.

        Returns:
            Dictionary with counts: {'added': int, 'updated': int, 'total': int}.

        Raises:
            IngestionException: If any chunk is missing a valid vector.
            KnowledgeBaseUnavailableException: If Qdrant upsert fails.
        """
        if not chunks:
            return {"added": 0, "updated": 0, "total": 0}

        for chunk in chunks:
            if not chunk.vector or len(chunk.vector) != self.vector_dimensions:
                raise IngestionException(
                    f"Chunk '{chunk.id}' has invalid vector dimensions "
                    f"(expected {self.vector_dimensions})."
                )

        self.ensure_collection()

        try:
            point_ids = [str(chunk.id) for chunk in chunks]
            existing_records = self._client.retrieve(
                collection_name=self.collection_name,
                ids=point_ids,
                with_payload=False,
                with_vectors=False,
            )
            existing_ids = {str(rec.id) for rec in existing_records}

            points: List[qmodels.PointStruct] = []
            added_count = 0
            updated_count = 0

            for chunk in chunks:
                pid = str(chunk.id)
                if pid in existing_ids:
                    updated_count += 1
                else:
                    added_count += 1

                payload: Dict[str, Any] = {
                    "company": chunk.company,
                    "source_document": chunk.source_document,
                    "section": chunk.section,
                    "language": chunk.language,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                }
                points.append(
                    qmodels.PointStruct(
                        id=pid,
                        vector=chunk.vector or [],
                        payload=payload,
                    )
                )

            self._client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            return {
                "added": added_count,
                "updated": updated_count,
                "total": len(points),
            }
        except IngestionException:
            raise
        except Exception as exc:
            raise KnowledgeBaseUnavailableException(
                f"Failed to upsert chunks into Qdrant collection '{self.collection_name}': {exc}"
            ) from exc

    def search(
        self,
        query_vector: List[float],
        top_k: int = 3,
        language: Optional[str] = None,
    ) -> List[RetrievedContext]:
        """Execute semantic cosine similarity search against `trackflow_knowledge`.

        Args:
            query_vector: 384-dimensional query embedding vector.
            top_k: Maximum number of results to return.
            language: Optional language filter.

        Returns:
            List of RetrievedContext ordered by similarity_score descending.

        Raises:
            KnowledgeBaseUnavailableException: If Qdrant search fails or times out.
        """
        if len(query_vector) != self.vector_dimensions:
            raise KnowledgeBaseUnavailableException(
                f"Query vector dimension mismatch: expected {self.vector_dimensions}, got {len(query_vector)}."
            )

        try:
            exists = self._client.collection_exists(collection_name=self.collection_name)
            if not exists:
                return []

            must_conditions: List[Any] = [
                qmodels.FieldCondition(
                    key="company",
                    match=qmodels.MatchValue(value="trackflow"),
                )
            ]
            if language:
                must_conditions.append(
                    qmodels.FieldCondition(
                        key="language",
                        match=qmodels.MatchValue(value=language),
                    )
                )
            query_filter = qmodels.Filter(must=must_conditions)

            if hasattr(self._client, "query_points"):
                response = self._client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )
                scored_points = response.points
            else:
                scored_points = self._client.search(  # type: ignore[attr-defined]
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )

            results: List[RetrievedContext] = []
            for rank_idx, pt in enumerate(scored_points, start=1):
                payload = pt.payload or {}
                chunk = KnowledgeChunk(
                    id=uuid.UUID(str(pt.id)),
                    company=str(payload.get("company", "trackflow")),
                    source_document=str(payload.get("source_document", "unknown")),
                    section=str(payload.get("section", "General")),
                    language=str(payload.get("language", "en")),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    text=str(payload.get("text", "")),
                )
                results.append(
                    RetrievedContext(
                        chunk=chunk,
                        similarity_score=round(float(pt.score), 4),
                        rank=rank_idx,
                    )
                )

            results.sort(key=lambda item: item.similarity_score, reverse=True)
            return results
        except Exception as exc:
            raise KnowledgeBaseUnavailableException(
                f"Vector search failed on collection '{self.collection_name}': {exc}"
            ) from exc

    def get_health_status(self) -> Dict[str, Any]:
        """Inspect Qdrant collection status and indexed points count.

        Returns:
            Dictionary with status, collection_name, indexed_points_count, and vector_dimensions.

        Raises:
            KnowledgeBaseUnavailableException: If Qdrant connection check fails.
        """
        try:
            exists = self._client.collection_exists(collection_name=self.collection_name)
            if not exists:
                return {
                    "status": "degraded",
                    "collection_name": self.collection_name,
                    "indexed_points_count": 0,
                    "vector_dimensions": self.vector_dimensions,
                }
            count_result = self._client.count(
                collection_name=self.collection_name, exact=True
            )
            points_count = int(count_result.count)
            status_val = "healthy" if points_count >= 12 else "degraded"
            return {
                "status": status_val,
                "collection_name": self.collection_name,
                "indexed_points_count": points_count,
                "vector_dimensions": self.vector_dimensions,
            }
        except Exception as exc:
            raise KnowledgeBaseUnavailableException(
                f"Qdrant health check failed: {exc}"
            ) from exc
