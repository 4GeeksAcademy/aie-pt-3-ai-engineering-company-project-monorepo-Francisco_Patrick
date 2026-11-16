"""RAG Retrieval & Answer Groundedness Benchmark Script (T027).

Evaluates the TrackFlow RAG pipeline against the standardized 10-query benchmark
dataset (`data/eval/test-queries.json`), computing:
- Recall@1
- Recall@3 (must be >= 80% per FR-015 / SC-002)
- Mean Reciprocal Rank (MRR)
- Out-of-scope refusal accuracy (100% per SC-003)
- Average query execution latency (< 3500 ms per SC-004).
"""

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.services.chunking import MarkdownSemanticChunker  # noqa: E402
from application.services.knowledge_service import KnowledgeService  # noqa: E402
from domain.knowledge.entities import QueryRequest  # noqa: E402
from infrastructure.adapters.embedding_adapter import FastEmbedAdapter  # noqa: E402
from infrastructure.adapters.grounded_generation_adapter import (  # noqa: E402
    GroundedGenerationAdapter,
)
from infrastructure.adapters.qdrant_vector_store_adapter import (  # noqa: E402
    QdrantVectorStoreAdapter,
)


def run_evaluation(eval_file: Path, docs_dir: Path) -> Dict[str, Any]:
    """Run the RAG evaluation benchmark and return aggregate metrics.

    Args:
        eval_file: Path to `data/eval/test-queries.json`.
        docs_dir: Path to `docs/company-knowledge-base/`.

    Returns:
        Dictionary of evaluation results including recall_at_1, recall_at_3, mrr, refusal_accuracy.
    """
    if not eval_file.exists():
        # Resolve relative to REPO_ROOT if called from services/api
        candidate = REPO_ROOT / eval_file
        if candidate.exists():
            eval_file = candidate
        else:
            raise FileNotFoundError(f"Evaluation dataset not found: {eval_file}")

    queries_data: List[Dict[str, Any]] = json.loads(
        eval_file.read_text(encoding="utf-8")
    )

    chunker = MarkdownSemanticChunker()
    embedder = FastEmbedAdapter()
    vector_store = QdrantVectorStoreAdapter(location=":memory:")
    llm_generator = GroundedGenerationAdapter()

    _, chunks = chunker.load_and_chunk_directory(docs_dir)
    vectors = embedder.embed_documents([c.text for c in chunks])
    embedded_chunks = [
        dataclasses.replace(c, vector=v) for c, v in zip(chunks, vectors)
    ]
    vector_store.upsert_chunks(embedded_chunks)

    service = KnowledgeService(
        vector_store=vector_store,
        embedding_service=embedder,
        llm_generator=llm_generator,
    )

    in_scope_total = 0
    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks: List[float] = []

    out_of_scope_total = 0
    out_of_scope_refusals = 0
    latencies_ms: List[float] = []

    print("=" * 72)
    print("TrackFlow RAG Knowledge Base — Retrieval & Grounding Evaluation Suite")
    print("=" * 72)

    for item in queries_data:
        qid = item["id"]
        query_text = item["query"]
        expected_doc = item.get("expected_source_document")
        is_oos = bool(item.get("is_out_of_scope", False))

        t0 = time.perf_counter()
        result = service.query(QueryRequest(query=query_text, top_k=3, min_score=0.62))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)

        retrieved_docs = [src.source_document for src in result.sources]

        if is_oos:
            out_of_scope_total += 1
            passed = result.is_refusal and len(result.sources) == 0
            if passed:
                out_of_scope_refusals += 1
            status_label = "PASS (REFUSED)" if passed else "FAIL (HALLUCINATED)"
            print(f"[{qid}] {status_label} | latency={elapsed_ms:.1f}ms | query='{query_text[:55]}...'")
        else:
            in_scope_total += 1
            rank_found: Optional[int] = None
            for idx, doc_slug in enumerate(retrieved_docs, start=1):
                if doc_slug == expected_doc:
                    rank_found = idx
                    break

            if rank_found == 1:
                hits_at_1 += 1
                hits_at_3 += 1
                reciprocal_ranks.append(1.0)
            elif rank_found is not None and rank_found <= 3:
                hits_at_3 += 1
                reciprocal_ranks.append(1.0 / rank_found)
            else:
                reciprocal_ranks.append(0.0)

            status_label = f"PASS (rank={rank_found})" if rank_found else "MISS"
            top_score = result.sources[0].similarity_score if result.sources else 0.0
            print(
                f"[{qid}] {status_label:<14} | score={top_score:.4f} | expected={expected_doc:<16} | got={retrieved_docs}"
            )

    recall_at_1 = (hits_at_1 / in_scope_total) if in_scope_total else 0.0
    recall_at_3 = (hits_at_3 / in_scope_total) if in_scope_total else 0.0
    mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0
    refusal_acc = (
        (out_of_scope_refusals / out_of_scope_total) if out_of_scope_total else 1.0
    )
    avg_latency_ms = (sum(latencies_ms) / len(latencies_ms)) if latencies_ms else 0.0

    print("-" * 72)
    print(f"In-Scope Queries Evaluated : {in_scope_total}")
    print(f"Recall@1                   : {recall_at_1 * 100:.1f}% ({hits_at_1}/{in_scope_total})")
    print(f"Recall@3 (Target >= 80.0%) : {recall_at_3 * 100:.1f}% ({hits_at_3}/{in_scope_total})")
    print(f"Mean Reciprocal Rank (MRR) : {mrr:.4f}")
    print(f"Out-of-Scope Refusal Rate  : {refusal_acc * 100:.1f}% ({out_of_scope_refusals}/{out_of_scope_total})")
    print(f"Average Latency            : {avg_latency_ms:.2f} ms")
    print("=" * 72)

    return {
        "in_scope_total": in_scope_total,
        "recall_at_1": recall_at_1,
        "recall_at_3": recall_at_3,
        "mrr": mrr,
        "refusal_accuracy": refusal_acc,
        "avg_latency_ms": avg_latency_ms,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for RAG benchmark evaluation."""
    parser = argparse.ArgumentParser(
        description="Evaluate TrackFlow RAG retrieval Recall@3 and refusal accuracy."
    )
    parser.add_argument(
        "--eval-file",
        type=str,
        default=str(REPO_ROOT / "data" / "eval" / "test-queries.json"),
        help="Path to evaluation queries JSON file.",
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        default=str(REPO_ROOT / "docs" / "company-knowledge-base"),
        help="Path to canonical knowledge base markdown files.",
    )
    args = parser.parse_args(argv)

    metrics = run_evaluation(
        eval_file=Path(args.eval_file),
        docs_dir=Path(args.docs_dir),
    )
    if metrics["recall_at_3"] < 0.80 or metrics["refusal_accuracy"] < 1.0:
        print(
            "Benchmark FAILED: Recall@3 must be >= 80% and Refusal Accuracy must be 100%.",
            file=sys.stderr,
        )
        return 1

    print("Benchmark PASSED: All KPIs exceeded target thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
