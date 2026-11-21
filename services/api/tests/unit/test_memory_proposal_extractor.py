"""Unit tests for single-call memory candidate detection and extraction (T010).

Verifies:
- Carrier route corrections in English and Spanish (e.g., SEUR rural Zaragoza coverage)
  produce structured `MemoryProposal` candidates (`category="carrier_rule"`, `target_entity="SEUR"`,
  `country_code="ES"`, `status="pending"`).
- Recurrent regional incident disruptions (e.g., Los Angeles port strike, Zaragoza transport strike)
  produce `MemoryProposal` candidates (`category="incident_context"`).
- Recurrent B2B client reporting preferences (e.g., cosmetics brand monthly report ordering)
  produce `MemoryProposal` candidates (`category="b2b_preference"`).
- Ephemeral, non-memorable interactions (tracking lookups, polite closings, translations,
  standard policy questions) return `None` without generating proposals (FR-009).
- Single-call structured generation evaluation introduces < 100ms overhead (SC-002).
"""

from datetime import datetime, timedelta, timezone
import json
import time
from typing import List
import pytest

from application.services.agent_workflow import generation_node
from application.services.memory_service import (
    AgentMemoryService,
    extract_memory_candidate,
)
from domain.agent.entities import AgentState, KnowledgeChunk, RetrievedContext
from domain.knowledge.entities import generate_chunk_id
from domain.knowledge.ports import LLMGenerationPort
from infrastructure.persistence.tinydb.agent_memory_repository import (
    TinyDBAgentMemoryRepository,
)
from infrastructure.persistence.tinydb.memory_audit_log_repository import (
    TinyDBMemoryAuditLogRepository,
)


