"""Automated evaluation test suite for TrackFlow Support Agent with LangGraph (T025–T029).

Verifies:
- T025: `EvaluationTestCase` entity and end-to-end knowledge base seeded evaluation fixtures
- T026 (Eval Scenario 1): Standard policy reasoning flow (`["intake", "retrieval", "generation"]`)
- T027 (Eval Scenario 2): Conditional refusal routing (`["intake", "retrieval", "refusal"]`) for unindexed topics
- T028 (Eval Scenario 3): Input validation and early termination (`["intake", "refusal"]`) for empty/whitespace queries
- T029 (Eval Scenario 4): Factual policy grounding against `docs/company-knowledge-base/` for return policy (30 days) and warehouse storage pricing (Los Angeles 18 USD / Zaragoza 16 EUR).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from application.services.chunking import MarkdownSemanticChunker  # noqa: E402
from application.services.guardrails import BusinessGuardrailValidator  # noqa: E402
from application.services.support_agent_service import SupportAgentService  # noqa: E402
from application.services.trace_registry import TraceRegistry  # noqa: E402
from domain.agent.entities import AgentQueryRequest  # noqa: E402
from domain.knowledge.entities import KnowledgeRuntimeConfig  # noqa: E402
from infrastructure.adapters.embedding_adapter import FastEmbedAdapter  # noqa: E402
from infrastructure.adapters.grounded_generation_adapter import (  # noqa: E402
    GroundedGenerationAdapter,
)
from infrastructure.adapters.qdrant_vector_store_adapter import (  # noqa: E402
    QdrantVectorStoreAdapter,
)


@dataclass(frozen=True)
class EvaluationTestCase:
    """Automated evaluation scenario asserting trace topology, routing, and factual grounding."""

    test_id: str
    description: str
    query: str
    expected_node_sequence: List[str]
    expected_is_refusal: bool
    prohibited_nodes: List[str] = field(default_factory=list)
    expected_text_contains: List[str] = field(default_factory=list)
    expected_sources_min: int = 0


EVALUATION_TEST_CASES: List[EvaluationTestCase] = [
    EvaluationTestCase(
        test_id="EVAL-001",
        description="Standard return window inquiry executes intake -> retrieval -> generation with 30-day grounding",
        query="What is TrackFlow's standard return window and who covers return shipping costs?",
        expected_node_sequence=["intake", "retrieval", "generation"],
        expected_is_refusal=False,
        prohibited_nodes=["refusal"],
        expected_text_contains=["30 days", "client brand"],
        expected_sources_min=1,
    ),
    EvaluationTestCase(
        test_id="EVAL-002",
        description="Unindexed pharmaceutical refrigeration inquiry branches conditionally to refusal without generation",
        query="What is the temperature range for pharmaceutical refrigeration storage?",
        expected_node_sequence=["intake", "retrieval", "refusal"],
        expected_is_refusal=True,
        prohibited_nodes=["generation"],
        expected_text_contains=[
            "TrackFlow internal documentation does not contain verified policy regarding",
            "pharmaceutical refrigeration",
        ],
        expected_sources_min=0,
    ),
    EvaluationTestCase(
        test_id="EVAL-003",
        description="Empty or whitespace inquiry halts early at intake -> refusal without vector retrieval or generation",
        query="     ",
        expected_node_sequence=["intake", "refusal"],
        expected_is_refusal=True,
        prohibited_nodes=["retrieval", "generation"],
        expected_text_contains=[
            "TrackFlow internal documentation does not contain verified policy regarding"
        ],
        expected_sources_min=0,
    ),
    EvaluationTestCase(
        test_id="EVAL-004",
        description="Warehouse storage pricing inquiry grounds response in Los Angeles (18 USD) and Zaragoza (16 EUR) rates",
        query="What is the standard monthly storage rate in Los Angeles versus Zaragoza?",
        expected_node_sequence=["intake", "retrieval", "generation"],
        expected_is_refusal=False,
        prohibited_nodes=["refusal"],
        expected_text_contains=["18 USD", "16 EUR", "Los Angeles", "Zaragoza", "30"],
        expected_sources_min=1,
    ),
]


@pytest.fixture(scope="module")
def seeded_support_agent_service() -> SupportAgentService:
    """Create a deterministic SupportAgentService seeded with the 4 canonical TrackFlow policy documents."""
    os.environ["QDRANT_Path"] = ""
    os.environ["QDRANT_PATH"] = ""
    config = KnowledgeRuntimeConfig.from_env(
        env={
            "LLM_PROVIDER": "deterministic",
            "KNOWLEDGE_SIMILARITY_THRESHOLD": "0.62",
            "USE_FASTEMBED_ONNX": "false",
            "QDRANT_URL": "",
            "QDRANT_HOST": "",
            "QDRANT_COLLECTION_NAME": "trackflow_knowledge",
        },
        load_dotenv_file=False,
    )

    embedder = FastEmbedAdapter(config=config)
    vector_store = QdrantVectorStoreAdapter(config=config)
    vector_store.ensure_collection()

    docs_dir = REPO_ROOT / "docs" / "company-knowledge-base"
    chunker = MarkdownSemanticChunker()
    _, chunks = chunker.load_and_chunk_directory(docs_dir)
    vectors = embedder.embed_documents([c.text for c in chunks])
    embedded_chunks = [
        dataclasses.replace(c, vector=v) for c, v in zip(chunks, vectors)
    ]
    vector_store.upsert_chunks(embedded_chunks)

    llm_generator = GroundedGenerationAdapter(
        guardrail_validator=BusinessGuardrailValidator(),
        config=config,
    )
    registry = TraceRegistry()

    return SupportAgentService(
        vector_store=vector_store,
        embedding_service=embedder,
        llm_generator=llm_generator,
        trace_registry=registry,
        config=config,
    )


def test_eval_standard_policy_reasoning_flow(
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """T026 (Eval Scenario 1): Verify standard policy query executes intake -> retrieval -> generation and cites returns-policy."""
    case = EVALUATION_TEST_CASES[0]
    result = seeded_support_agent_service.query(
        AgentQueryRequest(query=case.query, top_k=3, min_score=0.62)
    )

    assert result.node_sequence == case.expected_node_sequence
    assert result.is_refusal is case.expected_is_refusal
    assert len(result.sources) >= case.expected_sources_min
    assert any(src.source_document == "returns-policy" for src in result.sources)
    assert all(src.similarity_score >= 0.62 for src in result.sources)

    for phrase in case.expected_text_contains:
        assert phrase.lower() in result.answer.lower()

    trace = seeded_support_agent_service.get_trace(result.trace_id)
    assert trace.node_sequence == ["intake", "retrieval", "generation"]
    for prohibited in case.prohibited_nodes:
        assert prohibited not in trace.node_sequence
    assert set(trace.step_latencies.keys()) == {"intake", "retrieval", "generation"}


def test_eval_conditional_refusal_for_unindexed_topic(
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """T027 (Eval Scenario 2): Verify unindexed topic routes to intake -> retrieval -> refusal without invoking generation."""
    case = EVALUATION_TEST_CASES[1]
    result = seeded_support_agent_service.query(
        AgentQueryRequest(query=case.query, top_k=3, min_score=0.62)
    )

    assert result.node_sequence == case.expected_node_sequence
    assert result.is_refusal is True
    assert result.sources == []
    for phrase in case.expected_text_contains:
        assert phrase.lower() in result.answer.lower()

    trace = seeded_support_agent_service.get_trace(result.trace_id)
    assert trace.node_sequence == ["intake", "retrieval", "refusal"]
    assert "generation" not in trace.node_sequence
    assert trace.source_count == 0


def test_eval_empty_query_early_termination(
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """T028 (Eval Scenario 3): Verify empty/whitespace query halts at intake -> refusal without executing retrieval or generation."""
    case = EVALUATION_TEST_CASES[2]
    result = seeded_support_agent_service.query(
        AgentQueryRequest(query=case.query, top_k=3, min_score=0.62)
    )

    assert result.node_sequence == case.expected_node_sequence
    assert result.is_refusal is True
    assert result.sources == []

    trace = seeded_support_agent_service.get_trace(result.trace_id)
    assert trace.node_sequence == ["intake", "refusal"]
    assert "retrieval" not in trace.node_sequence
    assert "generation" not in trace.node_sequence
    assert trace.total_duration_ms < 50.0


def test_eval_storage_pricing_grounding(
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """T029 (Eval Scenario 4): Verify factual grounding for warehouse storage pricing and return policy against company docs."""
    case = EVALUATION_TEST_CASES[3]
    result = seeded_support_agent_service.query(
        AgentQueryRequest(query=case.query, top_k=3, min_score=0.62)
    )

    assert result.node_sequence == ["intake", "retrieval", "generation"]
    assert result.is_refusal is False
    assert any(src.source_document == "storage-pricing" for src in result.sources)
    for phrase in case.expected_text_contains:
        assert phrase.lower() in result.answer.lower()

    # Cross-check against source policy file in docs/company-knowledge-base/
    storage_doc_text = (
        REPO_ROOT / "docs" / "company-knowledge-base" / "trackflow-storage-pricing.en.md"
    ).read_text(encoding="utf-8")
    assert "18 USD" in storage_doc_text and "18 USD" in result.answer
    assert "16 EUR" in storage_doc_text and "16 EUR" in result.answer

    returns_doc_text = (
        REPO_ROOT / "docs" / "company-knowledge-base" / "trackflow-returns-policy.en.md"
    ).read_text(encoding="utf-8")
    return_res = seeded_support_agent_service.query(
        AgentQueryRequest(query="What is TrackFlow's standard return window?")
    )
    assert "30 days" in returns_doc_text and "30 days" in return_res.answer


def test_evaluation_matrix_all_scenarios_pass(
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """T025: Execute the full EVALUATION_TEST_CASES matrix and verify 100% pass rate and checkpoint persistence."""
    assert len(EVALUATION_TEST_CASES) >= 4
    for case in EVALUATION_TEST_CASES:
        result = seeded_support_agent_service.query(
            AgentQueryRequest(
                query=case.query,
                top_k=3,
                min_score=0.62,
                thread_id=f"eval-matrix-{case.test_id.lower()}",
            )
        )
        assert result.node_sequence == case.expected_node_sequence, f"Failed {case.test_id}"
        assert result.is_refusal is case.expected_is_refusal, f"Failed {case.test_id}"
        for prohibited in case.prohibited_nodes:
            assert prohibited not in result.node_sequence, f"Failed {case.test_id}"
        assert len(result.sources) >= case.expected_sources_min, f"Failed {case.test_id}"
        for expected_snippet in case.expected_text_contains:
            assert expected_snippet.lower() in result.answer.lower(), (
                f"Failed {case.test_id}: missing '{expected_snippet}' in '{result.answer}'"
            )
        checkpoints = seeded_support_agent_service.get_checkpoints(result.trace_id)
        assert len(checkpoints) >= 1
