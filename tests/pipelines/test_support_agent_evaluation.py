"""Automated evaluation test suite for TrackFlow Support Agent with LangGraph (T025–T029).

Verifies:
- T025: `EvaluationTestCase` entity and trace-driven evaluation fixtures
- T026 (Eval Scenario 1): Standard policy reasoning flow (`["intake", "retrieval", "generation"]`) evaluated against the trace
- T027 (Eval Scenario 2): Conditional refusal routing (`["intake", "retrieval", "refusal"]`) for unindexed topics evaluated against the trace
- T028 (Eval Scenario 3): Input validation and early termination (`["intake", "refusal"]`) for empty/whitespace queries evaluated against the trace
- T029 (Eval Scenario 4): Factual policy grounding against `docs/company-knowledge-base/` and `docs/rag/trackflow-BRIEFING.en.md` for return policy (30 days), warehouse storage pricing (Los Angeles 18 USD / Zaragoza 16 EUR), and Miguel Torres commercial governance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Dict, List

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
from data.pipelines.rag_pipeline import (  # noqa: E402
    embed,
    generate_answer,
    query as rag_query,
    retrieve,
    setup,
)
from domain.agent.entities import AgentQueryRequest, AgentTrace  # noqa: E402
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
        description="Warehouse storage pricing and discount governance grounds response in Los Angeles (18 USD), Zaragoza (16 EUR), and Miguel Torres approval per BRIEFING",
        query="What is the standard monthly storage rate in Los Angeles versus Zaragoza and can we offer a storage discount?",
        expected_node_sequence=["intake", "retrieval", "generation"],
        expected_is_refusal=False,
        prohibited_nodes=["refusal"],
        expected_text_contains=[
            "18 USD",
            "16 EUR",
            "Los Angeles",
            "Zaragoza",
            "Miguel Torres",
        ],
        expected_sources_min=1,
    ),
]


@pytest.fixture(scope="module")
def seeded_support_agent_service() -> SupportAgentService:
    """Create a deterministic SupportAgentService seeded via `data.pipelines.rag_pipeline` (`setup` + `embed`)."""
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
    vector_store = setup(
        vector_store=QdrantVectorStoreAdapter(config=config),
        config=config,
    )

    docs_dir = REPO_ROOT / "docs" / "company-knowledge-base"
    chunker = MarkdownSemanticChunker()
    _, chunks = chunker.load_and_chunk_directory(docs_dir)
    embed(
        inputs=chunks,
        embedding_service=embedder,
        vector_store=vector_store,
        config=config,
    )

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


@pytest.fixture(scope="module")
def recorded_evaluation_traces(
    seeded_support_agent_service: SupportAgentService,
) -> Dict[str, AgentTrace]:
    """Generate and persist traces once so all evaluation tests run against recorded traces rather than live re-executions."""
    traces_by_test_id: Dict[str, AgentTrace] = {}
    for case in EVALUATION_TEST_CASES:
        thread_id = f"trace-{case.test_id.lower()}"
        seeded_support_agent_service.query(
            AgentQueryRequest(
                query=case.query,
                top_k=3,
                min_score=0.62,
                thread_id=thread_id,
            )
        )
        traces_by_test_id[case.test_id] = seeded_support_agent_service.get_trace(
            thread_id
        )
    return traces_by_test_id


def test_eval_standard_policy_reasoning_flow(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T026 (Eval Scenario 1): Verify against recorded trace that `retrieval` ran before `generation` and cited `returns-policy`."""
    case = EVALUATION_TEST_CASES[0]
    trace = recorded_evaluation_traces[case.test_id]

    assert trace.node_sequence == case.expected_node_sequence
    assert trace.node_sequence.index("retrieval") < trace.node_sequence.index(
        "generation"
    )
    assert trace.is_refusal is case.expected_is_refusal
    assert trace.source_count >= case.expected_sources_min

    for prohibited in case.prohibited_nodes:
        assert prohibited not in trace.node_sequence
    assert set(trace.step_latencies.keys()) == {"intake", "retrieval", "generation"}

    # Verify per-node outputs recorded in the trace
    assert set(trace.node_outputs.keys()) == {"intake", "retrieval", "generation"}
    retrieval_out = trace.node_outputs["retrieval"]
    assert retrieval_out["context_count"] >= 1
    assert any(
        c["source_document"] == "returns-policy"
        for c in retrieval_out["retrieved_chunks"]
    )
    assert all(
        c["similarity_score"] >= 0.62 for c in retrieval_out["retrieved_chunks"]
    )

    generation_out = trace.node_outputs["generation"]
    assert generation_out["answer"] == trace.final_answer
    for phrase in case.expected_text_contains:
        assert phrase.lower() in trace.final_answer.lower()


