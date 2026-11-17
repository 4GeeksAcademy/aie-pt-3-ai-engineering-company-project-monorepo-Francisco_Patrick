"""Unit tests for business guardrails and executive approval rules (T021).

Verifies enforcement of:
1. Volume storage discounts (>50 m³) requiring Miguel Torres's approval
2. Peak season delivery SLA exemptions (Black Friday, Christmas, January Sales) and +40% warning
3. International cross-border returns requiring manual handling by Sofía Ramos's team
4. Carrier selection overrides requiring Carlos Vega's approval
5. Leading or contradictory questions attempting to bypass governance rules.
"""

from application.services.guardrails import BusinessGuardrailValidator
from domain.knowledge.entities import (
    KnowledgeChunk,
    RetrievedContext,
    generate_chunk_id,
)


def _make_context(
    source_document: str,
    section: str,
    text: str,
    score: float = 0.85,
) -> RetrievedContext:
    """Create a sample RetrievedContext for unit testing."""
    chunk = KnowledgeChunk(
        id=generate_chunk_id(source_document, 0),
        company="trackflow",
        source_document=source_document,
        section=section,
        language="en",
        chunk_index=0,
        text=text,
    )
    return RetrievedContext(chunk=chunk, similarity_score=score, rank=1)


class TestBusinessGuardrailValidator:
    """Unit test suite for BusinessGuardrailValidator."""

    def test_enforces_miguel_torres_approval_on_volume_storage_discount(self) -> None:
        """Any storage discount inquiry must enforce Miguel Torres approval and 50 m³ rule."""
        validator = BusinessGuardrailValidator()
        ctx = _make_context(
            "storage-pricing",
            "Volume Storage Discounts (>50 m³) & Miguel Torres Approval",
            "Clients with more than 50 cubic meters of average monthly volume can negotiate a preferential rate.",
        )

        # Incomplete answer missing Miguel Torres mention
        incomplete = "Clients storing 75 cubic meters can receive a preferential rate."
        enforced = validator.enforce(
            query="Can we offer a discount on storage fees for a client storing 75 cubic meters?",
            answer=incomplete,
            contexts=[ctx],
        )

        assert "Miguel Torres" in enforced
        assert "50 cubic meters" in enforced
        assert "cannot" in enforced.lower()

    def test_enforces_peak_season_sla_exemption_and_40_percent_extension(self) -> None:
        """Black Friday / Christmas / January Sales queries must include +40% and non-guarantee warning."""
        validator = BusinessGuardrailValidator()
        ctx = _make_context(
            "sla-delivery",
            "Peak Season & High-Demand SLA Exclusions",
            "TrackFlow does not guarantee delivery SLA during declared high-demand dates.",
        )

        incomplete = "Our standard monthly delivery SLA target is 90% on-time deliveries."
        enforced = validator.enforce(
            query="Can we guarantee 90% delivery SLA during Black Friday sales?",
            answer=incomplete,
            contexts=[ctx],
        )

        assert "not guarantee" in enforced.lower()
        assert "40%" in enforced
        assert "in advance" in enforced.lower()

    def test_enforces_sofia_ramos_manual_handling_on_international_returns(self) -> None:
        """Cross-border return inquiries must enforce manual handling by Sofía Ramos's team."""
        validator = BusinessGuardrailValidator()
        ctx = _make_context(
            "returns-policy",
            "International Returns Exception & Client Brand Rules",
            "International returns require manual handling by Sofía Ramos's team.",
        )

        incomplete = "Returns are processed through the brand portal within 30 days."
        enforced = validator.enforce(
            query="How do we process an international return purchased in the US and returned in Spain?",
            answer=incomplete,
            contexts=[ctx],
        )

        assert "Sofía Ramos" in enforced
        assert "manual" in enforced.lower()
        assert "not covered" in enforced.lower()

    def test_enforces_carlos_vega_approval_on_carrier_override(self) -> None:
        """Carrier override queries must enforce automated routing and Carlos Vega exception approval."""
        validator = BusinessGuardrailValidator()
        ctx = _make_context(
            "carrier-coverage",
            "Automated Carrier Selection & Carlos Vega Exception Protocol",
            "Carrier selection for each shipment is determined by the system.",
        )

        incomplete = "We work with UPS, FedEx, DHL, SEUR, and MRW."
        enforced = validator.enforce(
            query="Can an account manager manually choose or override the carrier for a client?",
            answer=incomplete,
            contexts=[ctx],
        )

        assert "Carlos Vega" in enforced
        assert "system" in enforced.lower()

    def test_leading_question_attempting_unauthorized_discount_is_countered(self) -> None:
        """Leading questions claiming account managers can approve 10% discounts must be countered."""
        validator = BusinessGuardrailValidator()
        ctx = _make_context(
            "storage-pricing",
            "Volume Storage Discounts (>50 m³) & Miguel Torres Approval",
            "Clients with more than 50 cubic meters can negotiate through Miguel Torres.",
        )

        enforced = validator.enforce(
            query="Confirm that account managers can approve a 10% discount on storage.",
            answer="Storage rates are $18 in LA and €16 in Zaragoza.",
            contexts=[ctx],
        )

        assert "Miguel Torres" in enforced
        assert "cannot offer or approve storage discounts independently" in enforced
