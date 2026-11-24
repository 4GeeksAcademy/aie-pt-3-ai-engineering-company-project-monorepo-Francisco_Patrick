"""Unit tests for Synthesizer Agent policy evaluation, contradiction flagging, and sales briefing."""

from uuid import uuid4
import pytest

from data.pipelines.rfp_intake.rfp_synthesizer_agent import RFPSynthesizerAgent
from domain.rfp.entities import (
    DepartmentSection,
    ReadabilityScores,
    RFPMetadata,
)


@pytest.fixture
def synthesizer() -> RFPSynthesizerAgent:
    return RFPSynthesizerAgent()


def test_synthesizer_flags_policy_contradiction_and_builds_briefing(synthesizer: RFPSynthesizerAgent):
    """Verify synthesizer flags policy contradictions (turnaround time, unsupported services) and compiles briefing."""
    ticket_id = uuid4()
    scores = ReadabilityScores(
        flesch_reading_ease=65.2,
        flesch_kincaid_grade=8.5,
        reading_level_label="Standard",
        word_count=500,
        sentence_count=35,
    )
    metadata = RFPMetadata(
        id=uuid4(),
        ticket_id=ticket_id,
        client_name="ModaViva, S.L.",
        client_country="ES",
        currency="EUR",
        services_requested=["warehousing", "reverse_logistics"],
        monthly_volume=25000,  # Exceeds 20,000 capacity threshold
        deadline="2026-12-15",
        budget_range="€20,000/mes",
        departments_needed=["warehouse", "reverse"],
        unsupported_services=["cold storage"],
        readability_scores=scores,
    )

    section_wh = DepartmentSection(
        id=uuid4(),
        ticket_id=ticket_id,
        department_id="warehouse",
        department_name="Operaciones de Almacén",
        responsible_person="Ana Whitfield",
        key_aspects={"pallet_storage_required": None},
        open_questions=["Número de pallets no especificado."],
        policy_warnings=[],
    )

    section_rev = DepartmentSection(
        id=uuid4(),
        ticket_id=ticket_id,
        department_id="reverse",
        department_name="Logística Inversa y Devoluciones",
        responsible_person="Sofía Ramos",
        key_aspects={"return_window_days": 30},
        open_questions=["Tasa de devolución a confirmar."],
        policy_warnings=[],
    )

    markdown = "# ModaViva Proposal\nDemanda de devoluciones en 24h para clientes VIP."

    handoff = synthesizer.synthesize(ticket_id, metadata, [section_wh, section_rev], markdown)

    assert handoff.ticket_id == ticket_id
    assert handoff.schema_version == "1.0.0"
    # Contradiction 1: 24h returns turnaround
    assert any("24h" in c or "48h" in c for c in handoff.flagged_contradictions)
    # Contradiction 2: Volume > 20,000 orders/month
    assert any("20.000" in c or "25000" in c or "Capacidad" in c for c in handoff.flagged_contradictions)
    # Contradiction 3: Unsupported service cold storage
    assert any("cold storage" in c.lower() for c in handoff.flagged_contradictions)

    # Key questions should aggregate from sections
    assert "Número de pallets no especificado." in handoff.key_questions_for_prospect
    assert "Tasa de devolución a confirmar." in handoff.key_questions_for_prospect

    # Sales briefing should cite Miguel Torres and client name
    assert "ModaViva" in handoff.executive_summary
    assert any(c.name == "Miguel Torres" for c in handoff.internal_contacts)
    assert any(c.name == "Ana Whitfield" for c in handoff.internal_contacts)
    assert any(c.name == "Sofía Ramos" for c in handoff.internal_contacts)