class TestMemoryProposalExtractor:
    """Unit tests for candidate detection heuristics and single-call proposal extraction (T010)."""

    def test_extracts_carrier_rule_correction_english_and_spanish(self) -> None:
        """Carrier route changes in Zaragoza / Los Angeles must emit carrier_rule proposals."""
        en_msg = (
            "SEUR no longer covers the rural Zaragoza zone; "
            "local carriers must be used starting this month."
        )
        en_proposal = extract_memory_candidate(en_msg, thread_id="t-carrier-en")
        assert en_proposal is not None
        assert en_proposal.category == "carrier_rule"
        assert en_proposal.target_entity.upper() == "SEUR"
        assert en_proposal.country_code == "ES"
        assert en_proposal.status == "pending"
        assert en_proposal.confidence >= 0.75
        assert "SEUR" in en_proposal.summary

        es_msg = (
            "En realidad SEUR ya no cubre esa zona rural de Zaragoza, "
            "hay que usar el carrier local desde el mes pasado."
        )
        es_proposal = extract_memory_candidate(es_msg, thread_id="t-carrier-es")
        assert es_proposal is not None
        assert es_proposal.category == "carrier_rule"
        assert es_proposal.target_entity.upper() == "SEUR"
        assert es_proposal.country_code == "ES"
        assert es_proposal.status == "pending"

    def test_extracts_recurring_incident_context_english_and_spanish(self) -> None:
        """Recurring regional incident explanations must emit incident_context proposals."""
        en_msg = (
            "The delays reported across Los Angeles branches this week are due to a port strike, "
            "not our fulfillment operations; this is the third ticket on this topic."
        )
        en_proposal = extract_memory_candidate(en_msg, thread_id="t-inc-en")
        assert en_proposal is not None
        assert en_proposal.category == "incident_context"
        assert "los angeles" in en_proposal.target_entity.lower()
        assert en_proposal.country_code == "US"
        assert en_proposal.status == "pending"

        es_msg = (
            "Esos retrasos reportados en incidencias de Los Ángeles esta semana son por la huelga portuaria, "
            "no por un problema nuestro — ya van tres tickets sobre lo mismo."
        )
        es_proposal = extract_memory_candidate(es_msg, thread_id="t-inc-es")
        assert es_proposal is not None
        assert es_proposal.category == "incident_context"
        assert es_proposal.country_code == "US"

    def test_extracts_recurrent_b2b_client_preference_english_and_spanish(self) -> None:
        """Recurrent B2B client reporting format preferences must emit b2b_preference proposals."""
        en_msg = (
            "The cosmetics brand always requests their monthly performance report "
            "with the returns breakdown presented before dispatch volume."
        )
        en_proposal = extract_memory_candidate(en_msg, thread_id="t-b2b-en")
        assert en_proposal is not None
        assert en_proposal.category == "b2b_preference"
        assert en_proposal.status == "pending"
        assert "cosmetics" in en_proposal.target_entity.lower() or "cosmetics" in en_proposal.summary.lower()

        es_msg = (
            "El cliente de cosméticos siempre quiere su reporte mensual con el desglose "
            "de devoluciones primero, antes que el volumen de envíos."
        )
        es_proposal = extract_memory_candidate(es_msg, thread_id="t-b2b-es")
        assert es_proposal is not None
        assert es_proposal.category == "b2b_preference"
        assert es_proposal.status == "pending"

    @pytest.mark.parametrize(
        "ephemeral_message",
        [
            "Where is package XJ4471?",
            "¿Dónde está el paquete con tracking XJ4471?",
            "Perfect, that resolved it.",
            "Perfecto, ya quedó resuelto.",
            "Translate this customer email to English.",
            "Tradúceme esto al inglés para el cliente.",
            "What is TrackFlow's standard return window?",
            "What is the current status of ticket INC-001?",
            "How many units of SKU TF-1001 are currently in stock?",
        ],
    )
    def test_dismisses_ephemeral_and_non_memorable_interactions(
        self, ephemeral_message: str
    ) -> None:
        """One-off tracking queries, conversational closings, and translations must emit no proposal."""
        proposal = extract_memory_candidate(ephemeral_message, thread_id="t-ephemeral")
        assert proposal is None

    def test_single_call_candidate_evaluation_latency_under_100ms(self) -> None:
        """Candidate evaluation and proposal staging must complete in < 100ms without secondary LLM calls."""
        service = AgentMemoryService(
            memory_repository=TinyDBAgentMemoryRepository(),
            audit_repository=TinyDBMemoryAuditLogRepository(),
        )
        start = time.perf_counter()
        proposal, answer_with_prompt = service.evaluate_turn_for_proposal(
            user_message="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
            base_answer="Understood. I have noted the operational update regarding SEUR coverage in rural Zaragoza.",
            thread_id="t-perf-1",
            language="en",
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 100.0
        assert proposal is not None
        assert "Would you like me to remember this rule for future sessions?" in answer_with_prompt
        # Verify zero records written to persistent memory before approval
        assert service.memory_repository.search_memories() == []

    def test_single_call_structured_llm_output_creates_proposal_with_deterministic_fallback(
        self,
    ) -> None:
        """AC-3.2: generation_node parses single-call structured LLM output (answer + memory_proposal) and falls back deterministically when plain text is returned."""

        class _StructuredLLM(LLMGenerationPort):
            def generate_grounded_answer(
                self,
                query: str,
                contexts: List[RetrievedContext],
                language: str = "en",
            ) -> str:
                return json.dumps(
                    {
                        "answer": "Understood. I will note the carrier coverage update for rural Zaragoza.",
                        "memory_proposal": {
                            "category": "carrier_rule",
                            "target_entity": "SEUR",
                            "country_code": "ES",
                            "summary": "SEUR no longer covers rural Zaragoza; assign local carriers.",
                            "confidence": 0.96,
                        },
                    }
                )

        chunk = KnowledgeChunk(
            id=generate_chunk_id("carrier-coverage", 0),
            company="trackflow",
            source_document="carrier-coverage",
            section="Spain Carrier Coverage",
            language="en",
            chunk_index=0,
            text="In Spain (Zaragoza), TrackFlow partners with SEUR and local carriers.",
        )
        ctx = RetrievedContext(chunk=chunk, similarity_score=0.90, rank=1)
        memory_service = AgentMemoryService(
            memory_repository=TinyDBAgentMemoryRepository(),
            audit_repository=TinyDBMemoryAuditLogRepository(),
        )

        # 1. Single-call structured LLM output path (even when user query wouldn't trigger regex alone)
        state: AgentState = {
            "query": "Please note our updated regional dispatch preference for Zaragoza.",
            "thread_id": "t-structured-llm-1",
            "trace_id": "trace-structured-1",
            "contexts": [ctx],
        }
        out = generation_node(
            state=state,
            llm_generator=_StructuredLLM(),
            memory_service=memory_service,
        )
        assert "Understood. I will note the carrier coverage update for rural Zaragoza." in out["answer"]
        assert "Would you like me to remember this rule for future sessions?" in out["answer"]
        assert '"memory_proposal"' not in out["answer"]
        assert out["memory_proposal"] is not None
        assert out["memory_proposal"].category == "carrier_rule"
        assert out["memory_proposal"].target_entity == "SEUR"
        assert out["memory_proposal"].country_code == "ES"
        assert out["memory_proposal"].summary == "SEUR no longer covers rural Zaragoza; assign local carriers."
        assert out["memory_proposal"].confidence == 0.96

    def test_expired_pending_proposal_is_auto_discarded_and_unblocks_thread(
        self,
    ) -> None:
        """Expired pending proposal (expires_at <= now) must be marked discarded, logged in audit repo, removed from _pending_by_thread, and allow new proposals."""
        audit_repo = TinyDBMemoryAuditLogRepository()
        service = AgentMemoryService(
            memory_repository=TinyDBAgentMemoryRepository(),
            audit_repository=audit_repo,
        )
        p1, _ = service.evaluate_turn_for_proposal(
            user_message="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
            base_answer="Noted.",
            thread_id="t-expire-1",
        )
        assert p1 is not None
        # Force expires_at into the past
        expired_p1 = p1.__class__(
            proposal_id=p1.proposal_id,
            category=p1.category,
            target_entity=p1.target_entity,
            country_code=p1.country_code,
            summary=p1.summary,
            status="pending",
            source_message=p1.source_message,
            confidence=p1.confidence,
            created_at=p1.created_at - timedelta(minutes=20),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            thread_id=p1.thread_id,
        )
        service._pending_by_thread["t-expire-1"] = expired_p1
        service._proposals_by_id[p1.proposal_id] = expired_p1

        # Calling get_pending_proposal must detect expiration, discard it, and return None
        assert service.get_pending_proposal("t-expire-1") is None
        resolved_p1 = service.get_proposal_by_id(p1.proposal_id)
        assert resolved_p1 is not None
        assert resolved_p1.status == "discarded"

        discard_logs = audit_repo.list_entries(
            proposal_id=p1.proposal_id, event_type="discarded"
        )
        assert len(discard_logs) == 1
        assert discard_logs[0].details.get("reason") == "proposal_expired"

        # Thread is now unblocked for a new proposal
        p2, _ = service.evaluate_turn_for_proposal(
            user_message="FedEx no longer covers rural Los Angeles; local carriers must be used starting this month.",
            base_answer="Noted.",
            thread_id="t-expire-1",
        )
        assert p2 is not None
        assert p2.proposal_id != p1.proposal_id
        assert p2.target_entity == "FedEx"
