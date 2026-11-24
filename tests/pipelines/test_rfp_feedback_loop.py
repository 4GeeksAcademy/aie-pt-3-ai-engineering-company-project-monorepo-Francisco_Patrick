"""Unit tests for the generator-evaluator revision feedback loop (User Story 3 - T024)."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, Optional
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_intake.rfp_generator_agents import (  # noqa: E402
    BaseDepartmentGeneratorAgent,
    LastMileGeneratorAgent,
    ReverseLogisticsGeneratorAgent,
    WarehouseGeneratorAgent,
)
from data.pipelines.rfp_response_generation.pipeline import (  # noqa: E402
    RFPResponseGenerationPipeline,
)


def _strip_revision_note(draft: str) -> str:
    """Return the main draft body before Section 5 (Revision Note)."""
    marker = "### 5. Revision Note"
    if marker in draft:
        return draft.split(marker, 1)[0].strip()
    return draft.strip()


class _SelfCorrectingReverseGenerator(BaseDepartmentGeneratorAgent):
    """Generator fixture that violates RULE-RETURNS-TIME on attempt 1 and fixes it on attempt 2."""

    department_id = "reverse"  # type: ignore[assignment]
    department_name = "Reverse Logistics"
    responsible_person = "Sofía Ramos"

    def __init__(self) -> None:
        super().__init__()
        self.received_feedback: list[Optional[str]] = []
        self._delegate = ReverseLogisticsGeneratorAgent()

    def generate(
        self,
        rfp_metadata: Dict[str, Any],
        section_context: Dict[str, Any],
        feedback_for_generator: Optional[str] = None,
        iteration: int = 1,
    ) -> str:
        self.received_feedback.append(feedback_for_generator)
        base_draft = self._delegate.generate(
            rfp_metadata=rfp_metadata,
            section_context=section_context,
            feedback_for_generator=feedback_for_generator,
            iteration=iteration,
        )
        if iteration == 1:
            # Inject a 24-hour return turnaround violation on attempt 1
            return base_draft + "\n\nSpecial note: we promise return processing in 24 hours."
        # On attempt 2, after receiving RULE-RETURNS-TIME feedback, emit compliant draft
        return base_draft


def test_feedback_loop_revises_failing_draft_and_passes_on_iteration_2() -> None:
    """Verify failing draft on attempt 1 receives feedback_for_generator and passes on attempt 2."""
    correcting_reverse = _SelfCorrectingReverseGenerator()
    pipeline = RFPResponseGenerationPipeline(
        generators={
            "warehouse": WarehouseGeneratorAgent(),
            "reverse": correcting_reverse,
        },
        max_attempts=3,
    )

    ticket_id = uuid4()
    rfp_metadata = {
        "client_name": "ModaViva, S.L.",
        "client_country": "ES",
        "currency": "EUR",
        "monthly_volume": 3500,
        "departments_needed": ["warehouse", "reverse"],
    }
    sections_ctx = {
        "warehouse": {
            "department_id": "warehouse",
            "key_aspects": {
                "warehouse_location_preference": "Zaragoza",
                "sku_count": 400,
                "onboarding_complexity": "Baja",
            },
            "open_questions": [],
        },
        "reverse": {
            "department_id": "reverse",
            "key_aspects": {
                "return_window_days": 30,
                "estimated_return_rate": 0.15,
                "inspection_required": True,
                "disposition_flow": ["reventa", "reacondicionamiento", "descarte"],
            },
            "open_questions": [],
        },
    }

    handoff = pipeline.execute_from_handoff(
        ticket_id=ticket_id,
        rfp_metadata=rfp_metadata,
        department_sections=sections_ctx,
    )

    assert handoff.overall_status == "passed"
    # Warehouse passed on iteration 1 and did NOT re-run
    assert handoff.department_sections["warehouse"]["iteration"] == 1
    assert handoff.department_sections["warehouse"]["status"] == "passed"

    # Reverse failed attempt 1, received feedback, and passed on iteration 2
    assert handoff.department_sections["reverse"]["iteration"] == 2
    assert handoff.department_sections["reverse"]["status"] == "passed"
    assert len(correcting_reverse.received_feedback) == 2
    assert correcting_reverse.received_feedback[0] is None
    assert correcting_reverse.received_feedback[1] is not None
    assert "RULE-RETURNS-TIME" in correcting_reverse.received_feedback[1]


def test_real_generators_actively_consume_feedback_on_revision() -> None:
    """Verify real generator agents actively mutate the main draft body (Sections 1-4) on iteration > 1."""
    rfp_metadata = {
        "client_name": "ModaViva, S.L.",
        "client_country": "ES",
        "currency": "EUR",
        "monthly_volume": 3500,
        "departments_needed": ["warehouse", "lastmile", "reverse"],
    }

    # 1. Warehouse generator: compare iteration 1 body vs. iteration 2 body (minus Revision Note)
    wh_agent = WarehouseGeneratorAgent()
    wh_ctx = {
        "department_id": "warehouse",
        "key_aspects": {
            "warehouse_location_preference": "Zaragoza",
            "pallet_storage_required": None,
            "sku_count": 450,
            "client_requested_quote": "$99.00 USD custom storage quote",
        },
        "open_questions": [],
    }
    wh_draft_iter_1 = wh_agent.generate(
        rfp_metadata=rfp_metadata,
        section_context=wh_ctx,
        iteration=1,
    )
    wh_draft_iter_2 = wh_agent.generate(
        rfp_metadata=rfp_metadata,
        section_context=wh_ctx,
        feedback_for_generator=(
            "[COMPLIANCE CRITICAL] Violates RULE-CURRENCY: draft contains USD ($) pricing. "
            "[COMPLIANCE CRITICAL] Violates RULE-SLA: committed 90% SLA missing. "
            "[RELEVANCE] Address the following missing Part 1 key aspects in the proposal section: "
            "special_handling, open_questions_coverage."
        ),
        iteration=2,
    )
    wh_body_1 = _strip_revision_note(wh_draft_iter_1)
    wh_body_2 = _strip_revision_note(wh_draft_iter_2)

    assert wh_body_2 != wh_body_1
    assert "USD" in wh_body_1  # Iteration 1 leaked the raw USD aspect value
    assert "USD" not in wh_body_2  # Iteration 2 actively sanitized foreign currency in the body
    assert "5% monthly tariff compensation" in wh_body_2
    assert "Addressed operational parameter special handling" in wh_body_2
    assert "### 4. Open Questions" in wh_body_2

    # 2. Last Mile generator: compare iteration 1 body vs. iteration 2 body (minus Revision Note)
    lm_agent = LastMileGeneratorAgent()
    lm_ctx = {
        "department_id": "lastmile",
        "key_aspects": {
            "carrier_strategy": "TrackFlow Network",
            "geographic_scope": "Domestic ES",
        },
        "open_questions": [],
    }
    lm_draft_iter_1 = lm_agent.generate(
        rfp_metadata=rfp_metadata,
        section_context=lm_ctx,
        iteration=1,
    )
    lm_draft_iter_2 = lm_agent.generate(
        rfp_metadata=rfp_metadata,
        section_context=lm_ctx,
        feedback_for_generator=(
            "[COMPLIANCE CRITICAL] Violates RULE-SLA: committed 90% SLA missing. "
            "[COMPLIANCE CRITICAL] Violates RULE-CARRIER-RATES: never disclose internal carrier rates."
        ),
        iteration=2,
    )
    lm_body_1 = _strip_revision_note(lm_draft_iter_1)
    lm_body_2 = _strip_revision_note(lm_draft_iter_2)

    assert lm_body_2 != lm_body_1
    assert "5% monthly tariff compensation" in lm_body_2
    assert "Rate confidentiality update" in lm_body_2

    # 3. Reverse Logistics generator: compare iteration 1 body vs. iteration 2 body
    # Also test end-to-end pipeline self-correction using the REAL ReverseLogisticsGeneratorAgent
    rev_agent = ReverseLogisticsGeneratorAgent()
    rev_ctx = {
        "department_id": "reverse",
        "key_aspects": {
            "return_window_days": 30,
            "estimated_return_rate": 0.15,
            "inspection_required": True,
            "disposition_flow": ["reventa", "reacondicionamiento", "descarte"],
            "client_requested_turnaround": "return processing in 24 hours",
        },
        "open_questions": [],
    }
    rev_draft_iter_1 = rev_agent.generate(
        rfp_metadata=rfp_metadata,
        section_context=rev_ctx,
        iteration=1,
    )
    rev_draft_iter_2 = rev_agent.generate(
        rfp_metadata=rfp_metadata,
        section_context=rev_ctx,
        feedback_for_generator="[COMPLIANCE CRITICAL] Violates RULE-RETURNS-TIME: returns promised under 48h.",
        iteration=2,
    )
    rev_body_1 = _strip_revision_note(rev_draft_iter_1)
    rev_body_2 = _strip_revision_note(rev_draft_iter_2)

    assert rev_body_2 != rev_body_1
    assert "24 hours" in rev_body_1
    assert "24 hours" not in rev_body_2
    assert "Turnaround compliance update" in rev_body_2

    # Verify the real ReverseLogisticsGeneratorAgent recovers in the pipeline from iteration 1 failure to iteration 2 pass
    real_pipeline = RFPResponseGenerationPipeline(max_attempts=3)
    outcome = real_pipeline.run_department_loop(
        ticket_id=uuid4(),
        department_id="reverse",
        rfp_metadata=rfp_metadata,
        section_context=rev_ctx,
    )
    assert outcome.iteration == 2
    assert outcome.status == "passed"
    assert outcome.evaluation_history[0].overall_pass is False
    assert "RULE-RETURNS-TIME" in outcome.evaluation_history[0].compliance.rule_ids
    assert outcome.evaluation_history[1].overall_pass is True
