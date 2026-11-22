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

from application.agent.rfp_generator_agents import (  # noqa: E402
    BaseDepartmentGeneratorAgent,
    ReverseLogisticsGeneratorAgent,
    WarehouseGeneratorAgent,
)
from data.pipelines.rfp_response_generation.pipeline import (  # noqa: E402
    RFPResponseGenerationPipeline,
)


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
