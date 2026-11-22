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
)
