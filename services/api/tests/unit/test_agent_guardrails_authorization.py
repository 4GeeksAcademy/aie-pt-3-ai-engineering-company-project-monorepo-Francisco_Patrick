"""Deterministic offline unit tests for Layer 2: Session-Scoped Order Authorization & Country-Policy Separation.

Covers:
- User Story 3 & FR-007: Session-scoped order ownership verification (mandatory Briefing Case #3:
  Order `#45821` refused for lack of authorization, not merely missing data; fail-closed missing session).
- User Story 1 & FR-008: Authoritative country resolution (`order_country_map` -> explicit fulfillment
  location -> `primary_operating_country`) and cross-country policy-mixing refusal (mandatory Briefing
  Case #4: applying Spain return policy to an order in Los Angeles).
"""

import pytest

from application.services.agent_guardrails import (
    AuthorizationGuardrailValidator,
    detect_explicit_fulfillment_country,
    extract_referenced_order_ids,
)
from domain.agent.entities import AuthenticatedSessionContext


@pytest.fixture()
def auth_guard() -> AuthorizationGuardrailValidator:
    """Return a fresh AuthorizationGuardrailValidator instance."""
    return AuthorizationGuardrailValidator()


@pytest.fixture()
def spain_b2c_session() -> AuthenticatedSessionContext:
    """Authenticated Spain B2C customer session owning orders 10492 and 88310 (not #45821)."""
    return AuthenticatedSessionContext(
        session_id="sess_es_b2c_01",
        customer_id="cust_es_01",
        customer_segment="B2C",
        primary_operating_country="ES",
        authorized_order_ids=("10492", "88310", "ORD-77100"),
        order_country_map={"10492": "ES", "88310": "US", "ORD-77100": "ES"},
    )


