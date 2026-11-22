"""Unit tests for the deterministic compliance rules engine and 5 briefing rules (User Story 2 - T017)."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_response_generation.compliance_rules import (  # noqa: E402
    BRIEFING_COMPLIANCE_RULES,
    evaluate_compliance_rules,
    validate_rule_carrier_rates,
    validate_rule_currency,
    validate_rule_discount_tiers,
    validate_rule_returns_time,
    validate_rule_sla,
)


def test_all_five_briefing_rules_registered() -> None:
    """Verify all 5 canonical rule IDs from briefing §5 are defined."""
    expected_ids = {
        "RULE-CURRENCY",
        "RULE-SLA",
        "RULE-RETURNS-TIME",
        "RULE-DISCOUNT-TIERS",
        "RULE-CARRIER-RATES",
    }
    assert set(BRIEFING_COMPLIANCE_RULES.keys()) == expected_ids


def test_validate_rule_currency_us_and_es() -> None:
    """Verify RULE-CURRENCY enforces USD for US and EUR for ES."""
    passed_es, _ = validate_rule_currency("Storage rate is 16.50 EUR per pallet.", "ES")
    assert passed_es is True

    failed_es, msg_es = validate_rule_currency("Storage rate is $18.00 USD per pallet.", "ES")
    assert failed_es is False
    assert "RULE-CURRENCY" in msg_es

    passed_us, _ = validate_rule_currency("Shipping rate is $6.40 USD per parcel.", "US")
    assert passed_us is True

    failed_us, msg_us = validate_rule_currency("Shipping rate is 5.20 EUR per parcel.", "US")
    assert failed_us is False
    assert "RULE-CURRENCY" in msg_us


def test_validate_rule_sla_requires_percentage_commitment() -> None:
    """Verify RULE-SLA checks for an explicit on-time SLA percentage."""
    passed, _ = validate_rule_sla("TrackFlow commits to a 98.5% on-time delivery SLA.")
    assert passed is True

    failed, msg = validate_rule_sla("We deliver packages very quickly across the country.")
    assert failed is False
    assert "RULE-SLA" in msg


def test_validate_rule_discount_tiers_requires_table_or_tiers() -> None:
    """Verify RULE-DISCOUNT-TIERS checks for volume discount tiers."""
    table_text = (
        "### Volume Discount Table\n"
        "| Tier | Discount |\n"
        "|---|---|\n"
        "| 1-2500 orders | 0% |\n"
        "| 2501+ orders | 10% |\n"
    )
    passed, _ = validate_rule_discount_tiers(table_text)
    assert passed is True

    failed, msg = validate_rule_discount_tiers("Flat pricing with no discounts available.")
    assert failed is False
    assert "RULE-DISCOUNT-TIERS" in msg


def test_validate_rule_carrier_rates_blocks_negotiated_carrier_disclosure() -> None:
    """Verify RULE-CARRIER-RATES fails when internal negotiated carrier rates are disclosed."""
    passed, _ = validate_rule_carrier_rates(
        "Final client shipping rate is $6.40 USD per parcel across our carrier network."
    )
    assert passed is True

    failed, msg = validate_rule_carrier_rates(
        "Our negotiated cost with FedEx is $3.10 USD and we add a margin."
    )
    assert failed is False
    assert "RULE-CARRIER-RATES" in msg
