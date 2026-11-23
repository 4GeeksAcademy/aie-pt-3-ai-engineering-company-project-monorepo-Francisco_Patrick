"""Focused tests for compliance-failure fixtures (User Story 2 - T018, Spec FR-017)."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_response_generation.evaluator import (  # noqa: E402
    DepartmentSectionEvaluator,
)


def test_compliance_failure_fixture_returns_turnaround_under_48_hours() -> None:
    """Focused test (FR-017 / AC-3.3): Draft promising 24-hour return processing fails with RULE-RETURNS-TIME."""
    non_compliant_reverse_draft = """
    ## Reverse Logistics Proposal — ModaViva, S.L.
    TrackFlow supports a 30 days return window for an estimated return rate of 18.0%.
    Every item undergoes manual quality inspection and disposition flow: reventa, reacondicionamiento, descarte.
    We promise ultra-fast return processing in 24 hours from receipt at our Zaragoza hub.
    TrackFlow commits to a canonical 90% on-time delivery and returns SLA.
    Inspection rate: 2.40 EUR per unit.

    ### Volume Discount Table
    Commercial governance: Pre-aprobado por Miguel Torres.
    | Volume Tier | Discount |
    |---|---|
    | 1 - 2,500 orders | 0% |
    | 2,501+ orders | 10% |
    """

    evaluator = DepartmentSectionEvaluator()
    result = evaluator.evaluate(
        department_id="reverse",
        draft_text=non_compliant_reverse_draft,
        client_country="ES",
        key_aspects={
            "return_window_days": 30,
            "estimated_return_rate": 0.18,
            "inspection_required": True,
            "disposition_flow": ["reventa", "reacondicionamiento", "descarte"],
        },
        iteration=1,
    )

    assert result.compliance.pass_status is False
    assert getattr(result.compliance, "pass") is False
    assert "RULE-RETURNS-TIME" in result.compliance.rule_ids
    assert result.overall_pass is False
    assert "RULE-RETURNS-TIME" in result.feedback_for_generator


def test_compliance_failure_fixture_currency_mismatch_and_missing_sla() -> None:
    """Verify draft quoting USD for a Spanish client and omitting SLA percentage fails both rules."""
    non_compliant_draft = """
    ## Warehouse Operations Proposal — ModaViva, S.L.
    Facility in Zaragoza with 400 SKUs and low onboarding complexity.
    Pallet storage rate is $18.00 USD per month.
    We provide fast fulfillment services without a specific percentage commitment.
    """

    evaluator = DepartmentSectionEvaluator()
    result = evaluator.evaluate(
        department_id="warehouse",
        draft_text=non_compliant_draft,
        client_country="ES",
        key_aspects={"warehouse_location_preference": "Zaragoza", "sku_count": 400},
        iteration=1,
    )

    assert result.compliance.pass_status is False
    assert "RULE-CURRENCY" in result.compliance.rule_ids
    assert "RULE-SLA" in result.compliance.rule_ids
    assert "RULE-DISCOUNT-TIERS" in result.compliance.rule_ids
    assert result.overall_pass is False
