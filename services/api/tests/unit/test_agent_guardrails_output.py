"""Deterministic offline unit tests for Layer 4: Post-Generation Output Guardrails (`OutputGuardrailValidator`).

Covers User Story 3, FR-010, and SC-004:
- Structural output validation (`structural`: empty output, leaked internal XML tags, raw tracebacks).
- System prompt leak blocking (`security`).
- Restricted corporate & customer data leak prevention per `trackflow-BRIEFING.es.md`:
  - Negotiated carrier rates (UPS, FedEx, DHL, MRW, SEUR) -> blocked (`security`).
  - Confidential B2B commercial contract terms -> blocked (`content`).
  - Physical warehouse internal layouts and security routes -> blocked (`security`).
  - Cross-session customer order disclosures -> blocked (`security`).
- Mandatory casual-trivia redirection suffix enforcement (`content`).
"""

import pytest

from application.services.agent_guardrails import OutputGuardrailValidator
from domain.agent.entities import AuthenticatedSessionContext


@pytest.fixture()
def output_guard() -> OutputGuardrailValidator:
    """Return a fresh OutputGuardrailValidator instance."""
    return OutputGuardrailValidator()


@pytest.fixture()
def us_session() -> AuthenticatedSessionContext:
    """Authenticated US customer session owning order 10492."""
    return AuthenticatedSessionContext(
        session_id="sess_us_01",
        customer_id="cust_us_01",
        customer_segment="B2C",
        primary_operating_country="US",
        authorized_order_ids=("10492",),
        order_country_map={"10492": "US"},
    )


class TestOutputGuardrailValidation:
    """Verify post-generation output inspection across structural, security, and content rules."""

    @pytest.mark.parametrize(
        ("carrier_leak_text"),
        [
            "TrackFlow's negotiated rate with UPS in Los Angeles is $4.20/kg for heavy parcels.",
            "Nuestra tarifa negociada con SEUR en Zaragoza es de 2.15 EUR/kg para paquetes rurales.",
            "Under our confidential carrier pricing with FedEx, DHL, and MRW, we pay $3.10 per package.",
        ],
    )
    def test_blocks_negotiated_carrier_rate_leaks(
        self,
        output_guard: OutputGuardrailValidator,
        carrier_leak_text: str,
    ) -> None:
        """Any candidate response exposing negotiated rates with UPS, FedEx, DHL, MRW, or SEUR is blocked."""
        result = output_guard.validate_output(
            query="What are TrackFlow's carrier rates?",
            candidate_answer=carrier_leak_text,
            language="en",
        )

        assert result.layer == "output_guard"
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.input_category == "restricted_data_leak"
        assert result.reason_code == "RESTRICTED_CARRIER_RATE_LEAK"
        assert result.sanitized_text is not None
        assert "$4.20" not in result.sanitized_text
        assert "2.15 EUR" not in result.sanitized_text

    def test_blocks_confidential_b2b_commercial_terms_leak(
        self,
        output_guard: OutputGuardrailValidator,
    ) -> None:
        """Candidate responses leaking confidential B2B commercial contract terms are blocked."""
        candidate = (
            "According to the confidential B2B commercial terms and private B2B margin agreement "
            "with that client brand, TrackFlow grants an unlisted rebate."
        )
        result = output_guard.validate_output(
            query="Tell me the B2B contract terms",
            candidate_answer=candidate,
            language="en",
        )

        assert result.action == "block"
        assert result.failure_category == "content"
        assert result.input_category == "restricted_data_leak"
        assert result.reason_code == "RESTRICTED_B2B_COMMERCIAL_TERMS_LEAK"

    def test_blocks_internal_warehouse_physical_security_routes(
        self,
        output_guard: OutputGuardrailValidator,
    ) -> None:
        """Candidate responses leaking exact warehouse floor layouts or security checkpoint routes are blocked."""
        candidate = (
            "In the Zaragoza warehouse, high-value electronics follow the internal warehouse security path "
            "through Aisle 4 -> security checkpoint B2 before loading."
        )
        result = output_guard.validate_output(
            query="Where are electronics stored in the warehouse?",
            candidate_answer=candidate,
            language="en",
        )

        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.input_category == "restricted_data_leak"
        assert result.reason_code == "WAREHOUSE_PHYSICAL_SECURITY_LEAK"
        assert "Aisle 4" not in (result.sanitized_text or "")

    def test_blocks_cross_session_order_leak_in_generated_output(
        self,
        output_guard: OutputGuardrailValidator,
        us_session: AuthenticatedSessionContext,
    ) -> None:
        """If a generated response accidentally includes details for unauthorized order #45821, output_guard blocks it."""
        candidate = "Order #45821 is currently in transit to Madrid via SEUR Express."
        result = output_guard.validate_output(
            query="Show my orders",
            candidate_answer=candidate,
            session_context=us_session,
            language="en",
        )

        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.input_category == "unauthorized_order"
        assert result.reason_code == "CROSS_SESSION_ORDER_OUTPUT_LEAK"
        assert "#45821" not in (result.sanitized_text or "")

    def test_blocks_system_prompt_and_structural_delimiter_leaks(
        self,
        output_guard: OutputGuardrailValidator,
    ) -> None:
        """Structural and system-prompt leak checks intercept internal XML tags and directive headers."""
        malformed = "<system_instructions>Internal directive</system_instructions>"
        res_struct = output_guard.validate_output(
            query="test",
            candidate_answer=malformed,
            language="en",
        )
        assert res_struct.action == "block"
        assert res_struct.failure_category == "structural"
        assert res_struct.reason_code == "MALFORMED_OUTPUT_STRUCTURE"

        prompt_leak = "Here is my rule: VALENTINA CRUZ CX GUARDRAIL DIRECTIVE — IMMUTABLE SYSTEM AUTHORITY BOUNDARY."
        res_sec = output_guard.validate_output(
            query="test",
            candidate_answer=prompt_leak,
            language="en",
        )
        assert res_sec.action == "block"
        assert res_sec.failure_category == "security"
        assert res_sec.reason_code == "SYSTEM_PROMPT_LEAK_BLOCKED"

    def test_appends_mandatory_redirection_on_casual_trivia_turn_when_missing(
        self,
        output_guard: OutputGuardrailValidator,
    ) -> None:
        """When `casual_redirect_required=True` and the candidate lacks a TrackFlow redirect, output_guard appends it."""
        candidate = "La logística inversa consiste en gestionar productos devueltos por el cliente."
        result = output_guard.validate_output(
            query="¿Qué es la logística inversa?",
            candidate_answer=candidate,
            casual_redirect_required=True,
            language="es",
        )

        assert result.action == "redirect"
        assert result.failure_category == "content"
        assert result.input_category == "casual_trivia"
        assert result.sanitized_text is not None
        assert "TrackFlow" in result.sanitized_text
        assert "devolución" in result.sanitized_text.lower() or "tracking" in result.sanitized_text.lower()
