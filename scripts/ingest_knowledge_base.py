"""Idempotent CLI ingestion pipeline for the TrackFlow Knowledge Base.

Parses, semantically chunks, embeds, and indexes all four canonical corporate
policy documents into the Qdrant `trackflow_knowledge` collection through
the encapsulated `QdrantVectorStoreAdapter` and `FastEmbedAdapter`.
"""

import argparse
import dataclasses
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Ensure services/api is on sys.path for clean domain/application/infrastructure imports
REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.services.chunking import MarkdownSemanticChunker  # noqa: E402
from domain.knowledge.entities import (  # noqa: E402
    KnowledgeChunk,
    KnowledgeRuntimeConfig,
)
from domain.knowledge.exceptions import KnowledgeBaseException  # noqa: E402
from domain.knowledge.ports import (  # noqa: E402
    EmbeddingServicePort,
    VectorStorePort,
)
from infrastructure.adapters.embedding_adapter import FastEmbedAdapter  # noqa: E402
from infrastructure.adapters.qdrant_vector_store_adapter import (  # noqa: E402
    CANONICAL_COLLECTION_NAME,
    QdrantVectorStoreAdapter,
)

logger = logging.getLogger("trackflow.ingest_knowledge_base")


def ingest_corpus(
    docs_dir: Path,
    vector_store: VectorStorePort,
    embedder: EmbeddingServicePort,
    chunker: Optional[MarkdownSemanticChunker] = None,
) -> Dict[str, int]:
    """Parse, chunk, embed, and idempotently upsert the corporate knowledge base.

    Args:
        docs_dir: Directory containing canonical `trackflow-*.md` documents.
        vector_store: VectorStorePort implementation (`QdrantVectorStoreAdapter`).
        embedder: EmbeddingServicePort implementation (`FastEmbedAdapter`).
        chunker: Optional MarkdownSemanticChunker instance.

    Returns:
        Summary dictionary with keys 'documents', 'added', 'updated', 'total'.
    """
    active_chunker = chunker or MarkdownSemanticChunker()
    documents, raw_chunks = active_chunker.load_and_chunk_directory(docs_dir)

    for doc in documents:
        doc_chunk_count = sum(1 for c in raw_chunks if c.source_document == doc.id)
        filename = Path(doc.source_file).name
        print(f"Parsed {filename} ({doc_chunk_count} chunks)")

    texts = [chunk.text for chunk in raw_chunks]
    vectors = embedder.embed_documents(texts)

    embedded_chunks: List[KnowledgeChunk] = [
        dataclasses.replace(chunk, vector=vec)
        for chunk, vec in zip(raw_chunks, vectors)
    ]

    vector_store.ensure_collection()
    upsert_stats = vector_store.upsert_chunks(embedded_chunks)

    added = upsert_stats["added"]
    updated = upsert_stats["updated"]
    total = upsert_stats["total"]

    print(
        f"Indexed {total} points into Qdrant collection '{CANONICAL_COLLECTION_NAME}': "
        f"{added} new chunks added ({updated} updated/skipped)"
    )
    return {
        "documents": len(documents),
        "added": added,
        "updated": updated,
        "total": total,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for knowledge base ingestion."""
    parser = argparse.ArgumentParser(
        description="Idempotently ingest TrackFlow knowledge base documents into Qdrant."
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        default=str(REPO_ROOT / "docs" / "company-knowledge-base"),
        help="Path to directory containing trackflow-*.en.md files.",
    )
    parser.add_argument(
        "--in-memory",
        action="store_true",
        help="Use ephemeral :memory: Qdrant instance instead of persistent/remote storage.",
    )
    args = parser.parse_args(argv)

    docs_path = Path(args.docs_dir).resolve()
    try:
        config = KnowledgeRuntimeConfig.from_env()
        if args.in_memory:
            vector_store = QdrantVectorStoreAdapter(location=":memory:", config=config)
        elif config.qdrant_url or config.qdrant_host or os.getenv("QDRANT_PATH"):
            vector_store = QdrantVectorStoreAdapter(config=config)
        else:
            default_storage = REPO_ROOT / ".qdrant_storage"
            vector_store = QdrantVectorStoreAdapter(path=str(default_storage), config=config)

        embedder = FastEmbedAdapter(config=config)
        ingest_corpus(docs_dir=docs_path, vector_store=vector_store, embedder=embedder)
        return 0
    except KnowledgeBaseException as exc:
        print(f"Error during knowledge base ingestion: {exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected ingestion failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
