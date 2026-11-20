"""Automated evaluation test suite for TrackFlow Support Agent with LangGraph (T038–T042).

Verifies:
- Part 1 RAG & Grounding Scenarios (`EVAL-001` – `EVAL-004`):
  - `test_eval_standard_policy_reasoning_flow` (`EVAL-001`): `["intake", "retrieval", "generation"]`, `sources_consulted == ["rag"]`
  - `test_eval_conditional_refusal_for_unindexed_topic` (`EVAL-002`): `["intake", "retrieval", "refusal"]`
  - `test_eval_empty_query_early_termination` (`EVAL-003`): `["intake", "refusal"]`
  - `test_eval_storage_pricing_grounding` (`EVAL-004`): Los Angeles (`18 USD`), Zaragoza (`16 EUR`), and `Miguel Torres` approval
- Part 2 Operational Tools & Autonomous Routing Scenarios (`EVAL-005` – `EVAL-009`):
  - `test_eval_autonomous_ticket_tool_routing` (`EVAL-005`): Live support ticket (`INC-001`) resolved via `ticket_tool` without RAG
  - `test_eval_autonomous_rag_vs_tool_separation` (`EVAL-006`): Static policy inquiry resolved via `rag` without invoking `ticket_tool` or `inventory_tool`
  - `test_eval_autonomous_inventory_tool_routing` (`EVAL-007`): Live SKU (`TF-1001`) resolved via `inventory_tool` with stock & threshold status
  - `test_eval_tool_fallback_on_missing_ticket_or_unavailable_service` (`EVAL-008`): Missing ticket (`INC-999999`) and simulated tool timeout/unavailable service traverse `tool_fallback` honestly
  - `test_eval_hybrid_multi_source_canonical_order_and_partial_fallback` (`EVAL-009`): Canonical multi-source execution (`ticket_tool` -> `retrieval` -> `generation`) and graceful partial fallback (`ticket_tool` -> `retrieval` -> `tool_fallback` -> `generation`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional

import pytest
from sqlmodel import SQLModel, Session, create_engine
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from application.inventory.dto import InboundOrderCreateDTO, ProductCreateDTO  # noqa: E402
from application.inventory.inventory_service import InventoryService  # noqa: E402
from application.services.chunking import MarkdownSemanticChunker  # noqa: E402
from application.services.guardrails import BusinessGuardrailValidator  # noqa: E402
from application.services.incident_service import IncidentService  # noqa: E402
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
from domain.incident_model import Incident  # noqa: E402
from domain.knowledge.entities import KnowledgeRuntimeConfig  # noqa: E402
from infrastructure.adapters.embedding_adapter import FastEmbedAdapter  # noqa: E402
from infrastructure.adapters.grounded_generation_adapter import (  # noqa: E402
    GroundedGenerationAdapter,
)
from infrastructure.adapters.inventory_stock_tool_adapter import (  # noqa: E402
    InventoryStockQueryToolAdapter,
)
from infrastructure.adapters.qdrant_vector_store_adapter import (  # noqa: E402
    QdrantVectorStoreAdapter,
)
from infrastructure.adapters.support_ticket_tool_adapter import (  # noqa: E402
    IncidentSupportTicketToolAdapter,
)
from infrastructure.adapters.tiny_db_incident_repository import (  # noqa: E402
    TinyDBIncidentRepository,
)
from infrastructure.persistence.sqlmodel.inventory_repository import (  # noqa: E402
    SQLModelInventoryRepository,
)
from shared.incidents.enums import (  # noqa: E402
    IncidentCategory,
    IncidentOrigin,
    IncidentStatus,
)


@dataclass(frozen=True)
class EvaluationTestCase:
    """Automated evaluation scenario asserting trace topology, autonomous routing, and factual grounding."""

    test_id: str
    description: str
    query: str
    expected_node_sequence: List[str]
    expected_is_refusal: bool
    expected_sources_consulted: List[str] = field(default_factory=list)
    expected_fallback_triggered: bool = False
    prohibited_nodes: List[str] = field(default_factory=list)
    expected_text_contains: List[str] = field(default_factory=list)
    prohibited_text_contains: List[str] = field(default_factory=list)
    expected_sources_min: int = 0


EVALUATION_TEST_CASES: List[EvaluationTestCase] = [
    EvaluationTestCase(
        test_id="EVAL-001",
        description="Standard return window inquiry executes intake -> retrieval -> generation with 30-day grounding",
        query="What is TrackFlow's standard return window and who covers return shipping costs?",
        expected_node_sequence=["intake", "retrieval", "generation"],
        expected_is_refusal=False,
        expected_sources_consulted=["rag"],
        expected_fallback_triggered=False,
        prohibited_nodes=["refusal", "ticket_tool", "inventory_tool", "tool_fallback"],
        expected_text_contains=["30 days", "client brand"],
        expected_sources_min=1,
    ),
    EvaluationTestCase(
        test_id="EVAL-002",
        description="Unindexed pharmaceutical refrigeration inquiry branches conditionally to refusal without generation",
        query="What is the temperature range for pharmaceutical refrigeration storage?",
        expected_node_sequence=["intake", "retrieval", "refusal"],
        expected_is_refusal=True,
        expected_sources_consulted=["rag"],
        expected_fallback_triggered=False,
        prohibited_nodes=["generation", "ticket_tool", "inventory_tool", "tool_fallback"],
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
        expected_sources_consulted=[],
        expected_fallback_triggered=False,
        prohibited_nodes=["retrieval", "generation", "ticket_tool", "inventory_tool", "tool_fallback"],
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
        expected_sources_consulted=["rag"],
        expected_fallback_triggered=False,
        prohibited_nodes=["refusal", "ticket_tool", "inventory_tool", "tool_fallback"],
        expected_text_contains=[
            "18 USD",
            "16 EUR",
            "Los Angeles",
            "Zaragoza",
            "Miguel Torres",
        ],
        expected_sources_min=1,
    ),
    EvaluationTestCase(
        test_id="EVAL-005",
        description="Autonomous operational tool routing: live support ticket INC-001 resolved exclusively via ticket_tool",
        query="What is the current status and category of support ticket INC-001?",
        expected_node_sequence=["intake", "ticket_tool", "generation"],
        expected_is_refusal=False,
        expected_sources_consulted=["ticket_tool"],
        expected_fallback_triggered=False,
        prohibited_nodes=["retrieval", "inventory_tool", "tool_fallback", "refusal"],
        expected_text_contains=[
            "INC-001",
            "Delayed pallet shipment to Zaragoza",
            "open",
            "warehouse",
            "zaragoza",
        ],
        expected_sources_min=0,
    ),
    EvaluationTestCase(
        test_id="EVAL-006",
        description="Autonomous RAG vs tool separation: static claim reporting policy resolved exclusively via RAG",
        query="What is TrackFlow's standard return window and who covers return shipping fees?",
        expected_node_sequence=["intake", "retrieval", "generation"],
        expected_is_refusal=False,
        expected_sources_consulted=["rag"],
        expected_fallback_triggered=False,
        prohibited_nodes=["ticket_tool", "inventory_tool", "tool_fallback", "refusal"],
        expected_text_contains=["30 days", "client brand"],
        expected_sources_min=1,
    ),
    EvaluationTestCase(
        test_id="EVAL-007",
        description="Autonomous inventory tool routing: live SKU TF-1001 stock level resolved exclusively via inventory_tool",
        query="How many units of SKU TF-1001 are currently in stock?",
        expected_node_sequence=["intake", "inventory_tool", "generation"],
        expected_is_refusal=False,
        expected_sources_consulted=["inventory_tool"],
        expected_fallback_triggered=False,
        prohibited_nodes=["retrieval", "ticket_tool", "tool_fallback", "refusal"],
        expected_text_contains=[
            "TF-1001",
            "Industrial Thermal Shipping Label Roll",
            "145 units",
            "20",
        ],
        expected_sources_min=0,
    ),
    EvaluationTestCase(
        test_id="EVAL-008",
        description="Honest fallback recovery on non-existent support ticket INC-999999 without hallucinated status",
        query="What is the current status of support ticket INC-999999?",
        expected_node_sequence=["intake", "ticket_tool", "tool_fallback"],
        expected_is_refusal=False,
        expected_sources_consulted=["ticket_tool"],
        expected_fallback_triggered=True,
        prohibited_nodes=["retrieval", "inventory_tool", "generation", "refusal"],
        expected_text_contains=[
            "I couldn't confirm the status of ticket 'INC-999999' right now",
            "no matching incident record was found",
        ],
        prohibited_text_contains=["status 'open'", "status 'resolved'", "status 'in_progress'"],
        expected_sources_min=0,
    ),
    EvaluationTestCase(
        test_id="EVAL-009",
        description="Hybrid multi-source inquiry executes in canonical order ticket_tool -> retrieval -> generation",
        query="What is the status of ticket INC-001, and what is TrackFlow's standard return window?",
        expected_node_sequence=["intake", "ticket_tool", "retrieval", "generation"],
        expected_is_refusal=False,
        expected_sources_consulted=["ticket_tool", "rag"],
        expected_fallback_triggered=False,
        prohibited_nodes=["inventory_tool", "tool_fallback", "refusal"],
        expected_text_contains=[
            "INC-001",
            "open",
            "zaragoza",
            "30 days",
        ],
        expected_sources_min=1,
    ),
]


def _build_seeded_incident_service() -> IncidentService:
    """Create a deterministic TinyDB-backed IncidentService seeded with real Incident records."""
    db = TinyDB(storage=MemoryStorage)
    repo = TinyDBIncidentRepository(db)
    service = IncidentService(repo=repo)

    repo.save(
        Incident(
            id="INC-001",
            title="Delayed pallet shipment to Zaragoza",
            description="Outbound pallet shipment delayed by 48 hours at Zaragoza regional hub.",
            category=IncidentCategory.WAREHOUSE,
            status=IncidentStatus.OPEN,
            origin=IncidentOrigin.INTERNAL,
            branch="zaragoza",
            created_at="2026-11-17T09:00:00+00:00",
            updated_at="2026-11-18T10:30:00+00:00",
            legacy_id="1001",
        )
    )
    repo.save(
        Incident(
            id="INC-002",
            title="Damaged outer carton on last-mile delivery",
            description="Customer reported water damage on carton upon delivery in Valencia.",
            category=IncidentCategory.LAST_MILE,
            status=IncidentStatus.IN_PROGRESS,
            origin=IncidentOrigin.CUSTOMER,
            branch="valencia",
            created_at="2026-11-16T12:00:00+00:00",
            updated_at="2026-11-17T15:45:00+00:00",
            legacy_id="1002",
        )
    )
    return service


def _build_seeded_inventory_service() -> InventoryService:
    """Create a deterministic SQLModel-backed InventoryService seeded with real SKU and stock records."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    repo = SQLModelInventoryRepository(session=session)
    service = InventoryService(inventory_repo=repo)

    p1 = service.create_product(
        ProductCreateDTO(
            sku="TF-1001",
            name="Industrial Thermal Shipping Label Roll",
            warehouse_id="zaragoza",
            low_stock_threshold=20,
        )
    )
    service.create_inbound_order(
        InboundOrderCreateDTO(
            sku_id=p1.id,
            warehouse_id="zaragoza",
            quantity=145,
        ),
        user_uuid="eval-seed",
    )

    p2 = service.create_product(
        ProductCreateDTO(
            sku="TF-2002",
            name="Reinforced Euro Pallet Wrap",
            warehouse_id="los_angeles",
            low_stock_threshold=50,
        )
    )
    service.create_inbound_order(
        InboundOrderCreateDTO(
            sku_id=p2.id,
            warehouse_id="los_angeles",
            quantity=12,
        ),
        user_uuid="eval-seed",
    )
    return service


