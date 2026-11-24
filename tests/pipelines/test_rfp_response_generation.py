"""Comprehensive pipeline test suite for RFP Response Generation (Part 2 of 3).

Covers Quickstart Scenarios 1, 2, and 3 and Spec FR-017 / SC-007 requirements:
- Department generator agent tests (Warehouse, LastMile, Reverse)
- Multi-dimensional evaluator tests (passing and failing)
- Focused compliance-failure test case (returns turnaround < 48 hours -> RULE-RETURNS-TIME)
- Generator-evaluator feedback loop & iteration cap enforcement (max 3 attempts -> needs_human_review)
"""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.pipelines.test_compliance_rules import (  # noqa: E402, F401
    test_all_five_briefing_rules_registered,
    test_validate_rule_carrier_rates_blocks_negotiated_carrier_disclosure,
    test_validate_rule_currency_us_and_es,
    test_validate_rule_discount_tiers_requires_table_or_tiers,
    test_validate_rule_sla_requires_percentage_commitment,
)
from tests.pipelines.test_rfp_compliance_failures import (  # noqa: E402, F401
    test_compliance_failure_fixture_currency_mismatch_and_missing_sla,
    test_compliance_failure_fixture_returns_turnaround_under_48_hours,
)
from tests.pipelines.test_rfp_evaluators import (  # noqa: E402, F401
    test_department_section_evaluator_emits_structured_evaluation_result,
    test_evaluate_readability_fails_empty_or_too_short_draft,
    test_evaluate_readability_passes_executive_draft,
    test_evaluate_relevance_detects_missing_key_aspects,
)
from tests.pipelines.test_rfp_feedback_loop import (  # noqa: E402, F401
    test_feedback_loop_revises_failing_draft_and_passes_on_iteration_2,
)
from tests.pipelines.test_rfp_generators import (  # noqa: E402, F401
    test_factory_get_department_generator_agent,
    test_lastmile_generator_luna_cosmetics_us_usd_draft,
    test_reverse_generator_enforces_48h_minimum_turnaround,
    test_warehouse_generator_modaviva_spain_eur_draft,
)
from tests.pipelines.test_rfp_handoff_packaging import (  # noqa: E402, F401
    test_part3_handoff_payload_matches_json_schema_contract,
)
from tests.pipelines.test_rfp_iteration_cap import (  # noqa: E402, F401
    test_iteration_cap_exhaustion_escalates_to_needs_human_review_in_db,
    test_success_scenario_persists_approved_sections_and_part3_handoff_in_db,
)


def test_pipeline_executes_departments_concurrently() -> None:
    """Verify RFPResponseGenerationPipeline executes active departments in parallel using ThreadPoolExecutor."""
    import threading
    import time
    from uuid import uuid4
    from data.pipelines.rfp_intake.rfp_generator_agents import (
        BaseDepartmentGeneratorAgent,
        LastMileGeneratorAgent,
        WarehouseGeneratorAgent,
    )
    from data.pipelines.rfp_response_generation.pipeline import RFPResponseGenerationPipeline

    executed_threads = set()

    class _TrackingWarehouseAgent(BaseDepartmentGeneratorAgent):
        department_id = "warehouse"  # type: ignore[assignment]
        department_name = "Warehouse Operations"
        responsible_person = "Ana Whitfield"

        def __init__(self) -> None:
            super().__init__()
            self._base = WarehouseGeneratorAgent()

        def generate(self, rfp_metadata, section_context, feedback_for_generator=None, iteration=1) -> str:
            executed_threads.add(threading.current_thread().ident)
            time.sleep(0.05)
            return self._base.generate(rfp_metadata, section_context, feedback_for_generator, iteration)

    class _TrackingLastMileAgent(BaseDepartmentGeneratorAgent):
        department_id = "lastmile"  # type: ignore[assignment]
        department_name = "Last Mile and Carrier Management"
        responsible_person = "Carlos Vega"

        def __init__(self) -> None:
            super().__init__()
            self._base = LastMileGeneratorAgent()

        def generate(self, rfp_metadata, section_context, feedback_for_generator=None, iteration=1) -> str:
            executed_threads.add(threading.current_thread().ident)
            time.sleep(0.05)
            return self._base.generate(rfp_metadata, section_context, feedback_for_generator, iteration)

    pipeline = RFPResponseGenerationPipeline(
        generators={
            "warehouse": _TrackingWarehouseAgent(),
            "lastmile": _TrackingLastMileAgent(),
        }
    )

    handoff = pipeline.execute_from_handoff(
        ticket_id=uuid4(),
        rfp_metadata={
            "client_name": "Luna Cosmetics",
            "client_country": "US",
            "currency": "USD",
            "monthly_volume": 5000,
            "departments_needed": ["warehouse", "lastmile"],
        },
        department_sections={
            "warehouse": {
                "department_id": "warehouse",
                "key_aspects": {"warehouse_location_preference": "Los Ángeles"},
                "open_questions": [],
            },
            "lastmile": {
                "department_id": "lastmile",
                "key_aspects": {"carrier_strategy": "TrackFlow Network"},
                "open_questions": [],
            },
        },
    )

    assert handoff.overall_status == "passed"
    # Verification that multiple threads executed concurrently
    assert len(executed_threads) >= 2
