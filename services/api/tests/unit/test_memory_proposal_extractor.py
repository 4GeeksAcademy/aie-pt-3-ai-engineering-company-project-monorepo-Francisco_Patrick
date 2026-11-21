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

import time
import pytest

from application.services.memory_service import (
    AgentMemoryService,
    extract_memory_candidate,
)
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