@pytest.fixture(scope="module")
def seeded_support_agent_service() -> SupportAgentService:
    """Create a deterministic SupportAgentService seeded with real Qdrant chunks, TinyDB incidents, and SQLModel inventory."""
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
            "AGENT_TOOL_TIMEOUT_SECONDS": "4.0",
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

    incident_service = _build_seeded_incident_service()
    inventory_service = _build_seeded_inventory_service()

    ticket_tool = IncidentSupportTicketToolAdapter(
        incident_service=incident_service,
        config=config,
    )
    inventory_tool = InventoryStockQueryToolAdapter(
        inventory_service=inventory_service,
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
        ticket_tool=ticket_tool,
        inventory_tool=inventory_tool,
        trace_registry=registry,
        config=config,
    )


@pytest.fixture(scope="module")
def recorded_evaluation_traces(
    seeded_support_agent_service: SupportAgentService,
) -> Dict[str, AgentTrace]:
    """Generate and persist traces once so all evaluation tests run against recorded traces."""
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


# ==============================================================================
# Part 1 Evaluations: Static Policy RAG & Grounding (`EVAL-001` – `EVAL-004`)
# ==============================================================================


def test_eval_standard_policy_reasoning_flow(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """EVAL-001: Verify against recorded trace that `retrieval` ran before `generation` and cited `returns-policy`."""
    case = EVALUATION_TEST_CASES[0]
    trace = recorded_evaluation_traces[case.test_id]

    assert trace.node_sequence == case.expected_node_sequence
    assert trace.sources_consulted == ["rag"]
    assert trace.fallback_triggered is False
    assert trace.node_sequence.index("retrieval") < trace.node_sequence.index(
        "generation"
    )
    assert trace.is_refusal is case.expected_is_refusal
    assert trace.source_count >= case.expected_sources_min

    for prohibited in case.prohibited_nodes:
        assert prohibited not in trace.node_sequence
    assert set(trace.step_latencies.keys()) == {"intake", "retrieval", "generation"}

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
    """EVAL-002: Verify against recorded trace that unindexed topic routes `intake -> retrieval -> refusal` without `generation`."""
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
    """EVAL-003: Verify against recorded trace that empty/whitespace query halts at `intake -> refusal` without `retrieval` or `generation`."""
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
    """EVAL-004: Verify against recorded trace that answers remain anchored in `trackflow-BRIEFING.en.md` and policy docs."""
    case = EVALUATION_TEST_CASES[3]
    trace = recorded_evaluation_traces[case.test_id]

    assert trace.node_sequence == ["intake", "retrieval", "generation"]
    assert trace.sources_consulted == ["rag"]
    assert trace.is_refusal is False
    assert any(
        c["source_document"] == "storage-pricing"
        for c in trace.node_outputs["retrieval"]["retrieved_chunks"]
    )
    for phrase in case.expected_text_contains:
        assert phrase.lower() in trace.final_answer.lower()

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


# ==============================================================================
# Part 2 Evaluations: Operational Tools, Autonomous Routing & Fallback (`EVAL-005` – `EVAL-009`)
# ==============================================================================


def test_eval_autonomous_ticket_tool_routing(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T039 (EVAL-005): Operational question about live support ticket INC-001 is resolved via `ticket_tool` (NOT via RAG)."""
    trace = recorded_evaluation_traces["EVAL-005"]

    assert trace.sources_consulted == ["ticket_tool"]
    assert "rag" not in trace.sources_consulted
    assert trace.node_sequence == ["intake", "ticket_tool", "generation"]
    assert "retrieval" not in trace.node_sequence
    assert trace.fallback_triggered is False
    assert trace.is_refusal is False
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0]["tool_name"] == "ticket_tool"
    assert trace.tool_calls[0]["status"] == "success"
    assert trace.tool_calls[0]["total_matched"] == 1

    for expected in ("INC-001", "Delayed pallet shipment to Zaragoza", "open", "warehouse", "zaragoza"):
        assert expected.lower() in trace.final_answer.lower()


def test_eval_autonomous_rag_vs_tool_separation(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T039 (EVAL-006): Static policy question is resolved via `rag` without invoking `ticket_tool` or `inventory_tool`."""
    trace = recorded_evaluation_traces["EVAL-006"]

    assert trace.sources_consulted == ["rag"]
    assert "ticket_tool" not in trace.sources_consulted
    assert "inventory_tool" not in trace.sources_consulted
    assert trace.node_sequence == ["intake", "retrieval", "generation"]
    assert "ticket_tool" not in trace.node_sequence
    assert "inventory_tool" not in trace.node_sequence
    assert trace.tool_calls == []
    assert "30 days" in trace.final_answer
    assert trace.source_count >= 1


def test_eval_autonomous_inventory_tool_routing(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """T040 (EVAL-007): Live SKU stock question (`TF-1001`) is resolved via `inventory_tool` (NOT via RAG or `ticket_tool`)."""
    trace = recorded_evaluation_traces["EVAL-007"]

    assert trace.sources_consulted == ["inventory_tool"]
    assert trace.node_sequence == ["intake", "inventory_tool", "generation"]
    assert "retrieval" not in trace.node_sequence
    assert "ticket_tool" not in trace.node_sequence
    assert trace.fallback_triggered is False
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0]["tool_name"] == "inventory_tool"
    assert trace.tool_calls[0]["status"] == "success"
    assert "TF-1001" in trace.final_answer
    assert "145 units" in trace.final_answer


def test_eval_tool_fallback_on_missing_ticket_or_unavailable_service(
    recorded_evaluation_traces: Dict[str, AgentTrace],
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """T041 (EVAL-008): Verify honest `tool_fallback` behavior on missing ticket (`INC-999999`) and simulated unavailable/timed-out service."""
    # Sub-scenario A: Missing ticket INC-999999 from recorded matrix
    missing_trace = recorded_evaluation_traces["EVAL-008"]
    assert missing_trace.node_sequence == ["intake", "ticket_tool", "tool_fallback"]
    assert missing_trace.sources_consulted == ["ticket_tool"]
    assert missing_trace.fallback_triggered is True
    assert missing_trace.is_refusal is False
    assert len(missing_trace.tool_calls) == 1
    assert missing_trace.tool_calls[0]["status"] == "not_found"
    assert "couldn't confirm the status of ticket 'INC-999999'" in missing_trace.final_answer

    # Sub-scenario B: Simulated unavailable / timed-out incident service
    class SlowUnavailableIncidentService:
        def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
            time.sleep(0.25)
            return None

        def list_all_incidents(self, **kwargs: object) -> List[Incident]:
            time.sleep(0.25)
            return []

    timeout_ticket_tool = IncidentSupportTicketToolAdapter(
        incident_service=SlowUnavailableIncidentService(),  # type: ignore[arg-type]
        timeout_seconds=0.05,
    )
    degraded_agent = SupportAgentService(
        vector_store=seeded_support_agent_service._vector_store,
        embedding_service=seeded_support_agent_service._embedding_service,
        llm_generator=seeded_support_agent_service._llm_generator,
        ticket_tool=timeout_ticket_tool,
        inventory_tool=seeded_support_agent_service.inventory_tool,
        trace_registry=TraceRegistry(),
        config=seeded_support_agent_service.config,
    )

    timeout_result = degraded_agent.query(
        AgentQueryRequest(
            query="What is the current status of support ticket INC-001?",
            thread_id="trace-eval-008-timeout",
        )
    )
    timeout_trace = degraded_agent.get_trace("trace-eval-008-timeout")

    assert timeout_result.fallback_triggered is True
    assert timeout_trace.node_sequence == ["intake", "ticket_tool", "tool_fallback"]
    assert timeout_trace.tool_calls[0]["status"] == "timeout"
    assert "couldn't confirm the status of ticket 'INC-001' right now" in timeout_trace.final_answer
    assert "timed out" in timeout_trace.final_answer.lower()


def test_eval_hybrid_multi_source_canonical_order_and_partial_fallback(
    recorded_evaluation_traces: Dict[str, AgentTrace],
    seeded_support_agent_service: SupportAgentService,
) -> None:
    """T042 (EVAL-009): Verify canonical execution order (`ticket_tool` -> `retrieval` -> `generation`) and graceful partial answer on hybrid tool failure."""
    # Sub-scenario A: Both ticket_tool (INC-001) and RAG (return policy) succeed
    hybrid_trace = recorded_evaluation_traces["EVAL-009"]
    assert hybrid_trace.node_sequence == [
        "intake",
        "ticket_tool",
        "retrieval",
        "generation",
    ]
    assert hybrid_trace.sources_consulted == ["ticket_tool", "rag"]
    assert hybrid_trace.fallback_triggered is False
    assert "INC-001" in hybrid_trace.final_answer
    assert "30 days" in hybrid_trace.final_answer
    assert hybrid_trace.source_count >= 1

    # Sub-scenario B: Hybrid query where ticket INC-999999 is not_found while RAG succeeds
    partial_thread = "trace-eval-009-partial"
    partial_res = seeded_support_agent_service.query(
        AgentQueryRequest(
            query="What is the status of ticket INC-999999, and what is TrackFlow's standard return window?",
            thread_id=partial_thread,
        )
    )
    partial_trace = seeded_support_agent_service.get_trace(partial_thread)

    assert partial_trace.node_sequence == [
        "intake",
        "ticket_tool",
        "retrieval",
        "tool_fallback",
        "generation",
    ]
    assert partial_trace.sources_consulted == ["ticket_tool", "rag"]
    assert partial_trace.fallback_triggered is True
    assert partial_res.is_refusal is False
    assert "couldn't confirm the status of ticket 'INC-999999'" in partial_trace.final_answer
    assert "30 days" in partial_trace.final_answer
    assert partial_trace.source_count >= 1


def test_evaluation_matrix_all_scenarios_pass(
    recorded_evaluation_traces: Dict[str, AgentTrace],
) -> None:
    """Evaluate the full EVALUATION_TEST_CASES matrix (`EVAL-001` through `EVAL-009`) against recorded traces."""
    assert len(EVALUATION_TEST_CASES) >= 9
    for case in EVALUATION_TEST_CASES:
        trace = recorded_evaluation_traces[case.test_id]
        assert trace.node_sequence == case.expected_node_sequence, f"Failed {case.test_id}"
        assert trace.is_refusal is case.expected_is_refusal, f"Failed {case.test_id}"
        assert (
            trace.sources_consulted == case.expected_sources_consulted
        ), f"Failed {case.test_id}: sources_consulted={trace.sources_consulted}"
        assert (
            trace.fallback_triggered is case.expected_fallback_triggered
        ), f"Failed {case.test_id}: fallback_triggered={trace.fallback_triggered}"
        for prohibited in case.prohibited_nodes:
            assert prohibited not in trace.node_sequence, f"Failed {case.test_id}"
        assert trace.source_count >= case.expected_sources_min, f"Failed {case.test_id}"
        for expected_snippet in case.expected_text_contains:
            assert expected_snippet.lower() in trace.final_answer.lower(), (
                f"Failed {case.test_id}: missing '{expected_snippet}' in '{trace.final_answer}'"
            )
        for prohibited_snippet in case.prohibited_text_contains:
            assert prohibited_snippet.lower() not in trace.final_answer.lower(), (
                f"Failed {case.test_id}: prohibited '{prohibited_snippet}' found in '{trace.final_answer}'"
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

    grounded = rag_query(
        question=question,
        vector_store=seeded_support_agent_service._vector_store,
        embedding_service=seeded_support_agent_service._embedding_service,
        llm_generator=seeded_support_agent_service._llm_generator,
        context=contexts,
    )
    assert grounded.is_refusal is False
    assert "30 days" in grounded.answer