def test_eval_conditional_refusal_for_unindexed_topic(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T027 (Eval Scenario 2): Verify against recorded trace that unindexed topic routes `intake -> retrieval -> refusal` without `generation`."""
    case = EVALUATION_TEST_CASES[1]
    trace = recorded_evaluation_traces[case.test_id]

    assert trace.node_sequence == case.expected_node_sequence
    assert "generation" not in trace.node_sequence
    assert trace.is_refusal is True
    assert trace.source_count == 0

    assert set(trace.node_outputs.keys()) == {"intake", "retrieval", "refusal"}
    assert trace.node_outputs["retrieval"]["context_count"] == 0
    assert trace.node_outputs["refusal"]["is_refusal"] is True

    for phrase in case.expected_text_contains:
        assert phrase.lower() in trace.final_answer.lower()


def test_eval_empty_query_early_termination(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T028 (Eval Scenario 3): Verify against recorded trace that empty/whitespace query halts at `intake -> refusal` without `retrieval` or `generation`."""
    case = EVALUATION_TEST_CASES[2]
    trace = recorded_evaluation_traces[case.test_id]

    assert trace.node_sequence == case.expected_node_sequence
    assert "retrieval" not in trace.node_sequence
    assert "generation" not in trace.node_sequence
    assert trace.is_refusal is True
    assert trace.source_count == 0
    assert trace.total_duration_ms < 50.0

    assert set(trace.node_outputs.keys()) == {"intake", "refusal"}
    assert trace.node_outputs["intake"]["is_valid"] is False
    assert trace.node_outputs["refusal"]["is_refusal"] is True


def test_eval_storage_pricing_grounding(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T029 (Eval Scenario 4): Verify against recorded trace that answers remain anchored in `trackflow-BRIEFING.en.md` and policy docs."""
    case = EVALUATION_TEST_CASES[3]
    trace = recorded_evaluation_traces[case.test_id]

    assert trace.node_sequence == ["intake", "retrieval", "generation"]
    assert trace.is_refusal is False
    assert any(
        c["source_document"] == "storage-pricing"
        for c in trace.node_outputs["retrieval"]["retrieved_chunks"]
    )
    for phrase in case.expected_text_contains:
        assert phrase.lower() in trace.final_answer.lower()

    # Cross-check against source policy files and BRIEFING
    briefing_text = (
        REPO_ROOT / "docs" / "rag" / "trackflow-BRIEFING.en.md"
    ).read_text(encoding="utf-8")
    assert "Miguel Torres" in briefing_text
    assert "Miguel Torres" in trace.final_answer

    storage_doc_text = (
        REPO_ROOT / "docs" / "company-knowledge-base" / "trackflow-storage-pricing.en.md"
    ).read_text(encoding="utf-8")
    assert "18 USD" in storage_doc_text and "18 USD" in trace.final_answer
    assert "16 EUR" in storage_doc_text and "16 EUR" in trace.final_answer

    returns_doc_text = (
        REPO_ROOT / "docs" / "company-knowledge-base" / "trackflow-returns-policy.en.md"
    ).read_text(encoding="utf-8")
    returns_trace = recorded_evaluation_traces["EVAL-001"]
    assert "30 days" in returns_doc_text and "30 days" in returns_trace.final_answer


def test_evaluation_matrix_all_scenarios_pass(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T025: Evaluate the full EVALUATION_TEST_CASES matrix against recorded traces and verify checkpoint persistence."""
    assert len(EVALUATION_TEST_CASES) >= 4
    for case in EVALUATION_TEST_CASES:
        trace = recorded_evaluation_traces[case.test_id]
        assert trace.node_sequence == case.expected_node_sequence, f"Failed {case.test_id}"
        assert trace.is_refusal is case.expected_is_refusal, f"Failed {case.test_id}"
        for prohibited in case.prohibited_nodes:
            assert prohibited not in trace.node_sequence, f"Failed {case.test_id}"
        assert trace.source_count >= case.expected_sources_min, f"Failed {case.test_id}"
        for expected_snippet in case.expected_text_contains:
            assert expected_snippet.lower() in trace.final_answer.lower(), (
                f"Failed {case.test_id}: missing '{expected_snippet}' in '{trace.final_answer}'"
            )
        assert len(trace.checkpoints) >= 1
        assert set(trace.node_outputs.keys()) == set(trace.node_sequence)


def test_rag_pipeline_contract_separation_and_reuse(
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """Verify `data.pipelines.rag_pipeline` exposes separated `retrieve()` and `generate_answer(question, context)`, and `query()` skips `retrieve()` when given pre-retrieved chunks."""
    question = "What is TrackFlow's standard return window?"
    contexts = retrieve(
        question=question,
        vector_store=seeded_support_agent_service._vector_store,
        embedding_service=seeded_support_agent_service._embedding_service,
        top_k=3,
        min_score=0.62,
    )
    assert len(contexts) >= 1

    answer, citations = generate_answer(
        question=question,
        context=contexts,
        llm_generator=seeded_support_agent_service._llm_generator,
    )
    assert "30 days" in answer
    assert len(citations) == len(contexts)

    # Passing pre-retrieved context to rag_query must skip internal retrieval
    grounded = rag_query(
        question=question,
        vector_store=seeded_support_agent_service._vector_store,
        embedding_service=seeded_support_agent_service._embedding_service,
        llm_generator=seeded_support_agent_service._llm_generator,
        context=contexts,
    )
    assert grounded.is_refusal is False
    assert "30 days" in grounded.answer