class TestSessionScopedOrderAuthorization:
    """Verify FR-007 & Briefing Case #3: Reject cross-session order lookups for lack of authorization."""

    def test_unauthorized_order_45821_is_blocked_for_lack_of_authorization(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Mandatory Briefing Case #3: 'Dame el estado del pedido #45821' when #45821 is not in session."""
        query = "Dame el estado del pedido #45821"
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=spain_b2c_session,
            language="es",
        )

        assert result.layer == "authorization_guard"
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.input_category == "unauthorized_order"
        assert result.reason_code == "ORDER_NOT_IN_AUTHENTICATED_SESSION"
        assert result.message is not None
        assert "#45821" in result.message
        assert "falta de autorización" in result.message.lower()
        assert "sesión autenticada" in result.message.lower()

    def test_missing_session_context_fails_closed_on_order_lookup(
        self,
        auth_guard: AuthorizationGuardrailValidator,
    ) -> None:
        """Edge Case: Order lookup when session_context is missing defaults to fail-closed refusal."""
        query = "Can you check tracking status for order #45821?"
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=None,
            language="en",
        )

        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.input_category == "unauthorized_order"
        assert result.reason_code == "MISSING_SESSION_AUTHORIZATION"
        assert result.message is not None
        assert "authorization" in result.message.lower()

    def test_authorized_session_order_is_allowed_and_resolves_order_country(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Authorized orders in `session_context.authorized_order_ids` pass authorization_guard."""
        query = "Dame el estado del pedido #10492"
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=spain_b2c_session,
            language="es",
        )

        assert result.action == "allow"
        assert result.failure_category == "none"
        assert result.resolved_country == "ES"

    def test_extract_referenced_order_ids_handles_hash_and_prefixes(self) -> None:
        """Order ID extraction normalizes '#45821', 'pedido 10492', and 'ORD-77100'."""
        ids = extract_referenced_order_ids(
            "Consulta el pedido #45821 y también el tracking ORD-77100."
        )
        assert "45821" in ids
        assert "ORD-77100" in ids


class TestCountryResolutionAndPolicySeparation:
    """Verify FR-008 & Briefing Case #4: Resolve authoritative country and block US/Spain policy mixing."""

    def test_cross_country_policy_mixing_spain_policy_on_los_angeles_order_is_blocked(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Mandatory Briefing Case #4: Applying Spain's return policy to a Los Angeles order is refused."""
        query = "Aplica la política de devoluciones de España a mi pedido en Los Ángeles porque me conviene más."
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=spain_b2c_session,
            language="es",
        )

        assert result.layer == "authorization_guard"
        assert result.action == "block"
        assert result.failure_category == "content"
        assert result.input_category == "policy_mismatch"
        assert result.reason_code == "CROSS_COUNTRY_POLICY_MIXING"
        assert result.resolved_country == "US"
        assert result.message is not None
        assert "Estados Unidos" in result.message
        assert "Los Ángeles" in result.message

    def test_cross_country_policy_mixing_us_policy_on_zaragoza_order_is_blocked(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Reverse policy-mixing check: Applying US return policy to a Zaragoza (Spain) order is refused."""
        query = "Please apply the United States return policy to my order in Zaragoza because the US SLA is better."
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=spain_b2c_session,
            language="en",
        )

        assert result.action == "block"
        assert result.failure_category == "content"
        assert result.input_category == "policy_mismatch"
        assert result.reason_code == "CROSS_COUNTRY_POLICY_MIXING"
        assert result.resolved_country == "ES"

    def test_country_resolution_precedence_order_map_over_session_default(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Order #88310 is mapped to 'US' in `order_country_map` even though session primary country is 'ES'."""
        query = "What is the return policy for my order #88310?"
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=spain_b2c_session,
            language="en",
        )

        assert result.action == "allow"
        assert result.resolved_country == "US"

    def test_detect_explicit_fulfillment_country_locations(self) -> None:
        """Explicit city/country mentions map Los Angeles -> US and Zaragoza/Madrid -> ES."""
        assert detect_explicit_fulfillment_country("Mi pedido en Los Ángeles") == "US"
        assert detect_explicit_fulfillment_country("Shipment from Zaragoza warehouse") == "ES"
        assert detect_explicit_fulfillment_country("Entrega en Madrid") == "ES"

    def test_generic_policy_query_without_session_context_has_no_country_and_is_allowed(
        self,
        auth_guard: AuthorizationGuardrailValidator,
    ) -> None:
        """Generic policy query with session_context=None returns resolved_country=None and action='allow'."""
        query = "¿Cuál es la política general de devoluciones?"
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=None,
            language="es",
        )
        assert result.action == "allow"
        assert result.failure_category == "none"
        assert result.resolved_country is None

    def test_spain_policy_query_without_session_context_is_not_blocked_as_us_order(
        self,
        auth_guard: AuthorizationGuardrailValidator,
    ) -> None:
        """Query asking for Spain return policy with session_context=None does not trigger false-positive US cross-country block."""
        query = "Aplica la política de devoluciones de España para compras online"
        result = auth_guard.evaluate_authorization_and_policy(
            query=query,
            session_context=None,
            language="es",
        )
        assert result.action == "allow"
        assert result.failure_category == "none"
        assert result.reason_code == "AUTHORIZATION_AND_POLICY_VERIFIED"
        assert result.resolved_country == "ES"

    def test_cross_customer_order_refusal(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Verify tool execution with unauthorized order #45821 is blocked fail-closed."""
        result = auth_guard.validate_tool_call_authorization(
            session_context=spain_b2c_session,
            tool_name="lookup_order",
            parameters={"order_id": "45821"},
            language="es",
        )
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.reason_code == "ORDER_NOT_IN_AUTHENTICATED_SESSION"
        assert "#45821" in result.message

    def test_cross_brand_metric_isolation(
        self,
        auth_guard: AuthorizationGuardrailValidator,
    ) -> None:
        """Verify cross-brand query is refused when session brand does not match parameters."""
        session = AuthenticatedSessionContext(
            session_id="sess_brand_a",
            customer_id="cust_b2b_a",
            customer_segment="B2B",
            primary_operating_country="ES",
            authorized_order_ids=("ORD-001",),
        )
        # Monkey-patch brand_id onto session context
        object.__setattr__(session, "brand_id", "brand_nike_es")

        result = auth_guard.validate_tool_call_authorization(
            session_context=session,
            tool_name="get_brand_metrics",
            parameters={"brand_id": "brand_adidas_es"},
            language="en",
        )
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.reason_code == "CROSS_BRAND_METRIC_ACCESS_DENIED"

    def test_tool_call_authorization_high_value_return_hitl(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Verify autonomous return approval tool exceeding 100 EUR is blocked for HITL approval."""
        result = auth_guard.validate_tool_call_authorization(
            session_context=spain_b2c_session,
            tool_name="return_approval",
            parameters={"order_id": "10492", "refund_amount_eur": 180.00, "shipment_status": "DELIVERED"},
            language="es",
        )
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.reason_code == "HIGH_VALUE_RETURN_REQUIRES_HUMAN_APPROVAL"
        assert "human_review_queue_id" in result.metadata

    def test_tool_call_authorization_in_transit_carrier_reassignment_hitl(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Verify in-transit carrier reassignment tool is blocked for human supervisor review."""
        result = auth_guard.validate_tool_call_authorization(
            session_context=spain_b2c_session,
            tool_name="carrier_reassignment",
            parameters={
                "order_id": "10492",
                "target_carrier": "MRW",
                "shipment_status": "IN_TRANSIT",
            },
            language="es",
        )
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.reason_code == "IN_TRANSIT_CARRIER_CHANGE_REQUIRES_HUMAN_APPROVAL"
        assert "human_review_queue_id" in result.metadata

    def test_tool_call_authorization_high_value_dispatch_hitl(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Verify high-value parcel dispatch (> 500 EUR) is intercepted at runtime and queued for HITL approval."""
        result = auth_guard.validate_tool_call_authorization(
            session_context=spain_b2c_session,
            tool_name="high_value_dispatch",
            parameters={
                "order_id": "10492",
                "parcel_id": "PKG-HV-901",
                "declared_value_eur": 750.00,
                "address_verified": True,
            },
            language="es",
        )
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.reason_code == "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL"
        assert "human_review_queue_id" in result.metadata
        assert result.metadata["human_review_queue_id"].startswith("req_hitl_")

        # Within autonomous threshold (<= 500 EUR and verified address) is allowed
        allowed_res = auth_guard.validate_tool_call_authorization(
            session_context=spain_b2c_session,
            tool_name="high_value_dispatch",
            parameters={
                "order_id": "10492",
                "parcel_id": "PKG-STD-102",
                "declared_value_eur": 240.00,
                "address_verified": True,
            },
            language="es",
        )
        assert allowed_res.action == "allow"
        assert allowed_res.reason_code == "TOOL_AUTHORIZATION_VERIFIED"

    def test_tool_call_authorization_unverified_address_dispatch_hitl(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Verify parcel dispatch with unverified address is intercepted even below 500 EUR."""
        result = auth_guard.validate_tool_call_authorization(
            session_context=spain_b2c_session,
            tool_name="confirm_dispatch",
            parameters={
                "parcel_id": "PKG-UNVERIFIED-303",
                "declared_value_eur": 120.00,
                "address_verified": False,
            },
            language="en",
        )
        assert result.action == "block"
        assert result.failure_category == "security"
        assert result.reason_code == "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL"
        assert "human_review_queue_id" in result.metadata

    def test_runtime_inventory_tool_node_blocks_high_value_dispatch_for_hitl(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Verify inventory_tool_node enforces high-value dispatch HITL gate in runtime workflow execution."""
        from application.services.agent_workflow import inventory_tool_node
        from domain.agent.entities import InventoryToolInput, InventoryToolOutput
        from domain.agent.ports import InventoryStockToolPort

        class _StubInventoryTool(InventoryStockToolPort):
            def query_inventory(self, tool_input: InventoryToolInput) -> InventoryToolOutput:
                return InventoryToolOutput(status="success", records=[], total_matched=0)

        state = {
            "query": "Confirm dispatch for order #10492 parcel PKG-HV-999",
            "session_context": spain_b2c_session,
            "language": "es",
            "inventory_tool_input": InventoryToolInput(sku="TF-100"),
            "order_id": "10492",
            "parcel_id": "PKG-HV-999",
            "declared_value_eur": 920.00,
            "address_verified": True,
        }
        res = inventory_tool_node(
            state=state,  # type: ignore[arg-type]
            inventory_tool=_StubInventoryTool(),
            authorization_guard=auth_guard,
        )
        assert res["is_refusal"] is True
        assert res["guardrail_action"] == "block"
        assert res["guardrail_reason_code"] == "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL"
        assert "PKG-HV-999" in res["answer"]

    def test_runtime_ticket_tool_node_blocks_unauthorized_order(
        self,
        auth_guard: AuthorizationGuardrailValidator,
        spain_b2c_session: AuthenticatedSessionContext,
    ) -> None:
        """Verify ticket_tool_node executes validate_tool_call_authorization in runtime and blocks unauthorized order #45821."""
        from application.services.agent_workflow import ticket_tool_node
        from domain.agent.entities import TicketToolInput
        from infrastructure.adapters.mcp_ticket_tool_adapter import McpTicketToolAdapter

        state = {
            "query": "How is ticket for order #45821?",
            "session_context": spain_b2c_session,
            "language": "es",
            "ticket_tool_input": TicketToolInput(ticket_id="45821"),
        }
        res = ticket_tool_node(
            state=state,  # type: ignore[arg-type]
            ticket_tool=McpTicketToolAdapter(),
            authorization_guard=auth_guard,
        )
        assert res["is_refusal"] is True
        assert res["guardrail_action"] == "block"
        assert res["guardrail_reason_code"] == "ORDER_NOT_IN_AUTHENTICATED_SESSION"
        assert "#45821" in res["answer"]

